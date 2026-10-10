"""Faculty subject requests and management-published weekly assignments."""
from datetime import date, datetime, time as time_type, timedelta
from math import ceil
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.clock import get_now
from app.timetable_lock import acquire_timetable_state_lock
from app.deps import get_db, require_roles
from app.engine.slots import PERIOD_SLOTS, SLOTS
from app.models.academic import Department, Faculty, FacultyTeachingEligibility, Section, Subject
from app.models.availability import RoomUnavailability
from app.models.campus import Room
from app.models.faculty_work import (
    ClassroomRequest,
    FacultySubjectAssignment,
    FacultySubjectRequest,
    FacultySubjectRequestItem,
)
from app.models.identity import Setting, User
from app.models.schedule import SessionOverride, TimetableEntry
from app.models.workflow import Notification
from app.schemas.faculty import (
    FacultySubjectAssignmentCreate,
    FacultySubjectAssignmentResponse,
    FacultySubjectAssignmentsUpdate,
    FacultySubjectRequestCreate,
    FacultySubjectRequestDecision,
    FacultySubjectRequestItemResponse,
    FacultySubjectRequestResponse,
    FacultyTeachingEligibilityUpdate,
)

router = APIRouter()
WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _faculty_for_user(db: Session, user: User) -> Faculty:
    faculty = db.query(Faculty).filter(Faculty.user_id == user.id).first()
    if faculty is None:
        raise HTTPException(status_code=404, detail="Faculty profile is not provisioned.")
    return faculty


def _faculty_eligible_sections(db: Session, faculty: Faculty) -> list[Section]:
    eligibility = db.query(FacultyTeachingEligibility).filter(
        FacultyTeachingEligibility.faculty_id == faculty.id
    ).all()
    academic_years = {
        row.academic_year for row in eligibility if row.academic_year is not None
    }
    section_ids = {row.section_id for row in eligibility if row.section_id}
    criteria = []
    if academic_years:
        criteria.append(Section.year.in_(academic_years))
    if section_ids:
        criteria.append(Section.id.in_(section_ids))
    if not criteria:
        return []
    return db.query(Section).filter(or_(*criteria)).order_by(
        Section.year, Section.code
    ).all()


def _eligible_sections(db: Session, faculty: Faculty, subject: Subject) -> list[Section]:
    eligible_section_ids = {
        section.id for section in _faculty_eligible_sections(db, faculty)
    }
    if not eligible_section_ids:
        return []
    return db.query(Section).join(
        TimetableEntry, TimetableEntry.section_id == Section.id
    ).filter(
        TimetableEntry.subject_id == subject.id,
        Section.id.in_(eligible_section_ids),
    ).distinct().order_by(Section.year, Section.code).all()


def _request_response(db: Session, request: FacultySubjectRequest) -> FacultySubjectRequestResponse:
    faculty = db.query(Faculty).filter(Faculty.id == request.faculty_id).first()
    if faculty is None:
        raise HTTPException(status_code=409, detail="The requesting faculty profile no longer exists.")
    department = db.query(Department).filter(Department.id == faculty.department_id).first() if faculty.department_id else None
    items = db.query(FacultySubjectRequestItem).filter(
        FacultySubjectRequestItem.request_id == request.id
    ).order_by(FacultySubjectRequestItem.created_at, FacultySubjectRequestItem.id).all()
    item_responses = []
    for item in items:
        subject = db.query(Subject).filter(Subject.id == item.subject_id).first()
        if subject is None:
            raise HTTPException(status_code=409, detail="A requested subject no longer exists.")
        faculty = db.query(Faculty).filter(Faculty.id == request.faculty_id).first()
        if faculty is None:
            raise HTTPException(status_code=409, detail="The requesting faculty profile no longer exists.")
        sections = db.query(Section).filter(
            Section.id.in_(item.preferred_section_ids or [])
        ).order_by(Section.code).all() if item.preferred_section_ids else []
        eligible_sections = _eligible_sections(db, faculty, subject)
        assignments = db.query(FacultySubjectAssignment).filter(
            FacultySubjectAssignment.request_item_id == item.id
        ).order_by(FacultySubjectAssignment.weekday, FacultySubjectAssignment.start_slot).all()
        assignment_responses = []
        for assignment in assignments:
            section = db.query(Section).filter(Section.id == assignment.section_id).first()
            room = db.query(Room).filter(Room.id == assignment.room_id).first()
            if section is None or room is None:
                raise HTTPException(status_code=409, detail="A staged assignment references missing data.")
            assignment_responses.append(FacultySubjectAssignmentResponse(
                id=assignment.id,
                section_id=section.id,
                section_code=section.code,
                room_id=room.id,
                room_code=room.code,
                weekday=assignment.weekday,
                start_slot=assignment.start_slot,
                duration_slots=assignment.duration_slots,
                published=assignment.timetable_entry_id is not None,
            ))
        item_responses.append(FacultySubjectRequestItemResponse(
            id=item.id,
            subject_id=subject.id,
            subject_code=subject.code,
            subject_name=subject.name,
            subject_kind=subject.kind,
            subject_lab_kind=subject.lab_kind,
            required_facilities=subject.required_facilities or [],
            preferred_section_ids=item.preferred_section_ids or [],
            preferred_sections=[{"id": section.id, "code": section.code} for section in sections],
            eligible_sections=[{"id": section.id, "code": section.code, "strength": section.strength} for section in eligible_sections],
            availability=item.availability or {},
            periods_per_week=item.periods_per_week,
            status=item.status,
            decision_reason=item.decision_reason,
            assignments=assignment_responses,
        ))
    return FacultySubjectRequestResponse(
        id=request.id,
        faculty_id=faculty.id,
        faculty_name=faculty.name or "Faculty",
        department=department.name if department else None,
        designation=faculty.designation,
        note=request.note,
        status=request.status,
        created_at=request.created_at.isoformat(),
        items=item_responses,
    )


def _refresh_request_status(db: Session, request: FacultySubjectRequest) -> None:
    db.flush()
    statuses = [row[0] for row in db.query(FacultySubjectRequestItem.status).filter(
        FacultySubjectRequestItem.request_id == request.id
    ).all()]
    if statuses and all(status in {"PUBLISHED", "REJECTED"} for status in statuses):
        request.status = "COMPLETED"
    elif statuses and all(status == "PENDING" for status in statuses):
        request.status = "PENDING"
    elif "PUBLISHED" in statuses:
        request.status = "PARTIALLY_PUBLISHED"
    elif "ASSIGNED" in statuses:
        request.status = "ASSIGNMENT_IN_PROGRESS"
    elif "APPROVED" in statuses:
        request.status = "APPROVED"
    else:
        request.status = "IN_REVIEW"
    request.updated_at = get_now()


def _periods(start_slot: str, duration_slots: int) -> set[str]:
    if start_slot not in PERIOD_SLOTS:
        raise HTTPException(status_code=422, detail="Choose a valid teaching period.")
    end_index = PERIOD_SLOTS.index(start_slot) + duration_slots
    if duration_slots < 1 or end_index > len(PERIOD_SLOTS):
        raise HTTPException(status_code=422, detail="The assignment extends beyond the teaching day.")
    return set(PERIOD_SLOTS[PERIOD_SLOTS.index(start_slot):end_index])


def _time_range(periods: set[str]) -> tuple[time_type, time_type]:
    first = next(slot for slot in PERIOD_SLOTS if slot in periods)
    last = next(slot for slot in reversed(PERIOD_SLOTS) if slot in periods)
    return SLOTS[first][0], SLOTS[last][1]


def _lab_group_size(db: Session, section: Section) -> int:
    setting = db.query(Setting).filter(Setting.key == "lab_batches").first()
    value = setting.value if setting else 2
    if isinstance(value, dict):
        value = value.get("lab_batches", value.get("value", 2))
    try:
        batches = max(int(value), 1)
    except (TypeError, ValueError):
        batches = 2
    return ceil(section.strength / batches)


def _next_weekday(start: date, weekday: int) -> date:
    return start + timedelta(days=(weekday - start.weekday()) % 7)


def _validate_room_and_slot(
    db: Session,
    faculty: Faculty,
    item: FacultySubjectRequestItem,
    subject: Subject,
    section: Section,
    room: Room,
    weekday: int,
    periods: set[str],
) -> None:
    if section.id not in {row.id for row in _eligible_sections(db, faculty, subject)}:
        raise HTTPException(status_code=422, detail="The selected section is not eligible for this faculty subject.")
    if item.preferred_section_ids and section.id not in item.preferred_section_ids:
        raise HTTPException(status_code=422, detail="Choose one of the requested preferred sections.")
    if room.status is None or room.status.upper() != "ACTIVE" or not room.allocatable_for_classes:
        raise HTTPException(status_code=422, detail="The selected room is not active and allocatable for classes.")

    is_lab = (subject.kind or "THEORY").upper() == "LAB"
    if is_lab:
        if room.resource_type != "LAB":
            raise HTTPException(status_code=422, detail="Lab subjects require a lab room.")
        if subject.lab_kind and room.lab_kind != subject.lab_kind:
            raise HTTPException(status_code=422, detail="The selected lab does not match the subject lab kind.")
        required_strength = _lab_group_size(db, section)
    else:
        if room.resource_type not in {"CLASSROOM", "SEMINAR_HALL"}:
            raise HTTPException(status_code=422, detail="Theory subjects require a classroom or seminar hall.")
        required_strength = section.strength
    if room.capacity is None or room.capacity < required_strength:
        raise HTTPException(status_code=422, detail=f"Room capacity must be recorded and at least {required_strength}.")
    if not set(subject.required_facilities or []).issubset(set(room.facilities or [])):
        raise HTTPException(status_code=422, detail="The selected room lacks required subject facilities.")

    allowed = {day.upper(): set(slots) for day, slots in (item.availability or {}).items()}
    if allowed and not periods.issubset(allowed.get(WEEKDAYS[weekday], set())):
        raise HTTPException(status_code=422, detail="The assignment is outside the faculty member's stated availability.")

    proposed_start, proposed_end = _time_range(periods)
    existing = db.query(TimetableEntry).filter(TimetableEntry.weekday == weekday).all()
    entry_ids = [entry.id for entry in existing]
    overrides = db.query(SessionOverride).filter(
        SessionOverride.entry_id.in_(entry_ids),
        SessionOverride.active.is_(True),
    ).all() if entry_ids else []
    overrides_by_entry = {override.entry_id: override for override in overrides}

    for entry in existing:
        entry_periods = _periods(entry.start_slot, max(entry.duration_slots or 1, 1))
        if not periods.intersection(entry_periods):
            continue
        if entry.faculty_id == faculty.id:
            raise HTTPException(status_code=409, detail="The faculty member already has a class in this time slot.")
        if entry.section_id == section.id:
            raise HTTPException(status_code=409, detail="The selected section already has a class in this time slot.")
        if entry.base_room_id == room.id:
            raise HTTPException(status_code=409, detail="The selected room is already occupied in this time slot.")

    today = get_now().date()
    for override in overrides:
        entry = next((row for row in existing if row.id == override.entry_id), None)
        if entry is None or override.date.date() < today or override.date.weekday() != weekday:
            continue
        override_periods = _periods(
            override.start_slot_override or entry.start_slot,
            max(entry.duration_slots or 1, 1),
        )
        if not periods.intersection(override_periods):
            continue
        if entry.faculty_id == faculty.id:
            raise HTTPException(status_code=409, detail="An active dated timetable override conflicts with this faculty member.")
        if entry.section_id == section.id:
            raise HTTPException(status_code=409, detail="An active dated timetable override conflicts with this section.")
        if override.room_id == room.id:
            raise HTTPException(status_code=409, detail="An active dated timetable override occupies this room and slot.")

    staged_assignments = db.query(FacultySubjectAssignment).join(
        FacultySubjectRequestItem,
        FacultySubjectRequestItem.id == FacultySubjectAssignment.request_item_id,
    ).join(
        FacultySubjectRequest,
        FacultySubjectRequest.id == FacultySubjectRequestItem.request_id,
    ).filter(
        FacultySubjectRequest.faculty_id == faculty.id,
        FacultySubjectRequestItem.status == "ASSIGNED",
        FacultySubjectAssignment.request_item_id != item.id,
        FacultySubjectAssignment.timetable_entry_id.is_(None),
        FacultySubjectAssignment.weekday == weekday,
    ).all()
    for staged in staged_assignments:
        staged_periods = _periods(staged.start_slot, max(staged.duration_slots or 1, 1))
        if periods.intersection(staged_periods):
            if staged.room_id == room.id:
                raise HTTPException(status_code=409, detail="Another staged assignment reserves this room and slot.")
            raise HTTPException(status_code=409, detail="This faculty member has another staged assignment in this time slot.")

    for unavailable in db.query(RoomUnavailability).filter(
        RoomUnavailability.room_id == room.id,
        RoomUnavailability.active.is_(True),
    ).all():
        occurrence = _next_weekday(max(today, unavailable.start_dt.date()), weekday)
        while occurrence <= unavailable.end_dt.date():
            if (
                unavailable.start_dt < datetime.combine(occurrence, proposed_end)
                and unavailable.end_dt > datetime.combine(occurrence, proposed_start)
            ):
                raise HTTPException(status_code=409, detail="The room is unavailable during a recurring assignment slot.")
            occurrence += timedelta(days=7)

    extras = db.query(ClassroomRequest).filter(
        ClassroomRequest.status == "APPROVED",
        ClassroomRequest.requested_date >= today,
    ).all()
    for extra in extras:
        if extra.requested_date.weekday() != weekday:
            continue
        if max(proposed_start, extra.start_time) >= min(proposed_end, extra.end_time):
            continue
        if extra.faculty_id == faculty.id or extra.section_id == section.id:
            raise HTTPException(status_code=409, detail="An approved extra class conflicts with this faculty or section slot.")
        if extra.approved_room_id == room.id:
            raise HTTPException(status_code=409, detail="An approved extra class reserves this room and slot.")


def _validate_assignments(
    db: Session,
    request: FacultySubjectRequest,
    item: FacultySubjectRequestItem,
    assignments: list[FacultySubjectAssignmentCreate],
) -> tuple[Faculty, Subject]:
    faculty = db.query(Faculty).filter(Faculty.id == request.faculty_id).first()
    subject = db.query(Subject).filter(Subject.id == item.subject_id).first()
    if faculty is None or subject is None:
        raise HTTPException(status_code=409, detail="Faculty or requested subject no longer exists.")
    if sum(assignment.duration_slots for assignment in assignments) != item.periods_per_week:
        raise HTTPException(status_code=422, detail=f"Assignment durations must total {item.periods_per_week} teaching periods per week.")

    # Serialize this workflow's competing slot allocations on shared faculty,
    # section, and room rows until the staging/publish transaction completes.
    db.query(Faculty).filter(Faculty.id == faculty.id).with_for_update().first()
    section_ids = sorted({assignment.section_id for assignment in assignments})
    room_ids = sorted({assignment.room_id for assignment in assignments})
    if section_ids:
        db.query(Section).filter(Section.id.in_(section_ids)).order_by(Section.id).with_for_update().all()
    if room_ids:
        db.query(Room).filter(Room.id.in_(room_ids)).order_by(Room.id).with_for_update().all()

    proposed: list[tuple[int, set[str]]] = []
    for assignment in assignments:
        section = db.query(Section).filter(Section.id == assignment.section_id).first()
        room = db.query(Room).filter(Room.id == assignment.room_id).first()
        if section is None or room is None:
            raise HTTPException(status_code=422, detail="Choose an existing section and room.")
        periods = _periods(assignment.start_slot, assignment.duration_slots)
        if any(day == assignment.weekday and periods.intersection(previous) for day, previous in proposed):
            raise HTTPException(status_code=409, detail="Proposed assignments overlap for the same faculty member.")
        proposed.append((assignment.weekday, periods))
        _validate_room_and_slot(db, faculty, item, subject, section, room, assignment.weekday, periods)
    return faculty, subject


def _notify_faculty(
    db: Session,
    request: FacultySubjectRequest,
    item: FacultySubjectRequestItem,
    title: str,
    body: str,
) -> None:
    db.add(Notification(
        id=_id("notif"),
        audience_type="FACULTY",
        audience_id=request.faculty_id,
        type="FACULTY_SUBJECT_REQUEST",
        title=title,
        body=body,
        payload={"request_id": request.id, "request_item_id": item.id, "status": item.status},
        created_at=get_now(),
    ))


@router.get("/management/faculty-teaching-eligibility")
def list_faculty_teaching_eligibility(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    faculty_rows = db.query(Faculty).order_by(Faculty.name, Faculty.employee_id).all()
    departments = {
        department.id: department.name
        for department in db.query(Department).all()
    }
    accounts = {
        account.id: account
        for account in db.query(User).filter(
            User.id.in_({faculty.user_id for faculty in faculty_rows if faculty.user_id})
        ).all()
    }
    sections = db.query(Section).order_by(Section.year, Section.code).all()
    eligibility_rows = db.query(FacultyTeachingEligibility).all()
    return {
        "faculty": [{
            "id": faculty.id,
            "name": faculty.name or (
                accounts[faculty.user_id].display_name
                if faculty.user_id in accounts else None
            ) or "Faculty",
            "employee_id": faculty.employee_id,
            "department": departments.get(faculty.department_id),
        } for faculty in faculty_rows],
        "academic_years": sorted({section.year for section in sections}),
        "sections": [{
            "id": section.id,
            "code": section.code,
            "name": section.name,
            "year": section.year,
            "department": departments.get(section.department_id),
        } for section in sections],
        "eligibility": [{
            "faculty_id": row.faculty_id,
            "academic_year": row.academic_year,
            "section_id": row.section_id,
        } for row in eligibility_rows],
    }


@router.put("/management/faculty/{faculty_id}/teaching-eligibility")
def update_faculty_teaching_eligibility(
    faculty_id: str,
    body: FacultyTeachingEligibilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).with_for_update().first()
    if faculty is None:
        raise HTTPException(status_code=404, detail="Faculty member not found.")
    valid_years = {
        row[0] for row in db.query(Section.year).distinct().all()
    }
    invalid_years = set(body.academic_years) - valid_years
    if invalid_years:
        raise HTTPException(
            status_code=422,
            detail="Eligibility years must match academic years represented by existing sections.",
        )
    sections = db.query(Section).filter(
        Section.id.in_(body.section_ids)
    ).all() if body.section_ids else []
    if len(sections) != len(body.section_ids):
        raise HTTPException(
            status_code=422,
            detail="Eligibility may reference only existing sections.",
        )

    db.query(FacultyTeachingEligibility).filter(
        FacultyTeachingEligibility.faculty_id == faculty.id
    ).delete(synchronize_session=False)
    db.add_all([
        FacultyTeachingEligibility(
            id=_id("elig"),
            faculty_id=faculty.id,
            academic_year=academic_year,
        )
        for academic_year in body.academic_years
    ] + [
        FacultyTeachingEligibility(
            id=_id("elig"),
            faculty_id=faculty.id,
            section_id=section.id,
        )
        for section in sections
    ])
    log_audit(db, user.id, "UPDATE_FACULTY_TEACHING_ELIGIBILITY", "Faculty", faculty.id, {
        "academic_years": sorted(body.academic_years),
        "section_ids": sorted(body.section_ids),
    }, role=user.role)
    db.commit()
    return {
        "faculty_id": faculty.id,
        "academic_years": sorted(body.academic_years),
        "sections": [{"id": section.id, "code": section.code, "year": section.year} for section in sections],
    }


@router.get("/faculty/subject-catalog")
def get_faculty_subject_catalog(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _faculty_for_user(db, user)
    department = db.query(Department).filter(
        Department.id == faculty.department_id
    ).first() if faculty.department_id else None
    eligibility_rows = db.query(FacultyTeachingEligibility).filter(
        FacultyTeachingEligibility.faculty_id == faculty.id
    ).all()
    eligible_academic_years = sorted({
        row.academic_year for row in eligibility_rows
        if row.academic_year is not None
    })
    eligible_sections = _faculty_eligible_sections(db, faculty)
    if not eligible_sections:
        return {
            "department": department.name if department else None,
            "eligible_academic_years": eligible_academic_years,
            "eligible_sections": [],
            "subjects": [],
            "message": (
                "Management has not designated eligible academic years or sections "
                "for your account."
            ),
        }
    eligible_section_ids = {section.id for section in eligible_sections}
    assigned_ids = {
        row[0] for row in db.query(TimetableEntry.subject_id).filter(
            TimetableEntry.faculty_id == faculty.id
        ).all()
    }
    active_requests = db.query(
        FacultySubjectRequestItem.subject_id,
        FacultySubjectRequestItem.status,
    ).join(
        FacultySubjectRequest,
        FacultySubjectRequest.id == FacultySubjectRequestItem.request_id,
    ).filter(
        FacultySubjectRequest.faculty_id == faculty.id,
        FacultySubjectRequestItem.status.in_(("PENDING", "APPROVED", "ASSIGNED")),
    ).all()
    active_request_statuses = {
        subject_id: status for subject_id, status in active_requests
    }
    subjects = db.query(Subject).join(
        TimetableEntry, TimetableEntry.subject_id == Subject.id
        ).filter(
            TimetableEntry.section_id.in_(eligible_section_ids)
            ).order_by(Subject.code, Subject.name).all()
    subjects = list({subject.id: subject for subject in subjects}.values())
    subjects.sort(key=lambda subject: (subject.code or "", subject.name or ""))
    eligible_subjects = [
        (subject, _eligible_sections(db, faculty, subject))
        for subject in subjects
    ]
    eligible_subjects = [
        (subject, sections) for subject, sections in eligible_subjects if sections
    ]
    message = None
    if not eligible_subjects:
        message = (
            "No existing timetable subject-to-section mappings were found for the "
            "academic years or sections designated for your account."
        )
    return {
        "department": department.name if department else None,
        "eligible_academic_years": eligible_academic_years,
        "eligible_sections": [
            {"id": section.id, "code": section.code, "year": section.year}
            for section in eligible_sections
        ],
        "message": message,
        "subjects": [{
            "id": subject.id,
            "code": subject.code,
            "name": subject.name,
            "kind": subject.kind,
            "already_assigned": subject.id in assigned_ids,
            "active_request_status": active_request_statuses.get(subject.id),
            "is_synthetic": bool(subject.is_synthetic),
            "eligible_sections": [{"id": section.id, "code": section.code} for section in sections],
        } for subject, sections in eligible_subjects],
    }


@router.get("/faculty/subject-requests", response_model=list[FacultySubjectRequestResponse])
def list_faculty_subject_requests(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _faculty_for_user(db, user)
    requests = db.query(FacultySubjectRequest).filter(
        FacultySubjectRequest.faculty_id == faculty.id
    ).order_by(FacultySubjectRequest.created_at.desc()).all()
    return [_request_response(db, request) for request in requests]


@router.post("/faculty/subject-requests", response_model=FacultySubjectRequestResponse, status_code=201)
def create_faculty_subject_request(
    body: FacultySubjectRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _faculty_for_user(db, user)
    faculty = db.query(Faculty).filter(Faculty.id == faculty.id).with_for_update().first()
    if not _faculty_eligible_sections(db, faculty):
        raise HTTPException(
            status_code=409,
            detail="Management must designate eligible academic years or sections before you can request subjects.",
        )
    subject_ids = {item.subject_id for item in body.items}
    subjects = db.query(Subject).filter(
        Subject.id.in_(subject_ids),
    ).all()
    if len(subjects) != len(subject_ids):
        raise HTTPException(status_code=422, detail="Requests may include only existing subjects.")
    subjects_by_id = {subject.id: subject for subject in subjects}
    if any(not _eligible_sections(db, faculty, subjects_by_id[subject_id]) for subject_id in subject_ids):
        raise HTTPException(
            status_code=422,
            detail="Requests may include only subjects offered to the faculty member's designated sections or academic years.",
        )
    assigned_subject_ids = {
        row[0] for row in db.query(TimetableEntry.subject_id).filter(
            TimetableEntry.faculty_id == faculty.id,
            TimetableEntry.subject_id.in_(subject_ids),
        ).all()
    }
    if assigned_subject_ids:
        raise HTTPException(status_code=409, detail="You already have a published timetable assignment for one of these subjects.")
    active_request = db.query(FacultySubjectRequestItem).join(
        FacultySubjectRequest, FacultySubjectRequest.id == FacultySubjectRequestItem.request_id
    ).filter(
        FacultySubjectRequest.faculty_id == faculty.id,
        FacultySubjectRequestItem.subject_id.in_(subject_ids),
        FacultySubjectRequestItem.status.in_(["PENDING", "APPROVED", "ASSIGNED"]),
    ).first()
    if active_request:
        raise HTTPException(status_code=409, detail="An active request already exists for one of these subjects.")
    for requested in body.items:
        if requested.preferred_section_ids:
            eligible_ids = {section.id for section in _eligible_sections(db, faculty, subjects_by_id[requested.subject_id])}
            if not set(requested.preferred_section_ids).issubset(eligible_ids):
                raise HTTPException(status_code=422, detail="Preferred sections must be linked to this subject and the faculty member's designated eligibility.")
    now = get_now()
    request = FacultySubjectRequest(
        id=_id("fsr"), faculty_id=faculty.id, status="PENDING", note=body.note,
        created_at=now, updated_at=now,
    )
    db.add(request)
    db.flush()
    for requested in body.items:
        db.add(FacultySubjectRequestItem(
            id=_id("fsri"),
            request_id=request.id,
            subject_id=requested.subject_id,
            preferred_section_ids=requested.preferred_section_ids,
            availability={day.upper(): slots for day, slots in requested.availability.items()},
            periods_per_week=requested.periods_per_week,
            status="PENDING",
            created_at=now,
            updated_at=now,
        ))
    try:
        log_audit(db, user.id, "CREATE_FACULTY_SUBJECT_REQUEST", "FacultySubjectRequest", request.id, {
            "subject_ids": sorted(subject_ids),
        }, role=user.role)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The request could not be saved due to a concurrent change.")
    db.refresh(request)
    return _request_response(db, request)


@router.get("/management/faculty-subject-requests", response_model=list[FacultySubjectRequestResponse])
def list_management_faculty_subject_requests(
    request_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    query = db.query(FacultySubjectRequest)
    if request_status:
        request_status = request_status.upper()
        valid_statuses = {"PENDING", "IN_REVIEW", "APPROVED", "ASSIGNMENT_IN_PROGRESS", "PARTIALLY_PUBLISHED", "COMPLETED"}
        if request_status not in valid_statuses:
            raise HTTPException(status_code=422, detail="Unknown faculty subject request status.")
        query = query.filter(FacultySubjectRequest.status == request_status)
    requests = query.order_by(FacultySubjectRequest.created_at.desc()).all()
    return [_request_response(db, request) for request in requests]


@router.post("/management/faculty-subject-requests/{request_id}/items/{item_id}/review", response_model=FacultySubjectRequestResponse)
def review_faculty_subject_request_item(
    request_id: str,
    item_id: str,
    body: FacultySubjectRequestDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    request = db.query(FacultySubjectRequest).filter(
        FacultySubjectRequest.id == request_id
    ).with_for_update().first()
    item = db.query(FacultySubjectRequestItem).filter(
        FacultySubjectRequestItem.id == item_id,
        FacultySubjectRequestItem.request_id == request_id,
    ).with_for_update().first()
    if request is None or item is None:
        raise HTTPException(status_code=404, detail="Faculty subject request item not found.")
    if item.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending subject requests can be reviewed.")
    item.status = body.status
    item.decision_reason = body.reason
    item.decided_by = user.id
    item.updated_at = get_now()
    _refresh_request_status(db, request)
    subject = db.query(Subject).filter(Subject.id == item.subject_id).first()
    label = subject.code if subject else "Subject"
    message = (
        f"Your request for {label} was approved. Management must assign and publish the weekly timetable before it is confirmed."
        if body.status == "APPROVED"
        else body.reason or "Your subject request was rejected."
    )
    _notify_faculty(db, request, item, f"Subject request {body.status.lower()}", message)
    log_audit(db, user.id, f"{body.status}_FACULTY_SUBJECT_REQUEST", "FacultySubjectRequestItem", item.id, {
        "request_id": request.id, "reason": body.reason,
    }, role=user.role)
    db.commit()
    db.refresh(request)
    return _request_response(db, request)


@router.put("/management/faculty-subject-requests/{request_id}/items/{item_id}/assignments", response_model=FacultySubjectRequestResponse)
def stage_faculty_subject_assignments(
    request_id: str,
    item_id: str,
    body: FacultySubjectAssignmentsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    request = db.query(FacultySubjectRequest).filter(FacultySubjectRequest.id == request_id).with_for_update().first()
    item = db.query(FacultySubjectRequestItem).filter(
        FacultySubjectRequestItem.id == item_id,
        FacultySubjectRequestItem.request_id == request_id,
    ).with_for_update().first()
    if request is None or item is None:
        raise HTTPException(status_code=404, detail="Faculty subject request item not found.")
    if item.status not in {"APPROVED", "ASSIGNED"}:
        raise HTTPException(status_code=409, detail="Only approved requests can be assigned.")
    existing = db.query(FacultySubjectAssignment).filter(
        FacultySubjectAssignment.request_item_id == item.id
    ).all()
    if any(assignment.timetable_entry_id for assignment in existing):
        raise HTTPException(status_code=409, detail="Published timetable assignments cannot be replaced.")
    faculty, subject = _validate_assignments(db, request, item, body.assignments)
    for assignment in existing:
        db.delete(assignment)
    db.flush()
    now = get_now()
    for assignment in body.assignments:
        db.add(FacultySubjectAssignment(
            id=_id("fsa"),
            request_item_id=item.id,
            section_id=assignment.section_id,
            room_id=assignment.room_id,
            weekday=assignment.weekday,
            start_slot=assignment.start_slot,
            duration_slots=assignment.duration_slots,
            timetable_entry_id=None,
            created_at=now,
        ))
    item.status = "ASSIGNED"
    item.updated_at = now
    _refresh_request_status(db, request)
    log_audit(db, user.id, "STAGE_FACULTY_SUBJECT_ASSIGNMENTS", "FacultySubjectRequestItem", item.id, {
        "assignment_count": len(body.assignments),
        "periods_per_week": item.periods_per_week,
        "faculty_id": faculty.id,
        "subject_id": subject.id,
    }, role=user.role)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An assignment slot changed concurrently; reload and try again.")
    db.refresh(request)
    return _request_response(db, request)


@router.post("/management/faculty-subject-requests/{request_id}/items/{item_id}/publish", response_model=FacultySubjectRequestResponse)
def publish_faculty_subject_assignments(
    request_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    acquire_timetable_state_lock(db)
    request = db.query(FacultySubjectRequest).filter(FacultySubjectRequest.id == request_id).with_for_update().first()
    item = db.query(FacultySubjectRequestItem).filter(
        FacultySubjectRequestItem.id == item_id,
        FacultySubjectRequestItem.request_id == request_id,
    ).with_for_update().first()
    if request is None or item is None:
        raise HTTPException(status_code=404, detail="Faculty subject request item not found.")
    if item.status != "ASSIGNED":
        raise HTTPException(status_code=409, detail="Stage and validate the weekly timetable before publishing.")
    staged = db.query(FacultySubjectAssignment).filter(
        FacultySubjectAssignment.request_item_id == item.id
    ).order_by(FacultySubjectAssignment.weekday, FacultySubjectAssignment.start_slot).all()
    if not staged or any(assignment.timetable_entry_id for assignment in staged):
        raise HTTPException(status_code=409, detail="No unpublished timetable assignments are available.")
    proposals = [FacultySubjectAssignmentCreate(
        section_id=assignment.section_id,
        room_id=assignment.room_id,
        weekday=assignment.weekday,
        start_slot=assignment.start_slot,
        duration_slots=assignment.duration_slots,
    ) for assignment in staged]
    faculty, subject = _validate_assignments(db, request, item, proposals)
    now = get_now()
    published_entries = []
    for assignment in staged:
        section = db.query(Section).filter(Section.id == assignment.section_id).first()
        if section is None:
            raise HTTPException(status_code=409, detail="A selected section no longer exists.")
        synthetic = bool(faculty.is_synthetic or subject.is_synthetic or section.is_synthetic)
        entry = TimetableEntry(
            id=_id("fte"),
            section_id=assignment.section_id,
            subject_id=subject.id,
            faculty_id=faculty.id,
            weekday=assignment.weekday,
            start_slot=assignment.start_slot,
            duration_slots=assignment.duration_slots,
            kind=(subject.kind or "THEORY").upper(),
            required_room_type="LAB" if (subject.kind or "THEORY").upper() == "LAB" else "CLASSROOM",
            required_lab_kind=subject.lab_kind,
            required_facilities=subject.required_facilities or [],
            base_room_id=assignment.room_id,
            provenance="SYNTHETIC_CONFIGURED" if synthetic else "MANAGEMENT_ASSIGNED",
        )
        db.add(entry)
        db.flush()
        assignment.timetable_entry_id = entry.id
        published_entries.append((assignment, section, entry))
    item.status = "PUBLISHED"
    item.updated_at = now
    _refresh_request_status(db, request)
    _notify_faculty(db, request, item, "Teaching assignment published", f"{subject.code} has been published to your weekly timetable.")
    for assignment, section, entry in published_entries:
        db.add(Notification(
            id=_id("notif"),
            audience_type="SECTION",
            audience_id=section.id,
            type="FACULTY_SUBJECT_ASSIGNMENT",
            title="New class added to your timetable",
            body=f"{subject.code} is scheduled at {assignment.start_slot}.",
            payload={"timetable_entry_id": entry.id, "subject_id": subject.id, "faculty_id": faculty.id},
            created_at=now,
        ))
    log_audit(db, user.id, "PUBLISH_FACULTY_SUBJECT_ASSIGNMENTS", "FacultySubjectRequestItem", item.id, {
        "timetable_entry_ids": [row[2].id for row in published_entries],
        "faculty_id": faculty.id,
        "subject_id": subject.id,
    }, role=user.role)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The timetable changed during publication; refresh and validate again.")
    db.refresh(request)
    return _request_response(db, request)
