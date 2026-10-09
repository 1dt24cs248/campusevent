"""Timetable and state API router."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.deps import get_db, get_current_user, require_roles
from app.models.identity import User
from app.models.schedule import TimetableEntry, SessionOverride
from app.models.faculty_work import ClassroomRequest
from app.models.academic import Section, Subject, Faculty, Student
from app.models.campus import Room, Floor
from app.engine.slots import PERIOD_SLOTS, SLOTS
from app.schemas.scenario import TimetableEntryResponse, StateOverviewResponse

router = APIRouter()


@router.get("/timetable/me", response_model=List[TimetableEntryResponse])
def get_my_timetable(
    date_str: Optional[str] = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current user's timetable (resolves overrides for a specific date)."""
    # Find which section this user belongs to
    section_id = None
    faculty_id = None
    if user.role == "STUDENT":
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student:
            section_id = student.section_id
    elif user.role == "FACULTY":
        faculty = db.query(Faculty).filter(Faculty.user_id == user.id).first()
        if faculty:
            faculty_id = faculty.id

    if section_id:
        entries = db.query(TimetableEntry).filter(TimetableEntry.section_id == section_id).all()
    elif faculty_id:
        entries = db.query(TimetableEntry).filter(TimetableEntry.faculty_id == faculty_id).all()
    else:
        entries = []

    result = _enrich_entries(entries, db, date_str)
    if date_str and (section_id or faculty_id):
        requested_date = date.fromisoformat(date_str)
        result.extend(_approved_request_entries(
            db,
            requested_date,
            section_id=section_id,
            faculty_id=faculty_id,
        ))
    return result


@router.get("/timetable/section/{section_id}", response_model=List[TimetableEntryResponse])
def get_section_timetable(
    section_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get timetable for a specific section."""
    if user.role == "STUDENT":
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student is None or student.section_id != section_id:
            raise HTTPException(status_code=403, detail="You can only view your own section timetable.")
    elif user.role != "MANAGEMENT":
        raise HTTPException(status_code=403, detail="Not enough permissions.")

    entries = db.query(TimetableEntry).filter(TimetableEntry.section_id == section_id).all()
    return _enrich_entries(entries, db)


@router.get("/timetable/management/section/{section_id}", response_model=List[TimetableEntryResponse])
def get_section_timetable_mgmt(
    section_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Get timetable for a specific section (Management access for What-If simulator)."""
    entries = db.query(TimetableEntry).filter(TimetableEntry.section_id == section_id).all()
    return _enrich_entries(entries, db)


@router.get("/state/overview", response_model=StateOverviewResponse)
def get_state_overview(db: Session = Depends(get_db), user: User = Depends(require_roles(["MANAGEMENT"]))):
    """Get current campus operational snapshot (Management only)."""
    rooms = db.query(Room).all()
    allocatable = [r for r in rooms if r.allocatable_for_classes]
    entries = db.query(TimetableEntry).all()
    sections = db.query(Section).all()
    faculty = db.query(Faculty).all()

    sections_map = {s.id: s for s in sections}
    rooms_map = {r.id: r for r in rooms}

    allocated = 0
    at_risk = 0
    floating = 0
    cap_violations = 0

    for e in entries:
        sec = sections_map.get(e.section_id)
        room = rooms_map.get(e.base_room_id)
        if not e.base_room_id:
            floating += 1
        elif room and sec and room.capacity and room.capacity < sec.strength:
            cap_violations += 1
            at_risk += 1
        else:
            allocated += 1

    return StateOverviewResponse(
        total_rooms=len(rooms),
        allocatable_rooms=len(allocatable),
        total_entries=len(entries),
        allocated=allocated,
        at_risk=at_risk,
        floating=floating,
        capacity_violations=cap_violations,
        total_sections=len(sections),
        total_faculty=len(faculty),
    )


def _enrich_entries(entries, db: Session, date_str: str = None) -> List[dict]:
    """Enrich timetable entries with section/subject/room names and overrides."""
    sections = {s.id: s for s in db.query(Section).all()}
    subjects = {s.id: s for s in db.query(Subject).all()}
    faculties = {f.id: f for f in db.query(Faculty).all()}
    rooms = {r.id: r for r in db.query(Room).all()}

    # Load active overrides for the date if specified
    overrides = {}
    if date_str:
        try:
            requested_date = date.fromisoformat(date_str)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Date must use YYYY-MM-DD format.") from error
        day_start = datetime.combine(requested_date, time.min)
        next_day = day_start + timedelta(days=1)
        ovs = db.query(SessionOverride).filter(
            SessionOverride.date >= day_start,
            SessionOverride.date < next_day,
            SessionOverride.active.is_(True),
        ).all()
        for ov in ovs:
            overrides[ov.entry_id] = ov

    result = []
    for e in entries:
        sec = sections.get(e.section_id)
        subj = subjects.get(e.subject_id)
        fac = faculties.get(e.faculty_id)
        base_room = rooms.get(e.base_room_id)

        override = overrides.get(e.id)
        eff_room_id = override.room_id if override else e.base_room_id
        eff_room = rooms.get(eff_room_id)
        effective_start_slot = (
            override.start_slot_override
            if override and override.start_slot_override
            else e.start_slot
        )
        start_time, end_time = _entry_times(effective_start_slot, e.duration_slots)

        result.append(TimetableEntryResponse(
            id=e.id,
            section_id=e.section_id,
            section_code=sec.code if sec else None,
            section_name=sec.name if sec else None,
            subject_id=e.subject_id,
            subject_code=subj.code if subj else None,
            subject_name=subj.name if subj else None,
            faculty_id=e.faculty_id,
            faculty_name=fac.name if fac else None,
            weekday=e.weekday,
            start_slot=e.start_slot,
            effective_start_slot=effective_start_slot,
            start_time=start_time,
            end_time=end_time,
            duration_slots=e.duration_slots,
            kind=e.kind,
            required_room_type=e.required_room_type,
            base_room_id=e.base_room_id,
            base_room_code=base_room.code if base_room else None,
            effective_room_id=eff_room_id,
            effective_room_code=eff_room.code if eff_room else None,
            room_changed=override is not None,
            change_reason=override.reason if override else None,
            provenance=e.provenance,
            is_synthetic=bool(
                (sec and sec.is_synthetic)
                or (subj and subj.is_synthetic)
                or (
                    e.provenance
                    and (
                        "demo" in e.provenance.casefold()
                        or "synthetic" in e.provenance.casefold()
                    )
                )
            ),
        ))
    return result


def _approved_request_entries(
    db: Session,
    requested_date: date,
    *,
    section_id: str | None = None,
    faculty_id: str | None = None,
) -> List[dict]:
    query = db.query(ClassroomRequest).filter(
        ClassroomRequest.status == "APPROVED",
        ClassroomRequest.requested_date == requested_date,
    )
    if section_id:
        query = query.filter(ClassroomRequest.section_id == section_id)
    if faculty_id:
        query = query.filter(ClassroomRequest.faculty_id == faculty_id)
    requests = query.all()
    sections = {
        section.id: section
        for section in db.query(Section).filter(
            Section.id.in_({request.section_id for request in requests})
        ).all()
    } if requests else {}
    subjects = {
        subject.id: subject
        for subject in db.query(Subject).filter(
            Subject.id.in_({request.subject_id for request in requests})
        ).all()
    } if requests else {}
    faculties = {
        faculty.id: faculty
        for faculty in db.query(Faculty).filter(
            Faculty.id.in_({request.faculty_id for request in requests})
        ).all()
    } if requests else {}
    rooms = {
        room.id: room
        for room in db.query(Room).filter(
            Room.id.in_({request.approved_room_id for request in requests if request.approved_room_id})
        ).all()
    } if requests else {}

    result = []
    for request in requests:
        section = sections.get(request.section_id)
        subject = subjects.get(request.subject_id)
        faculty = faculties.get(request.faculty_id)
        room = rooms.get(request.approved_room_id)
        if not section or not subject:
            continue
        result.append(TimetableEntryResponse(
            id=request.id,
            section_id=section.id,
            section_code=section.code,
            section_name=section.name,
            subject_id=subject.id,
            subject_code=subject.code,
            subject_name=subject.name,
            faculty_id=faculty.id if faculty else None,
            faculty_name=faculty.name if faculty else None,
            weekday=request.requested_date.weekday(),
            start_slot=request.start_time.strftime("%H:%M"),
            effective_start_slot=request.start_time.strftime("%H:%M"),
            start_time=request.start_time.strftime("%H:%M"),
            end_time=request.end_time.strftime("%H:%M"),
            duration_slots=1,
            kind="EXTRA_CLASS",
            base_room_id=None,
            base_room_code=None,
            effective_room_id=room.id if room else None,
            effective_room_code=room.code if room else None,
            room_changed=False,
            is_extra_class=True,
            provenance="FACULTY_APPROVED_CLASSROOM_REQUEST",
            is_synthetic=bool(section.is_synthetic or subject.is_synthetic),
        ).model_dump())
    return result


def _entry_times(start_slot: str, duration_slots: int) -> tuple[Optional[str], Optional[str]]:
    start = SLOTS.get(start_slot)
    slot_index = PERIOD_SLOTS.index(start_slot) if start_slot in SLOTS else -1
    end_index = slot_index + duration_slots - 1
    if start is None or duration_slots < 1 or end_index >= len(PERIOD_SLOTS):
        return None, None
    end = SLOTS[PERIOD_SLOTS[end_index]][1]
    return start[0].strftime("%H:%M"), end.strftime("%H:%M")
