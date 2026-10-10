"""Identity-scoped faculty teaching portal and classroom resource requests."""
import uuid
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.clock import get_now
from app.deps import get_db, require_roles
from app.engine.slots import PERIOD_SLOTS, SLOTS
from app.models.academic import Department, Faculty, Section, Student, Subject
from app.models.academic_content import AcademicMark, AcademicResource, SyllabusModule
from app.models.availability import RoomUnavailability
from app.models.campus import Floor, Room
from app.models.faculty_work import (
    AttendanceRecord,
    AttendanceSession,
    ClassroomRequest,
    FacultySubjectAssignment,
    FacultySubjectRequest,
    FacultySubjectRequestItem,
)
from app.models.identity import User
from app.models.operations import Assessment
from app.models.operations import Announcement
from app.announcement_access import announcement_visible
from app.models.schedule import SessionOverride, TimetableEntry
from app.models.workflow import Notification
from app.routers.timetable import _approved_request_entries, _enrich_entries
from app.schemas.faculty import (
    AttendanceSessionCreate,
    AttendanceSessionResponse,
    ClassroomRequestCreate,
    ClassroomRequestDecision,
    ClassroomRequestRejection,
    ClassroomRequestResponse,
    FacultyClassroomOptionsResponse,
    FacultyProfileResponse,
    FacultySectionResponse,
    FacultySubjectResponse,
)
from app.schemas.academic import (
    AcademicResourceCreate,
    AssessmentCreate,
    AttendanceMarkRequest,
    AttendanceSessionDetailResponse,
    AttendanceStudentResponse,
    MarkEntryRequest,
    SyllabusModuleCreate,
)

router = APIRouter()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _get_faculty(db: Session, user: User) -> Faculty:
    faculty = db.query(Faculty).filter(Faculty.user_id == user.id).first()
    if faculty is None:
        raise HTTPException(status_code=404, detail="Faculty profile is not provisioned.")
    return faculty


def _assignments(db: Session, faculty_id: str) -> list[TimetableEntry]:
    return db.query(TimetableEntry).filter(
        TimetableEntry.faculty_id == faculty_id
    ).all()


def _require_academic_assignment(
    db: Session,
    faculty: Faculty,
    subject_id: str,
    section_id: str | None = None,
) -> TimetableEntry:
    query = db.query(TimetableEntry).filter(
        TimetableEntry.faculty_id == faculty.id,
        TimetableEntry.subject_id == subject_id,
    )
    if section_id is not None:
        query = query.filter(TimetableEntry.section_id == section_id)
    entry = query.first()
    if entry is None:
        raise HTTPException(
            status_code=403,
            detail="You can manage academic records only for subjects and sections assigned to you.",
        )
    return entry


def _request_response(db: Session, request: ClassroomRequest) -> ClassroomRequestResponse:
    faculty = db.query(Faculty).filter(Faculty.id == request.faculty_id).first()
    user = db.query(User).filter(User.id == faculty.user_id).first() if faculty and faculty.user_id else None
    subject = db.query(Subject).filter(Subject.id == request.subject_id).first()
    section = db.query(Section).filter(Section.id == request.section_id).first()
    preferred_room = db.query(Room).filter(Room.id == request.preferred_room_id).first() if request.preferred_room_id else None
    approved_room = db.query(Room).filter(Room.id == request.approved_room_id).first() if request.approved_room_id else None
    if not faculty or not subject or not section:
        raise HTTPException(status_code=409, detail="Classroom request references incomplete academic data.")
    return ClassroomRequestResponse(
        id=request.id,
        faculty_id=faculty.id,
        faculty_name=faculty.name or (user.display_name if user else "Faculty"),
        employee_id=faculty.employee_id,
        subject_id=subject.id,
        subject_code=subject.code,
        subject_name=subject.name,
        section_id=section.id,
        section_code=section.code,
        requested_date=request.requested_date,
        start_time=request.start_time,
        end_time=request.end_time,
        expected_strength=request.expected_strength,
        preferred_floor_id=request.preferred_floor_id,
        preferred_room_id=request.preferred_room_id,
        preferred_room_code=preferred_room.code if preferred_room else None,
        reason=request.reason,
        status=request.status,
        approved_room_id=request.approved_room_id,
        approved_room_code=approved_room.code if approved_room else None,
        decision_reason=request.decision_reason,
        created_at=request.created_at.isoformat(),
    )


def _validate_request_assignment(
    db: Session,
    faculty: Faculty,
    body: ClassroomRequestCreate,
) -> tuple[Section, list[TimetableEntry]]:
    if body.requested_date < get_now().date():
        raise HTTPException(status_code=422, detail="Classroom requests must be for today or a future date.")
    section = db.query(Section).filter(Section.id == body.section_id).first()
    if section is None:
        raise HTTPException(status_code=422, detail="Select an existing section.")
    assignments = db.query(TimetableEntry).filter(
        TimetableEntry.faculty_id == faculty.id,
        TimetableEntry.section_id == section.id,
        TimetableEntry.subject_id == body.subject_id,
    ).all()
    if not assignments:
        raise HTTPException(
            status_code=403,
            detail="You can request a classroom only for a subject and section assigned to you.",
        )
    if section.strength is not None and body.expected_strength > section.strength:
        raise HTTPException(
            status_code=422,
            detail=f"Expected student strength cannot exceed the section strength ({section.strength}).",
        )
    if body.preferred_floor_id and not db.query(Floor).filter(
        Floor.id == body.preferred_floor_id
    ).first():
        raise HTTPException(status_code=422, detail="Select an existing preferred floor.")
    if body.preferred_room_id:
        preferred_room = db.query(Room).filter(Room.id == body.preferred_room_id).first()
        if preferred_room is None:
            raise HTTPException(status_code=422, detail="Select an existing preferred room.")
        if body.preferred_floor_id and preferred_room.floor_id != body.preferred_floor_id:
            raise HTTPException(status_code=422, detail="The preferred room is not on the preferred floor.")
    return section, assignments


def _time_overlaps(start: time, end: time, other_start: time, other_end: time) -> bool:
    return max(start, other_start) < min(end, other_end)


def _entry_interval(entry: TimetableEntry, override: SessionOverride | None) -> tuple[time, time] | None:
    start_slot = (
        override.start_slot_override
        if override and override.start_slot_override
        else entry.start_slot
    )
    if start_slot not in PERIOD_SLOTS:
        return None
    start_index = PERIOD_SLOTS.index(start_slot)
    end_index = start_index + max(entry.duration_slots or 1, 1) - 1
    if end_index >= len(PERIOD_SLOTS):
        return None
    return SLOTS[start_slot][0], SLOTS[PERIOD_SLOTS[end_index]][1]


def _validate_room_for_request(
    db: Session,
    request: ClassroomRequest,
    room: Room,
    assignments: list[TimetableEntry],
) -> None:
    if room.status is None or room.status.upper() != "ACTIVE":
        raise HTTPException(status_code=422, detail="The selected room is not active.")
    if not room.allocatable_for_classes:
        raise HTTPException(status_code=422, detail="The selected room is not available for classes.")
    if room.capacity is None or room.capacity < request.expected_strength:
        raise HTTPException(
            status_code=422,
            detail=f"The selected room does not meet the requested capacity of {request.expected_strength}.",
        )
    required_room_types = {entry.required_room_type for entry in assignments if entry.required_room_type}
    if required_room_types and room.resource_type not in required_room_types:
        raise HTTPException(status_code=422, detail="The selected room does not meet the class room-type requirement.")
    required_lab_kinds = {entry.required_lab_kind for entry in assignments if entry.required_lab_kind}
    if required_lab_kinds and room.lab_kind not in required_lab_kinds:
        raise HTTPException(status_code=422, detail="The selected room does not meet the class lab requirement.")
    required_facilities = {
        facility
        for entry in assignments
        for facility in (entry.required_facilities or [])
    }
    if not required_facilities.issubset(set(room.facilities or [])):
        raise HTTPException(status_code=422, detail="The selected room lacks required class facilities.")

    requested_start = datetime.combine(request.requested_date, request.start_time)
    requested_end = datetime.combine(request.requested_date, request.end_time)
    unavailable = db.query(RoomUnavailability).filter(
        RoomUnavailability.room_id == room.id,
        RoomUnavailability.active.is_(True),
        RoomUnavailability.start_dt < requested_end,
        RoomUnavailability.end_dt > requested_start,
    ).first()
    if unavailable:
        raise HTTPException(status_code=409, detail="The selected room is unavailable during this time.")

    approved_request_conflict = db.query(ClassroomRequest).filter(
        ClassroomRequest.status == "APPROVED",
        ClassroomRequest.approved_room_id == room.id,
        ClassroomRequest.requested_date == request.requested_date,
        ClassroomRequest.start_time < request.end_time,
        ClassroomRequest.end_time > request.start_time,
        ClassroomRequest.id != request.id,
    ).first()
    if approved_request_conflict:
        raise HTTPException(status_code=409, detail="The selected room is booked for another approved request.")

    weekday = request.requested_date.weekday()
    entries = db.query(TimetableEntry).filter(TimetableEntry.weekday == weekday).all()
    entry_ids = [entry.id for entry in entries]
    day_start = datetime.combine(request.requested_date, time.min)
    next_day = day_start + timedelta(days=1)
    overrides = db.query(SessionOverride).filter(
        SessionOverride.entry_id.in_(entry_ids),
        SessionOverride.date >= day_start,
        SessionOverride.date < next_day,
        SessionOverride.active.is_(True),
    ).all() if entry_ids else []
    overrides_by_entry = {override.entry_id: override for override in overrides}
    for entry in entries:
        override = overrides_by_entry.get(entry.id)
        interval = _entry_interval(entry, override)
        if not interval or not _time_overlaps(
            request.start_time, request.end_time, interval[0], interval[1]
        ):
            continue
        effective_room_id = override.room_id if override else entry.base_room_id
        if effective_room_id == room.id:
            raise HTTPException(status_code=409, detail="The selected room conflicts with a scheduled class.")
        if entry.faculty_id == request.faculty_id or entry.section_id == request.section_id:
            raise HTTPException(
                status_code=409,
                detail="The faculty member or section has another class during this time.",
            )


@router.get("/faculty/profile", response_model=FacultyProfileResponse)
def get_faculty_profile(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    department = db.query(Department).filter(Department.id == faculty.department_id).first()
    return FacultyProfileResponse(
        full_name=faculty.name or user.display_name or user.email,
        employee_id=faculty.employee_id,
        email=user.email,
        department=department.name if department else None,
        designation=faculty.designation,
        active=bool(user.active),
    )


@router.get("/faculty/timetable")
def get_faculty_timetable(
    date_str: str | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    entries = _assignments(db, faculty.id)
    result = _enrich_entries(entries, db, date_str)
    if date_str:
        requested_date = date.fromisoformat(date_str)
        result.extend(_approved_request_entries(
            db,
            requested_date,
            faculty_id=faculty.id,
        ))
    return result


@router.get("/faculty/subjects", response_model=list[FacultySubjectResponse])
def get_faculty_subjects(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    assignments = _assignments(db, faculty.id)
    subject_entries: dict[str, list[TimetableEntry]] = {}
    for entry in assignments:
        if entry.subject_id:
            subject_entries.setdefault(entry.subject_id, []).append(entry)
    result = []
    published_subject_ids = set(subject_entries)
    for subject_id, entries in subject_entries.items():
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if subject is None:
            continue
        sections = db.query(Section).filter(
            Section.id.in_({entry.section_id for entry in entries})
        ).all()
        result.append(FacultySubjectResponse(
            id=subject.id,
            code=subject.code,
            name=subject.name,
            kind=subject.kind,
            sections=sorted(section.code for section in sections),
            semesters=[],
            assignment_status="PUBLISHED",
            weekly_periods=sum(max(entry.duration_slots or 1, 1) for entry in entries),
            weekly_hours=round(
                sum(max(entry.duration_slots or 1, 1) for entry in entries) * 55 / 60,
                2,
            ),
            demo_data=bool(
                subject.is_synthetic
                or any(
                    entry.provenance
                    and ("demo" in entry.provenance.casefold() or "synthetic" in entry.provenance.casefold())
                    for entry in entries
                )
            ),
        ))
    request_items = db.query(FacultySubjectRequestItem).join(
        FacultySubjectRequest,
        FacultySubjectRequest.id == FacultySubjectRequestItem.request_id,
    ).filter(
        FacultySubjectRequest.faculty_id == faculty.id,
        FacultySubjectRequestItem.status.in_(("PENDING", "APPROVED", "ASSIGNED")),
    ).order_by(
        FacultySubjectRequestItem.created_at,
        FacultySubjectRequestItem.id,
    ).all()
    for item in request_items:
        if item.subject_id in published_subject_ids:
            continue
        subject = db.query(Subject).filter(Subject.id == item.subject_id).first()
        if subject is None:
            continue
        staged = db.query(FacultySubjectAssignment).filter(
            FacultySubjectAssignment.request_item_id == item.id
        ).order_by(
            FacultySubjectAssignment.weekday,
            FacultySubjectAssignment.start_slot,
        ).all()
        section_ids = {assignment.section_id for assignment in staged}
        if not section_ids:
            section_ids = set(item.preferred_section_ids or [])
        sections = db.query(Section).filter(Section.id.in_(section_ids)).all() if section_ids else []
        weekly_periods = (
            sum(max(assignment.duration_slots or 1, 1) for assignment in staged)
            if staged else item.periods_per_week
        )
        result.append(FacultySubjectResponse(
            id=subject.id,
            code=subject.code,
            name=subject.name,
            kind=subject.kind,
            sections=sorted(section.code for section in sections),
            semesters=[],
            assignment_status=item.status,
            weekly_periods=weekly_periods,
            weekly_hours=round(weekly_periods * 55 / 60, 2),
            demo_data=bool(subject.is_synthetic),
        ))
    return sorted(result, key=lambda item: (item.code.casefold(), item.name.casefold()))


@router.get("/faculty/sections", response_model=list[FacultySectionResponse])
def get_faculty_sections(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    assignments = _assignments(db, faculty.id)
    section_entries: dict[str, list[TimetableEntry]] = {}
    for entry in assignments:
        if entry.section_id:
            section_entries.setdefault(entry.section_id, []).append(entry)
    result = []
    for section_id, entries in section_entries.items():
        section = db.query(Section).filter(Section.id == section_id).first()
        if section is None:
            continue
        department = db.query(Department).filter(Department.id == section.department_id).first()
        subject_ids = {entry.subject_id for entry in entries if entry.subject_id}
        subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all() if subject_ids else []
        result.append(FacultySectionResponse(
            id=section.id,
            code=section.code,
            name=section.name,
            department=department.name if department else None,
            year=section.year,
            strength=section.strength,
            subjects=sorted(subject.code for subject in subjects),
            demo_data=bool(section.is_synthetic),
        ))
    return sorted(result, key=lambda item: item.code.casefold())


@router.get("/faculty/attendance", response_model=list[AttendanceSessionResponse])
def list_attendance_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    sessions = db.query(AttendanceSession).filter(
        AttendanceSession.faculty_id == faculty.id
    ).order_by(AttendanceSession.session_date.desc(), AttendanceSession.start_time).all()
    results = []
    for session in sessions:
        section = db.query(Section).filter(Section.id == session.section_id).first()
        subject = db.query(Subject).filter(Subject.id == session.subject_id).first()
        records_entered = db.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == session.id
        ).count()
        if section and subject:
            results.append(AttendanceSessionResponse(
                id=session.id,
                timetable_entry_id=session.timetable_entry_id,
                session_date=session.session_date,
                start_time=session.start_time,
                status=session.status,
                section_code=section.code,
                subject_code=subject.code,
                subject_name=subject.name,
                records_entered=records_entered,
            ))
    return results


@router.post(
    "/faculty/attendance",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_attendance_session(
    body: AttendanceSessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    if body.session_date != get_now().date():
        raise HTTPException(status_code=422, detail="Attendance sessions can only be started for today.")
    entry = db.query(TimetableEntry).filter(
        TimetableEntry.id == body.timetable_entry_id,
        TimetableEntry.faculty_id == faculty.id,
        TimetableEntry.weekday == body.session_date.weekday(),
    ).first()
    if entry is None:
        raise HTTPException(status_code=403, detail="This class is not assigned to you today.")
    section = db.query(Section).filter(Section.id == entry.section_id).first()
    subject = db.query(Subject).filter(Subject.id == entry.subject_id).first()
    if section is None or subject is None or entry.start_slot not in SLOTS:
        raise HTTPException(status_code=409, detail="The scheduled class has incomplete academic data.")
    session = AttendanceSession(
        id=_id("att"),
        faculty_id=faculty.id,
        section_id=section.id,
        subject_id=subject.id,
        timetable_entry_id=entry.id,
        session_date=body.session_date,
        start_time=SLOTS[entry.start_slot][0],
        status="OPEN",
        created_at=get_now(),
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Attendance has already been started for this class today.") from error
    return AttendanceSessionResponse(
        id=session.id,
        timetable_entry_id=entry.id,
        session_date=session.session_date,
        start_time=session.start_time,
        status=session.status,
        section_code=section.code,
        subject_code=subject.code,
        subject_name=subject.name,
        records_entered=0,
    )


@router.get("/faculty/attendance/{session_id}", response_model=AttendanceSessionDetailResponse)
def get_attendance_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == session_id,
        AttendanceSession.faculty_id == faculty.id,
    ).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Attendance session not found.")
    section = db.query(Section).filter(Section.id == session.section_id).first()
    subject = db.query(Subject).filter(Subject.id == session.subject_id).first()
    if section is None or subject is None:
        raise HTTPException(status_code=409, detail="Attendance session academic data is incomplete.")
    students = db.query(Student).filter(
        Student.section_id == section.id
    ).order_by(Student.usn, Student.id).all()
    records = {
        record.student_id: record.status
        for record in db.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == session.id
        ).all()
    }
    student_rows = []
    for student in students:
        student_user = db.query(User).filter(User.id == student.user_id).first()
        student_rows.append(AttendanceStudentResponse(
            student_id=student.id,
            usn=student.usn,
            name=(student_user.display_name if student_user else None) or student.usn or "Student",
            status=records.get(student.id),
        ))
    return AttendanceSessionDetailResponse(
        id=session.id,
        subject_id=subject.id,
        subject_code=subject.code,
        subject_name=subject.name,
        section_id=section.id,
        section_code=section.code,
        session_date=session.session_date,
        status=session.status,
        records=student_rows,
    )


@router.put("/faculty/attendance/{session_id}/records")
def save_attendance_records(
    session_id: str,
    body: AttendanceMarkRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == session_id,
        AttendanceSession.faculty_id == faculty.id,
    ).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Attendance session not found.")
    _require_academic_assignment(db, faculty, session.subject_id, session.section_id)
    roster = db.query(Student).filter(Student.section_id == session.section_id).all()
    roster_ids = {student.id for student in roster}
    submitted_ids = {record.student_id for record in body.records}
    if not roster_ids:
        raise HTTPException(status_code=422, detail="No students are assigned to this section.")
    if submitted_ids != roster_ids:
        raise HTTPException(
            status_code=422,
            detail="Submit exactly one attendance status for every student in this section.",
        )
    now = get_now()
    for submitted in body.records:
        record = db.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == session.id,
            AttendanceRecord.student_id == submitted.student_id,
        ).first()
        if record is None:
            record = AttendanceRecord(
                id=_id("attrec"),
                session_id=session.id,
                student_id=submitted.student_id,
                status=submitted.status,
                marked_at=now,
                marked_by=user.id,
            )
            db.add(record)
        else:
            record.status = submitted.status
            record.marked_at = now
            record.marked_by = user.id
    session.status = "COMPLETED"
    log_audit(
        db,
        user.id,
        "SAVE_ATTENDANCE",
        "AttendanceSession",
        session.id,
        {"students_marked": len(body.records)},
        role=user.role,
    )
    db.commit()
    return {
        "session_id": session.id,
        "status": session.status,
        "records_entered": len(body.records),
        "present": sum(record.status == "PRESENT" for record in body.records),
        "absent": sum(record.status == "ABSENT" for record in body.records),
    }


@router.get("/faculty/academic-assignments")
def list_faculty_academic_assignments(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    entries = _assignments(db, faculty.id)
    result = {}
    for entry in entries:
        if not entry.subject_id or not entry.section_id:
            continue
        subject = db.query(Subject).filter(Subject.id == entry.subject_id).first()
        section = db.query(Section).filter(Section.id == entry.section_id).first()
        if subject is None or section is None:
            continue
        result[(subject.id, section.id)] = {
            "subject_id": subject.id,
            "subject_code": subject.code,
            "subject_name": subject.name,
            "section_id": section.id,
            "section_code": section.code,
            "is_synthetic": bool(faculty.is_synthetic or subject.is_synthetic or section.is_synthetic),
        }
    return sorted(result.values(), key=lambda row: (row["subject_code"], row["section_code"]))


@router.get("/faculty/announcements")
def list_faculty_announcements(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    section_ids = {
        entry.section_id
        for entry in _assignments(db, faculty.id)
        if entry.section_id
    }
    announcements = db.query(Announcement).order_by(
        Announcement.published_at.desc()
    ).all()
    return [
        {
            "id": item.id,
            "title": item.title,
            "body": item.body,
            "published_at": item.published_at.isoformat(),
        }
        for item in announcements
        if announcement_visible(item, "FACULTY", None)
        or any(announcement_visible(item, "FACULTY", section_id) for section_id in section_ids)
    ]


@router.get("/faculty/academic-content")
def list_faculty_academic_content(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    entries = _assignments(db, faculty.id)
    pairs = {
        (entry.subject_id, entry.section_id)
        for entry in entries
        if entry.subject_id and entry.section_id
    }
    subject_ids = {subject_id for subject_id, _ in pairs}
    pair_filters = [
        and_(Assessment.subject_id == subject_id, Assessment.section_id == section_id)
        for subject_id, section_id in pairs
    ]
    assessments = db.query(Assessment).filter(or_(*pair_filters)).order_by(
        Assessment.date
    ).all() if pair_filters else []
    resources = db.query(AcademicResource).filter(or_(*[
        and_(AcademicResource.subject_id == subject_id, AcademicResource.section_id == section_id)
        for subject_id, section_id in pairs
    ])).order_by(AcademicResource.created_at.desc()).all() if pairs else []
    modules = db.query(SyllabusModule).filter(
        SyllabusModule.subject_id.in_(subject_ids)
    ).order_by(SyllabusModule.subject_id, SyllabusModule.sequence).all() if subject_ids else []
    return {
        "assessments": [
            {
                "id": item.id,
                "subject_id": item.subject_id,
                "section_id": item.section_id,
                "title": item.title,
                "kind": item.kind,
                "date": item.date.isoformat(),
                "maximum_marks": float(item.maximum_marks) if item.maximum_marks is not None else None,
                "status": item.status,
            }
            for item in assessments
        ],
        "resources": [
            {
                "id": item.id,
                "subject_id": item.subject_id,
                "section_id": item.section_id,
                "title": item.title,
                "resource_type": item.resource_type,
                "status": item.status,
            }
            for item in resources
        ],
        "syllabus": [
            {
                "id": item.id,
                "subject_id": item.subject_id,
                "module_number": item.module_number,
                "title": item.title,
                "status": item.status,
            }
            for item in modules
        ],
    }


@router.get("/faculty/sections/{section_id}/students")
def list_faculty_section_students(
    section_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    if not db.query(TimetableEntry.id).filter(
        TimetableEntry.faculty_id == faculty.id,
        TimetableEntry.section_id == section_id,
    ).first():
        raise HTTPException(status_code=403, detail="This section is not assigned to you.")
    students = db.query(Student).filter(
        Student.section_id == section_id
    ).order_by(Student.usn, Student.id).all()
    return [
        {
            "student_id": student.id,
            "usn": student.usn,
            "name": (
                (db.query(User).filter(User.id == student.user_id).first().display_name or student.usn)
                if student.user_id and db.query(User).filter(User.id == student.user_id).first()
                else student.usn or "Student"
            ),
        }
        for student in students
    ]


@router.post("/faculty/syllabus", status_code=status.HTTP_201_CREATED)
def create_syllabus_module(
    body: SyllabusModuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    _require_academic_assignment(db, faculty, body.subject_id)
    subject = db.query(Subject).filter(Subject.id == body.subject_id).first()
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    synthetic = bool(faculty.is_synthetic or subject.is_synthetic)
    now = get_now()
    module = SyllabusModule(
        id=_id("syllabus"),
        subject_id=subject.id,
        module_number=body.module_number,
        title=body.title,
        description=body.description,
        sequence=body.sequence,
        status=body.status,
        created_by=user.id,
        created_at=now,
        updated_at=now,
        is_synthetic=synthetic,
        provenance="SYNTHETIC" if synthetic else "PROVIDED",
    )
    db.add(module)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="A syllabus module with that number already exists for this subject.") from error
    return {"id": module.id, "status": module.status}


@router.post("/faculty/syllabus/{module_id}/publish")
def publish_syllabus_module(
    module_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    module = db.query(SyllabusModule).filter(SyllabusModule.id == module_id).first()
    if module is None:
        raise HTTPException(status_code=404, detail="Syllabus module not found.")
    _require_academic_assignment(db, faculty, module.subject_id)
    module.status = "PUBLISHED"
    module.updated_at = get_now()
    log_audit(db, user.id, "PUBLISH_SYLLABUS_MODULE", "SyllabusModule", module.id, {}, role=user.role)
    db.commit()
    return {"id": module.id, "status": module.status}


@router.post("/faculty/resources", status_code=status.HTTP_201_CREATED)
def create_academic_resource(
    body: AcademicResourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    _require_academic_assignment(db, faculty, body.subject_id, body.section_id)
    subject = db.query(Subject).filter(Subject.id == body.subject_id).first()
    section = db.query(Section).filter(Section.id == body.section_id).first()
    if subject is None or section is None:
        raise HTTPException(status_code=404, detail="Subject or section not found.")
    synthetic = bool(faculty.is_synthetic or subject.is_synthetic or section.is_synthetic)
    now = get_now()
    resource = AcademicResource(
        id=_id("resource"),
        subject_id=subject.id,
        section_id=section.id,
        title=body.title,
        description=body.description,
        resource_type=body.resource_type,
        url=body.url,
        status=body.status,
        created_by=user.id,
        created_at=now,
        updated_at=now,
        is_synthetic=synthetic,
        provenance="SYNTHETIC" if synthetic else "PROVIDED",
    )
    db.add(resource)
    db.commit()
    return {"id": resource.id, "status": resource.status}


@router.post("/faculty/resources/{resource_id}/publish")
def publish_academic_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    resource = db.query(AcademicResource).filter(AcademicResource.id == resource_id).first()
    if resource is None:
        raise HTTPException(status_code=404, detail="Academic resource not found.")
    _require_academic_assignment(db, faculty, resource.subject_id, resource.section_id)
    resource.status = "PUBLISHED"
    resource.updated_at = get_now()
    log_audit(db, user.id, "PUBLISH_ACADEMIC_RESOURCE", "AcademicResource", resource.id, {}, role=user.role)
    db.commit()
    return {"id": resource.id, "status": resource.status}


@router.post("/faculty/assessments", status_code=status.HTTP_201_CREATED)
def create_academic_assessment(
    body: AssessmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    _require_academic_assignment(db, faculty, body.subject_id, body.section_id)
    subject = db.query(Subject).filter(Subject.id == body.subject_id).first()
    section = db.query(Section).filter(Section.id == body.section_id).first()
    if subject is None or section is None:
        raise HTTPException(status_code=404, detail="Subject or section not found.")
    synthetic = bool(faculty.is_synthetic or subject.is_synthetic or section.is_synthetic)
    now = get_now()
    assessment = Assessment(
        id=_id("assessment"),
        subject_id=subject.id,
        section_id=section.id,
        title=body.title,
        date=body.date,
        kind=body.kind,
        description=body.description,
        maximum_marks=body.maximum_marks,
        created_by=user.id,
        status=body.status,
        created_at=now,
        updated_at=now,
        is_synthetic=synthetic,
        provenance="SYNTHETIC" if synthetic else "PROVIDED",
    )
    db.add(assessment)
    db.commit()
    return {"id": assessment.id, "status": assessment.status}


@router.put("/faculty/assessments/{assessment_id}/marks")
def save_academic_marks(
    assessment_id: str,
    body: MarkEntryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None or assessment.subject_id is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    _require_academic_assignment(db, faculty, assessment.subject_id, assessment.section_id)
    if assessment.maximum_marks is None:
        raise HTTPException(status_code=409, detail="Set maximum marks before entering student marks.")
    students = db.query(Student).filter(
        Student.section_id == assessment.section_id,
        Student.id.in_([record.student_id for record in body.records]),
    ).all()
    if len(students) != len(body.records):
        raise HTTPException(status_code=422, detail="Marks can be entered only for students in this assessment section.")
    now = get_now()
    for submitted in body.records:
        if submitted.marks > assessment.maximum_marks:
            raise HTTPException(status_code=422, detail="A student's marks cannot exceed the assessment maximum.")
        mark = db.query(AcademicMark).filter(
            AcademicMark.assessment_id == assessment.id,
            AcademicMark.student_id == submitted.student_id,
        ).first()
        if mark is None:
            mark = AcademicMark(
                id=_id("mark"),
                assessment_id=assessment.id,
                student_id=submitted.student_id,
                marks=submitted.marks,
                updated_by=user.id,
                updated_at=now,
            )
            db.add(mark)
        else:
            mark.marks = submitted.marks
            mark.updated_by = user.id
            mark.updated_at = now
    log_audit(
        db,
        user.id,
        "SAVE_ASSESSMENT_MARKS",
        "Assessment",
        assessment.id,
        {"students_marked": len(body.records)},
        role=user.role,
    )
    db.commit()
    return {"assessment_id": assessment.id, "records_saved": len(body.records)}


@router.get("/faculty/assessments/{assessment_id}/marks")
def get_academic_marks(
    assessment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None or assessment.subject_id is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    _require_academic_assignment(db, faculty, assessment.subject_id, assessment.section_id)
    marks_by_student = {
        mark.student_id: float(mark.marks)
        for mark in db.query(AcademicMark).filter(
            AcademicMark.assessment_id == assessment.id
        ).all()
    }
    students = db.query(Student).filter(
        Student.section_id == assessment.section_id
    ).order_by(Student.usn, Student.id).all()
    return {
        "assessment_id": assessment.id,
        "maximum_marks": float(assessment.maximum_marks) if assessment.maximum_marks is not None else None,
        "records": [
            {
                "student_id": student.id,
                "usn": student.usn,
                "name": (
                    student_user.display_name if (student_user := (
                        db.query(User).filter(User.id == student.user_id).first()
                    )) else student.usn
                ) or "Student",
                "marks": marks_by_student.get(student.id),
            }
            for student in students
        ],
    }


@router.post("/faculty/assessments/{assessment_id}/publish")
def publish_academic_assessment(
    assessment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None or assessment.subject_id is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    _require_academic_assignment(db, faculty, assessment.subject_id, assessment.section_id)
    if assessment.maximum_marks is None or assessment.maximum_marks <= 0:
        raise HTTPException(status_code=409, detail="Set a valid maximum mark before publishing this assessment.")
    assessment.status = "PUBLISHED"
    assessment.updated_at = get_now()
    log_audit(
        db,
        user.id,
        "PUBLISH_ASSESSMENT",
        "Assessment",
        assessment.id,
        {},
        role=user.role,
    )
    db.commit()
    return {"assessment_id": assessment.id, "status": assessment.status}


@router.get("/faculty/classroom-requests", response_model=list[ClassroomRequestResponse])
def list_faculty_classroom_requests(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    requests = db.query(ClassroomRequest).filter(
        ClassroomRequest.faculty_id == faculty.id
    ).order_by(ClassroomRequest.created_at.desc()).all()
    return [_request_response(db, request) for request in requests]


@router.get("/faculty/classroom-options", response_model=FacultyClassroomOptionsResponse)
def get_faculty_classroom_options(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["FACULTY"])),
):
    floors = db.query(Floor).order_by(Floor.level, Floor.name).all()
    rooms = db.query(Room).filter(
        Room.status == "ACTIVE",
        Room.allocatable_for_classes.is_(True),
    ).order_by(Room.code).all()
    return FacultyClassroomOptionsResponse(
        floors=[
            {"id": floor.id, "name": floor.name, "level": floor.level}
            for floor in floors
        ],
        rooms=[
            {
                "id": room.id,
                "code": room.code,
                "floor_id": room.floor_id,
                "capacity": room.capacity,
            }
            for room in rooms
        ],
    )


@router.get("/faculty/extra-classes", response_model=list[ClassroomRequestResponse])
def list_faculty_extra_classes(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    today = get_now().date()
    approved = db.query(ClassroomRequest).filter(
        ClassroomRequest.faculty_id == faculty.id,
        ClassroomRequest.status == "APPROVED",
        ClassroomRequest.requested_date >= today,
    ).order_by(ClassroomRequest.requested_date, ClassroomRequest.start_time).all()
    return [_request_response(db, request) for request in approved]


@router.post(
    "/faculty/classroom-requests",
    response_model=ClassroomRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_faculty_classroom_request(
    body: ClassroomRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    _validate_request_assignment(db, faculty, body)
    now = get_now()
    request = ClassroomRequest(
        id=_id("cr"),
        faculty_id=faculty.id,
        subject_id=body.subject_id,
        section_id=body.section_id,
        requested_date=body.requested_date,
        start_time=body.start_time,
        end_time=body.end_time,
        expected_strength=body.expected_strength,
        preferred_floor_id=body.preferred_floor_id,
        preferred_room_id=body.preferred_room_id,
        reason=body.reason,
        status="PENDING",
        created_at=now,
        updated_at=now,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return _request_response(db, request)


@router.post("/faculty/classroom-requests/{request_id}/cancel")
def cancel_faculty_classroom_request(
    request_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = _get_faculty(db, user)
    request = db.query(ClassroomRequest).filter(
        ClassroomRequest.id == request_id,
        ClassroomRequest.faculty_id == faculty.id,
    ).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Classroom request not found.")
    if request.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending requests can be cancelled.")
    request.status = "CANCELLED"
    request.updated_at = get_now()
    db.commit()
    return {"ok": True, "status": request.status}


@router.get("/management/classroom-requests", response_model=list[ClassroomRequestResponse])
def list_management_classroom_requests(
    request_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    query = db.query(ClassroomRequest)
    if request_status:
        request_status = request_status.upper()
        if request_status not in {"PENDING", "APPROVED", "REJECTED", "CANCELLED"}:
            raise HTTPException(status_code=422, detail="Unknown classroom request status.")
        query = query.filter(ClassroomRequest.status == request_status)
    requests = query.order_by(ClassroomRequest.created_at.desc()).all()
    return [_request_response(db, request) for request in requests]


@router.get("/management/classroom-requests/rooms")
def list_classroom_request_rooms(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    rooms = db.query(Room).order_by(Room.code).all()
    return [
        {
            "id": room.id,
            "code": room.code,
            "display_name": room.display_name,
            "floor_id": room.floor_id,
            "capacity": room.capacity,
            "resource_type": room.resource_type,
            "lab_kind": room.lab_kind,
            "facilities": room.facilities or [],
            "status": room.status,
            "allocatable_for_classes": room.allocatable_for_classes,
        }
        for room in rooms
    ]


@router.post("/management/classroom-requests/{request_id}/approve")
def approve_classroom_request(
    request_id: str,
    body: ClassroomRequestDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    request = db.query(ClassroomRequest).filter(
        ClassroomRequest.id == request_id
    ).with_for_update().first()
    if request is None:
        raise HTTPException(status_code=404, detail="Classroom request not found.")
    if request.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending requests can be approved.")
    room = db.query(Room).filter(Room.id == body.room_id).first()
    if room is None:
        raise HTTPException(status_code=422, detail="Select an existing classroom.")
    assignments = db.query(TimetableEntry).filter(
        TimetableEntry.faculty_id == request.faculty_id,
        TimetableEntry.section_id == request.section_id,
        TimetableEntry.subject_id == request.subject_id,
    ).all()
    if not assignments:
        raise HTTPException(status_code=409, detail="The faculty teaching assignment no longer exists.")
    _validate_room_for_request(db, request, room, assignments)

    request.status = "APPROVED"
    request.approved_room_id = room.id
    request.decided_by = user.id
    request.decision_reason = None
    request.updated_at = get_now()
    section = db.query(Section).filter(Section.id == request.section_id).first()
    now = get_now()
    db.add(Notification(
        id=_id("notif"),
        audience_type="FACULTY",
        audience_id=request.faculty_id,
        type="CLASSROOM_REQUEST",
        title="Classroom request approved",
        body=f"{room.code} is approved for {request.requested_date.isoformat()} from {request.start_time.strftime('%H:%M')} to {request.end_time.strftime('%H:%M')}.",
        payload={"request_id": request.id, "room_id": room.id},
        created_at=now,
    ))
    if section:
        subject = db.query(Subject).filter(Subject.id == request.subject_id).first()
        db.add(Notification(
            id=_id("notif"),
            audience_type="SECTION",
            audience_id=section.id,
            type="CLASSROOM_REQUEST",
            title="Extra class scheduled",
            body=f"{subject.code if subject else 'Extra class'} is scheduled in {room.code} on {request.requested_date.isoformat()} from {request.start_time.strftime('%H:%M')} to {request.end_time.strftime('%H:%M')}.",
            payload={"request_id": request.id, "room_id": room.id},
            created_at=now,
        ))
    log_audit(
        db,
        user.id,
        "APPROVE_CLASSROOM_REQUEST",
        "ClassroomRequest",
        request.id,
        {"room_id": room.id, "requested_date": request.requested_date.isoformat()},
        role=user.role,
    )
    db.commit()
    return _request_response(db, request)


@router.post("/management/classroom-requests/{request_id}/reject")
def reject_classroom_request(
    request_id: str,
    body: ClassroomRequestRejection,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    request = db.query(ClassroomRequest).filter(
        ClassroomRequest.id == request_id
    ).with_for_update().first()
    if request is None:
        raise HTTPException(status_code=404, detail="Classroom request not found.")
    if request.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending requests can be rejected.")
    request.status = "REJECTED"
    request.decided_by = user.id
    request.decision_reason = body.reason
    request.updated_at = get_now()
    db.add(Notification(
        id=_id("notif"),
        audience_type="FACULTY",
        audience_id=request.faculty_id,
        type="CLASSROOM_REQUEST",
        title="Classroom request rejected",
        body=body.reason,
        payload={"request_id": request.id, "status": "REJECTED"},
        created_at=get_now(),
    ))
    log_audit(
        db,
        user.id,
        "REJECT_CLASSROOM_REQUEST",
        "ClassroomRequest",
        request.id,
        {"reason": body.reason},
        role=user.role,
    )
    db.commit()
    return _request_response(db, request)
