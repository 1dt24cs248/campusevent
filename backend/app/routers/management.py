"""Management-only institutional identity and directory APIs."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.clock import get_now
from app.deps import get_db, require_roles
from app.models.academic import Department, Faculty, Section, Student, Subject
from app.models.identity import AuditLog, User
from app.models.schedule import TimetableEntry
from app.models.campus import Room
from app.models.faculty_work import AttendanceSession, ClassroomRequest
from app.models.operations import Assessment, Event
from app.security import get_password_hash
from app.models.operations import Announcement
from app.schemas.academic import AcademicAnnouncementCreate
from app.schemas.management import (
    DepartmentCreate,
    DepartmentUpdate,
    SectionCreate,
    SectionUpdate,
    SubjectCreate,
    SubjectUpdate,
)
from app.schemas.identity import (
    FacultyCreate,
    FacultyResponse,
    FacultyUpdate,
    PasswordReset,
    StudentCreate,
    StudentResponse,
    StudentUpdate,
)

router = APIRouter(prefix="/management")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _ensure_unique_name(
    db: Session,
    model: type[Department] | type[Section] | type[Subject],
    field: str,
    value: str,
    label: str,
    exclude_id: str | None = None,
) -> None:
    column = getattr(model, field)
    query = db.query(model).filter(func.lower(column) == value.lower())
    if exclude_id:
        query = query.filter(model.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail=f"That {label} is already in use.")


@router.get("/overview")
def get_management_overview(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    today = get_now().date()
    current_weekday = today.weekday()
    student_counts = db.query(
        func.count(Student.id),
        func.sum(func.cast(User.active, Integer)),
    ).join(User, User.id == Student.user_id).first()
    faculty_counts = db.query(
        func.count(Faculty.id),
        func.sum(func.cast(User.active, Integer)),
    ).join(User, User.id == Faculty.user_id).first()
    return {
        "students": {
            "total": int(student_counts[0] or 0),
            "active": int(student_counts[1] or 0),
        },
        "faculty": {
            "total": int(faculty_counts[0] or 0),
            "active": int(faculty_counts[1] or 0),
        },
        "departments": db.query(func.count(Department.id)).scalar() or 0,
        "sections": db.query(func.count(Section.id)).scalar() or 0,
        "subjects": db.query(func.count(Subject.id)).scalar() or 0,
        "rooms": db.query(func.count(Room.id)).scalar() or 0,
        "today_classes": db.query(func.count(TimetableEntry.id)).filter(
            TimetableEntry.weekday == current_weekday
        ).scalar() or 0,
        "pending_classroom_requests": db.query(func.count(ClassroomRequest.id)).filter(
            ClassroomRequest.status == "PENDING"
        ).scalar() or 0,
        "pending_event_proposals": db.query(func.count(Event.id)).filter(
            func.upper(Event.status).in_(("PENDING", "PROPOSED"))
        ).scalar() or 0,
        "upcoming_assessments": db.query(func.count(Assessment.id)).filter(
            Assessment.status == "PUBLISHED",
            Assessment.date >= get_now(),
        ).scalar() or 0,
        "attendance_sessions_today": db.query(func.count(AttendanceSession.id)).filter(
            AttendanceSession.session_date == today
        ).scalar() or 0,
        "published_announcements": db.query(func.count(Announcement.id)).scalar() or 0,
    }


@router.get("/audit-log")
def list_management_audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    query = db.query(AuditLog).order_by(AuditLog.ts.desc(), AuditLog.id.desc())
    total = query.count()
    entries = query.offset(offset).limit(limit).all()
    actors = {
        user.id: user
        for user in db.query(User).filter(
            User.id.in_({entry.user_id for entry in entries})
        ).all()
    } if entries else {}
    return {
        "items": [
            {
                "id": entry.id,
                "actor_id": entry.user_id,
                "actor": actors[entry.user_id].display_name or actors[entry.user_id].email
                if entry.user_id in actors else "Unknown account",
                "role": entry.role,
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "summary": entry.details,
                "timestamp": entry.ts.isoformat(),
            }
            for entry in entries
        ],
        "total": total,
    }


@router.get("/academics")
def get_academic_management_overview(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    departments = db.query(Department).order_by(Department.name).all()
    departments_by_id = {item.id: item for item in departments}
    sections = db.query(Section).order_by(Section.code).all()
    subjects = db.query(Subject).order_by(Subject.code).all()
    students = db.query(Student).order_by(Student.usn, Student.id).all()
    users = {
        item.id: item
        for item in db.query(User).filter(
            User.id.in_([student.user_id for student in students if student.user_id])
        ).all()
    } if any(student.user_id for student in students) else {}
    audit_rows = db.query(AuditLog).filter(
        AuditLog.entity_type.in_(
            ("Student", "Faculty", "Department", "Section", "Subject", "Announcement")
        )
    ).order_by(AuditLog.ts.desc()).limit(20).all()
    activity_users = {
        item.id: item
        for item in db.query(User).filter(
            User.id.in_({entry.user_id for entry in audit_rows})
        ).all()
    } if audit_rows else {}
    faculty_by_id = {
        faculty.id: faculty
        for faculty in db.query(Faculty).all()
    }
    assignments = db.query(TimetableEntry).filter(
        TimetableEntry.faculty_id.is_not(None),
        TimetableEntry.subject_id.is_not(None),
        TimetableEntry.section_id.is_not(None),
    ).all()
    assignment_rows = {}
    for entry in assignments:
        key = (entry.faculty_id, entry.subject_id, entry.section_id)
        if key in assignment_rows:
            continue
        faculty = faculty_by_id.get(entry.faculty_id)
        subject = db.query(Subject).filter(Subject.id == entry.subject_id).first()
        section = db.query(Section).filter(Section.id == entry.section_id).first()
        if faculty and subject and section:
            assignment_rows[key] = {
                "faculty_id": faculty.id,
                "faculty_name": faculty.name,
                "subject_id": subject.id,
                "subject_code": subject.code,
                "subject_name": subject.name,
                "section_id": section.id,
                "section_code": section.code,
            }
    announcements = db.query(Announcement).order_by(
        Announcement.published_at.desc()
    ).all()
    announcement_users = {
        account.id: account
        for account in db.query(User).filter(
            User.id.in_({item.created_by for item in announcements if item.created_by})
        ).all()
    } if any(item.created_by for item in announcements) else {}
    students_by_section = {}
    for student in students:
        students_by_section[student.section_id] = students_by_section.get(student.section_id, 0) + 1
    return {
        "departments": [
            {
                "id": item.id,
                "name": item.name,
                "section_count": sum(section.department_id == item.id for section in sections),
                "subject_count": sum(subject.department_id == item.id for subject in subjects),
            }
            for item in departments
        ],
        "sections": [
            {
                "id": section.id,
                "code": section.code,
                "name": section.name,
                "department_id": section.department_id,
                "department": departments_by_id[section.department_id].name
                if section.department_id in departments_by_id else None,
                "year": section.year,
                "student_count": students_by_section.get(section.id, 0),
                "students": [
                    {
                        "student_id": student.id,
                        "usn": student.usn,
                        "name": users[student.user_id].display_name
                        if student.user_id in users else None,
                    }
                    for student in students if student.section_id == section.id
                ],
                "teaching_assignments": [
                    assignment for assignment in assignment_rows.values()
                    if assignment["section_id"] == section.id
                ],
                "is_synthetic": bool(section.is_synthetic),
                "provenance": section.provenance,
            }
            for section in sections
        ],
        "subjects": [
            {
                "id": subject.id,
                "code": subject.code,
                "name": subject.name,
                "department_id": subject.department_id,
                "credits": subject.credits,
                "description": subject.description,
                "kind": subject.kind,
                "faculty": sorted({
                    assignment["faculty_name"]
                    for assignment in assignment_rows.values()
                    if assignment["subject_id"] == subject.id and assignment["faculty_name"]
                }),
                "sections": sorted({
                    assignment["section_code"]
                    for assignment in assignment_rows.values()
                    if assignment["subject_id"] == subject.id
                }),
                "is_synthetic": bool(subject.is_synthetic),
            }
            for subject in subjects
        ],
        "student_section_assignments": [
            {
                "student_id": student.id,
                "usn": student.usn,
                "name": users[student.user_id].display_name if student.user_id in users else None,
                "section_id": student.section_id,
            }
            for student in students
        ],
        "faculty_subject_section_assignments": [
            {**assignment, "timetable_entry_count": sum(
                entry.faculty_id == assignment["faculty_id"]
                and entry.subject_id == assignment["subject_id"]
                and entry.section_id == assignment["section_id"]
                for entry in assignments
            )}
            for assignment in assignment_rows.values()
        ],
        "upcoming_assessments": [
            {
                "id": assessment.id,
                "title": assessment.title,
                "date": assessment.date.isoformat(),
                "section_id": assessment.section_id,
                "subject_id": assessment.subject_id,
                "status": assessment.status,
            }
            for assessment in db.query(Assessment).filter(
                Assessment.status == "PUBLISHED",
                Assessment.date >= get_now(),
            ).order_by(Assessment.date).limit(20).all()
        ],
        "attendance_sessions": [
            {
                "id": session.id,
                "session_date": session.session_date.isoformat(),
                "status": session.status,
                "section_id": session.section_id,
                "subject_id": session.subject_id,
            }
            for session in db.query(AttendanceSession).order_by(
                AttendanceSession.session_date.desc()
            ).limit(20).all()
        ],
        "recent_activity": [
            {
                "id": entry.id,
                "actor": (
                    activity_users[entry.user_id].display_name
                    or activity_users[entry.user_id].email
                ) if entry.user_id in activity_users else "Unknown account",
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "timestamp": entry.ts.isoformat(),
            }
            for entry in audit_rows
        ],
        "announcements": [
            {
                "id": item.id,
                "title": item.title,
                "body": item.body,
                "section_id": item.section_id,
                "audience": item.audience,
                "created_by": item.created_by,
                "creator": (
                    announcement_users[item.created_by].display_name
                    or announcement_users[item.created_by].email
                ) if item.created_by in announcement_users else "Unknown account",
                "status": "PUBLISHED",
                "published_at": item.published_at.isoformat(),
            }
            for item in announcements
        ],
    }


@router.post("/announcements", status_code=201)
def create_academic_announcement(
    body: AcademicAnnouncementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    if body.section_id and not db.query(Section).filter(
        Section.id == body.section_id
    ).first():
        raise HTTPException(status_code=422, detail="Select an existing section.")
    announcement = Announcement(
        id=_id("announcement"),
        title=body.title,
        body=body.body,
        audience=body.audience,
        section_id=body.section_id,
        created_by=user.id,
        published_at=get_now(),
    )
    db.add(announcement)
    log_audit(
        db,
        user.id,
        "PUBLISH_ACADEMIC_ANNOUNCEMENT",
        "Announcement",
        announcement.id,
        {"audience": body.audience, "section_id": body.section_id},
        role=user.role,
    )
    db.commit()
    return {
        "id": announcement.id,
        "title": announcement.title,
        "section_id": announcement.section_id,
        "published_at": announcement.published_at.isoformat(),
    }


def _department(db: Session, department_id: str) -> Department:
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=422, detail="Select an existing department.")
    return department


def _section_for_department(
    db: Session, section_id: str, department_id: str
) -> Section:
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=422, detail="Select an existing section.")
    if section.department_id != department_id:
        raise HTTPException(
            status_code=422,
            detail="The selected section does not belong to the selected department.",
        )
    return section


def _ensure_email_available(
    db: Session, email: str, exclude_user_id: str | None = None
) -> None:
    query = db.query(User).filter(func.lower(User.email) == email.lower())
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    if query.first():
        raise HTTPException(status_code=409, detail="That college email is already in use.")


def _ensure_unique_value(
    db: Session,
    model: type[Student] | type[Faculty],
    field: str,
    value: str,
    label: str,
    exclude_id: str | None = None,
) -> None:
    column = getattr(model, field)
    query = db.query(model).filter(func.upper(column) == value.upper())
    if exclude_id:
        query = query.filter(model.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail=f"That {label} is already in use.")


def _raise_integrity_error(
    error: IntegrityError,
    duplicate_detail: str,
    reference_detail: str,
) -> None:
    original = error.orig
    sqlstate = getattr(original, "sqlstate", None)
    if sqlstate is None:
        sqlstate = getattr(getattr(original, "diag", None), "sqlstate", None)
    message = str(original).lower()
    if sqlstate == "23505" or "unique constraint failed" in message or "duplicate key" in message:
        raise HTTPException(status_code=409, detail=duplicate_detail) from error
    if sqlstate == "23503" or "foreign key constraint failed" in message:
        raise HTTPException(status_code=409, detail=reference_detail) from error
    raise error


def _student_response(db: Session, student: Student) -> StudentResponse:
    user = db.query(User).filter(User.id == student.user_id).first()
    section = db.query(Section).filter(Section.id == student.section_id).first()
    department = db.query(Department).filter(
        Department.id == (section.department_id if section else None)
    ).first()
    if not user or not section or not department:
        raise HTTPException(
            status_code=409,
            detail="This student record is incomplete. Assign an account and valid section before continuing.",
        )
    return StudentResponse(
        id=student.id,
        user_id=user.id,
        usn=student.usn,
        email=user.email,
        name=user.display_name or "",
        phone=student.phone,
        department_id=department.id,
        department=department.name,
        program=student.program,
        semester=student.semester,
        section_id=section.id,
        section=section.code,
        admission_year=student.admission_year,
        academic_status=student.academic_status,
        profile=student.profile,
        active=user.active,
        synthetic_section=bool(section.is_synthetic),
    )


def _faculty_response(db: Session, faculty: Faculty) -> FacultyResponse:
    user = db.query(User).filter(User.id == faculty.user_id).first() if faculty.user_id else None
    department = db.query(Department).filter(
        Department.id == faculty.department_id
    ).first() if faculty.department_id else None

    assignments = db.query(TimetableEntry).filter(
        TimetableEntry.faculty_id == faculty.id
    ).all()
    subject_ids = {entry.subject_id for entry in assignments if entry.subject_id}
    section_ids = {entry.section_id for entry in assignments if entry.section_id}
    subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all() if subject_ids else []
    sections = db.query(Section).filter(Section.id.in_(section_ids)).all() if section_ids else []

    return FacultyResponse(
        id=faculty.id,
        user_id=user.id if user else None,
        employee_id=faculty.employee_id,
        email=user.email if user else None,
        name=faculty.name or (user.display_name if user else None),
        department_id=faculty.department_id or "",
        department=department.name if department else "Unassigned",
        designation=faculty.designation,
        subjects_taught=sorted(subject.code for subject in subjects),
        sections_handled=sorted(section.code for section in sections),
        active=bool(user and user.active),
        account_provisioned=user is not None,
        synthetic=bool(faculty.is_synthetic),
    )


@router.get("/departments")
def list_departments(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    return [
        {
            "id": department.id,
            "name": department.name,
            "section_count": db.query(func.count(Section.id)).filter(
                Section.department_id == department.id
            ).scalar() or 0,
            "subject_count": db.query(func.count(Subject.id)).filter(
                Subject.department_id == department.id
            ).scalar() or 0,
        }
        for department in db.query(Department).order_by(Department.name).all()
    ]


@router.post("/departments", status_code=201)
def create_department(
    body: DepartmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    _ensure_unique_name(db, Department, "name", body.name, "department name")
    department = Department(id=_id("department"), name=body.name)
    db.add(department)
    log_audit(db, user.id, "CREATE_DEPARTMENT", "Department", department.id, {
        "name": department.name,
    }, role=user.role)
    db.commit()
    return {"id": department.id, "name": department.name}


@router.patch("/departments/{department_id}")
def update_department(
    department_id: str,
    body: DepartmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found.")
    _ensure_unique_name(db, Department, "name", body.name, "department name", department.id)
    department.name = body.name
    log_audit(db, user.id, "UPDATE_DEPARTMENT", "Department", department.id, {
        "name": department.name,
    }, role=user.role)
    db.commit()
    return {"id": department.id, "name": department.name}


@router.get("/sections")
def list_sections(
    department_id: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    query = db.query(Section)
    if department_id:
        query = query.filter(Section.department_id == department_id)
    sections = query.order_by(Section.code).all()
    assignments = db.query(TimetableEntry).filter(
        TimetableEntry.section_id.in_([section.id for section in sections])
    ).all() if sections else []
    subjects_by_id = {
        subject.id: subject
        for subject in db.query(Subject).filter(
            Subject.id.in_({entry.subject_id for entry in assignments if entry.subject_id})
        ).all()
    } if assignments else {}
    faculty_by_id = {
        faculty.id: faculty
        for faculty in db.query(Faculty).filter(
            Faculty.id.in_({entry.faculty_id for entry in assignments if entry.faculty_id})
        ).all()
    } if assignments else {}
    student_counts = dict(
        db.query(Student.section_id, func.count(Student.id))
        .filter(Student.section_id.in_([section.id for section in sections]))
        .group_by(Student.section_id)
        .all()
    ) if sections else {}
    assignments_by_section: dict[str, dict[tuple[str | None, str | None], dict]] = {}
    for entry in assignments:
        subject = subjects_by_id.get(entry.subject_id)
        faculty = faculty_by_id.get(entry.faculty_id)
        if not subject:
            continue
        rows = assignments_by_section.setdefault(entry.section_id, {})
        key = (subject.id, faculty.id if faculty else None)
        row = rows.setdefault(key, {
            "subject_id": subject.id,
            "subject_code": subject.code,
            "subject_name": subject.name,
            "faculty_id": faculty.id if faculty else None,
            "faculty_name": faculty.name if faculty else None,
            "timetable_entry_count": 0,
        })
        row["timetable_entry_count"] += 1
    return [
        {
            "id": section.id,
            "code": section.code,
            "name": section.name,
            "department_id": section.department_id,
            "year": section.year,
            "strength": section.strength,
            "student_count": student_counts.get(section.id, 0),
            "teaching_assignments": list(assignments_by_section.get(section.id, {}).values()),
            "synthetic": bool(section.is_synthetic),
        }
        for section in sections
    ]


@router.post("/sections", status_code=201)
def create_section(
    body: SectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    _department(db, body.department_id)
    _ensure_unique_name(db, Section, "code", body.code, "section code")
    section = Section(
        id=_id("section"),
        code=body.code,
        name=body.name,
        department_id=body.department_id,
        year=body.year,
        strength=body.strength,
        is_synthetic=False,
    )
    db.add(section)
    log_audit(db, user.id, "CREATE_SECTION", "Section", section.id, {
        "code": section.code,
        "department_id": section.department_id,
    }, role=user.role)
    db.commit()
    return {
        "id": section.id,
        "code": section.code,
        "name": section.name,
        "department_id": section.department_id,
        "year": section.year,
        "strength": section.strength,
    }


@router.patch("/sections/{section_id}")
def update_section(
    section_id: str,
    body: SectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found.")
    changes = body.model_dump(exclude_unset=True)
    _ensure_unique_name(
        db, Section, "code", changes.get("code", section.code),
        "section code", section.id,
    )
    department_id = changes.get("department_id", section.department_id)
    if department_id:
        _department(db, department_id)
    if department_id != section.department_id:
        linked_students = db.query(func.count(Student.id)).filter(
            Student.section_id == section.id
        ).scalar()
        linked_classes = db.query(func.count(TimetableEntry.id)).filter(
            TimetableEntry.section_id == section.id
        ).scalar()
        if linked_students or linked_classes:
            raise HTTPException(
                status_code=409,
                detail="Move students and timetable assignments before changing this section's department.",
            )
    for field, value in changes.items():
        setattr(section, field, value)
    log_audit(db, user.id, "UPDATE_SECTION", "Section", section.id, {
        "fields": sorted(changes),
    }, role=user.role)
    db.commit()
    return {
        "id": section.id,
        "code": section.code,
        "name": section.name,
        "department_id": section.department_id,
        "year": section.year,
        "strength": section.strength,
    }


@router.get("/subjects")
def list_subjects(
    q: str | None = Query(default=None, max_length=120),
    department_id: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    query = db.query(Subject)
    if department_id:
        query = query.filter(Subject.department_id == department_id)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(Subject.code.ilike(pattern), Subject.name.ilike(pattern)))
    subjects = query.order_by(Subject.code).all()
    return {
        "items": [
            {
                "id": subject.id,
                "code": subject.code,
                "name": subject.name,
                "department_id": subject.department_id,
                "credits": subject.credits,
                "description": subject.description,
                "kind": subject.kind,
                "is_synthetic": bool(subject.is_synthetic),
            }
            for subject in subjects
        ],
        "total": len(subjects),
    }


@router.post("/subjects", status_code=201)
def create_subject(
    body: SubjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    _ensure_unique_name(db, Subject, "code", body.code, "subject code")
    if body.department_id:
        _department(db, body.department_id)
    subject = Subject(
        id=_id("subject"),
        code=body.code,
        name=body.name,
        department_id=body.department_id,
        credits=body.credits,
        description=body.description,
        kind=body.kind,
        is_synthetic=False,
    )
    db.add(subject)
    log_audit(db, user.id, "CREATE_SUBJECT", "Subject", subject.id, {
        "code": subject.code,
        "department_id": subject.department_id,
    }, role=user.role)
    db.commit()
    return {"id": subject.id, "code": subject.code, "name": subject.name}


@router.patch("/subjects/{subject_id}")
def update_subject(
    subject_id: str,
    body: SubjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")
    changes = body.model_dump(exclude_unset=True)
    _ensure_unique_name(
        db, Subject, "code", changes.get("code", subject.code),
        "subject code", subject.id,
    )
    if "department_id" in changes and changes["department_id"]:
        _department(db, changes["department_id"])
    if changes.get("department_id") != subject.department_id and "department_id" in changes:
        if db.query(TimetableEntry).filter(TimetableEntry.subject_id == subject.id).first():
            raise HTTPException(
                status_code=409,
                detail="Move timetable assignments before changing this subject's department.",
            )
    for field, value in changes.items():
        setattr(subject, field, value)
    log_audit(db, user.id, "UPDATE_SUBJECT", "Subject", subject.id, {
        "fields": sorted(changes),
    }, role=user.role)
    db.commit()
    return {"id": subject.id, "code": subject.code, "name": subject.name}


@router.get("/students")
def list_students(
    q: str | None = Query(default=None, max_length=120),
    department_id: str | None = None,
    semester: int | None = Query(default=None, ge=1, le=8),
    section_id: str | None = None,
    active: bool | None = None,
    academic_status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    query = (
        db.query(Student)
        .join(User, User.id == Student.user_id)
        .join(Section, Section.id == Student.section_id)
    )
    if department_id:
        query = query.filter(Section.department_id == department_id)
    if semester is not None:
        query = query.filter(Student.semester == semester)
    if section_id:
        query = query.filter(Student.section_id == section_id)
    if active is not None:
        query = query.filter(User.active.is_(active))
    if academic_status:
        query = query.filter(func.upper(Student.academic_status) == academic_status.strip().upper())
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(
            Student.usn.ilike(pattern),
            User.email.ilike(pattern),
            User.display_name.ilike(pattern),
            Student.academic_status.ilike(pattern),
        ))
    total = query.count()
    students = query.order_by(Student.usn, User.display_name).offset(offset).limit(limit).all()
    return {"items": [_student_response(db, student) for student in students], "total": total}


@router.get("/students/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    return _student_response(db, student)


@router.post("/students", response_model=StudentResponse, status_code=201)
def create_student(
    body: StudentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    department = _department(db, body.department_id)
    section = _section_for_department(db, body.section_id, department.id)
    _ensure_email_available(db, body.email)
    _ensure_unique_value(db, Student, "usn", body.usn, label="USN")

    account = User(
        id=_id("user"),
        email=body.email,
        hashed_password=get_password_hash(body.password),
        role="STUDENT",
        display_name=body.name,
        active=True,
        can_view_incidents=False,
    )
    student = Student(
        id=_id("student"),
        user_id=account.id,
        section_id=section.id,
        usn=body.usn,
        phone=body.phone,
        program=body.program,
        semester=body.semester,
        admission_year=body.admission_year,
        academic_status=body.academic_status,
        profile=body.profile,
    )
    db.add(account)
    db.flush()
    db.add(student)
    log_audit(db, user.id, "CREATE_STUDENT", "Student", student.id, {
        "usn": student.usn,
        "email": account.email,
        "section_id": section.id,
    }, role=user.role)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        _raise_integrity_error(
            error,
            "A student with that USN or college email already exists.",
            "The selected account or section is no longer available. Refresh and try again.",
        )
    db.refresh(student)
    return _student_response(db, student)


@router.patch("/students/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: str,
    body: StudentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    account = db.query(User).filter(User.id == student.user_id).first()
    if not account:
        raise HTTPException(status_code=409, detail="Student has no linked login account.")

    changes = body.model_dump(exclude_unset=True)
    section_id = changes.get("section_id", student.section_id)
    current_section = db.query(Section).filter(Section.id == student.section_id).first()
    department_id = changes.get(
        "department_id",
        current_section.department_id if current_section else None,
    )
    if changes.get("department_id") is not None or changes.get("section_id") is not None:
        if not department_id or not section_id:
            raise HTTPException(status_code=422, detail="Assign both department and section.")
        _section_for_department(db, section_id, department_id)
    if changes.get("email") is not None:
        _ensure_email_available(db, changes["email"], exclude_user_id=account.id)
        account.email = changes["email"]
    if changes.get("usn") is not None:
        _ensure_unique_value(
            db, Student, "usn", changes["usn"], exclude_id=student.id, label="USN"
        )

    field_names = {
        "usn", "phone", "program", "semester", "section_id",
        "admission_year", "academic_status", "profile",
    }
    for key in field_names.intersection(changes):
        setattr(student, key, changes[key])
    if changes.get("name") is not None:
        account.display_name = changes["name"]
    if changes.get("active") is not None:
        account.active = changes["active"]

    log_audit(db, user.id, "UPDATE_STUDENT", "Student", student.id, {
        "fields": sorted(changes),
    }, role=user.role)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        _raise_integrity_error(
            error,
            "A student with that USN or college email already exists.",
            "The selected account or section is no longer available. Refresh and try again.",
        )
    db.refresh(student)
    return _student_response(db, student)


@router.post("/students/{student_id}/password")
def reset_student_password(
    student_id: str,
    body: PasswordReset,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    account = db.query(User).filter(User.id == student.user_id).first() if student else None
    if not student or not account:
        raise HTTPException(status_code=404, detail="Student account not found.")
    account.hashed_password = get_password_hash(body.password)
    log_audit(db, user.id, "RESET_STUDENT_PASSWORD", "Student", student.id, {}, role=user.role)
    db.commit()
    return {"ok": True}


@router.get("/faculty")
def list_faculty(
    q: str | None = Query(default=None, max_length=120),
    department_id: str | None = None,
    active: bool | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    query = db.query(Faculty).outerjoin(User, User.id == Faculty.user_id)
    if department_id:
        query = query.filter(Faculty.department_id == department_id)
    if active is not None:
        query = query.filter(User.active.is_(active))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(
            Faculty.employee_id.ilike(pattern),
            Faculty.name.ilike(pattern),
            Faculty.designation.ilike(pattern),
            User.email.ilike(pattern),
            User.display_name.ilike(pattern),
        ))
    total = query.count()
    faculty_members = query.order_by(Faculty.employee_id, Faculty.name).offset(offset).limit(limit).all()
    return {
        "items": [_faculty_response(db, faculty) for faculty in faculty_members],
        "total": total,
    }


@router.get("/faculty/{faculty_id}", response_model=FacultyResponse)
def get_faculty(
    faculty_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(["MANAGEMENT"])),
):
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty member not found.")
    return _faculty_response(db, faculty)


@router.post("/faculty", response_model=FacultyResponse, status_code=201)
def create_faculty(
    body: FacultyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    department = _department(db, body.department_id)
    _ensure_email_available(db, body.email)
    _ensure_unique_value(
        db, Faculty, "employee_id", body.employee_id, label="employee ID"
    )
    account = User(
        id=_id("user"),
        email=body.email,
        hashed_password=get_password_hash(body.password),
        role="FACULTY",
        display_name=body.name,
        active=True,
        can_view_incidents=False,
    )
    faculty = Faculty(
        id=_id("faculty"),
        user_id=account.id,
        department_id=department.id,
        name=body.name,
        employee_id=body.employee_id,
        designation=body.designation,
        is_synthetic=False,
    )
    db.add(account)
    db.flush()
    db.add(faculty)
    log_audit(db, user.id, "CREATE_FACULTY", "Faculty", faculty.id, {
        "employee_id": faculty.employee_id,
        "email": account.email,
        "department_id": department.id,
    }, role=user.role)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        _raise_integrity_error(
            error,
            "A faculty member with that employee ID or college email already exists.",
            "The selected account or department is no longer available. Refresh and try again.",
        )
    db.refresh(faculty)
    return _faculty_response(db, faculty)


@router.patch("/faculty/{faculty_id}", response_model=FacultyResponse)
def update_faculty(
    faculty_id: str,
    body: FacultyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty member not found.")
    account = db.query(User).filter(User.id == faculty.user_id).first() if faculty.user_id else None
    changes = body.model_dump(exclude_unset=True)

    if account is None:
        if bool(changes.get("email")) != bool(changes.get("password")):
            raise HTTPException(
                status_code=422,
                detail="Provide both college email and initial password to provision this faculty login.",
            )
        if changes.get("email") and changes.get("password"):
            _ensure_email_available(db, changes["email"])
            account = User(
                id=_id("user"),
                email=changes["email"],
                hashed_password=get_password_hash(changes["password"]),
                role="FACULTY",
                display_name=faculty.name,
                active=True,
                can_view_incidents=False,
            )
            db.add(account)
            db.flush()
            faculty.user_id = account.id
    elif "password" in changes:
        raise HTTPException(
            status_code=422,
            detail="Use the faculty password endpoint to reset an existing account password.",
        )

    if changes.get("department_id") is not None:
        faculty.department_id = _department(db, changes["department_id"]).id
    if changes.get("employee_id") is not None:
        _ensure_unique_value(
            db, Faculty, "employee_id", changes["employee_id"],
            exclude_id=faculty.id, label="employee ID",
        )
        faculty.employee_id = changes["employee_id"]
    if changes.get("name") is not None:
        faculty.name = changes["name"]
        if account:
            account.display_name = changes["name"]
    if changes.get("designation") is not None:
        faculty.designation = changes["designation"]
    if account and changes.get("email") is not None:
        _ensure_email_available(db, changes["email"], exclude_user_id=account.id)
        account.email = changes["email"]
    if account and changes.get("active") is not None:
        account.active = changes["active"]

    log_audit(db, user.id, "UPDATE_FACULTY", "Faculty", faculty.id, {
        "fields": sorted(set(changes) - {"password"}),
    }, role=user.role)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        _raise_integrity_error(
            error,
            "A faculty member with that employee ID or college email already exists.",
            "The selected account or department is no longer available. Refresh and try again.",
        )
    db.refresh(faculty)
    return _faculty_response(db, faculty)


@router.post("/faculty/{faculty_id}/password")
def reset_faculty_password(
    faculty_id: str,
    body: PasswordReset,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    account = db.query(User).filter(User.id == faculty.user_id).first() if faculty and faculty.user_id else None
    if not faculty or not account:
        raise HTTPException(status_code=409, detail="Faculty member has no provisioned login account.")
    account.hashed_password = get_password_hash(body.password)
    log_audit(db, user.id, "RESET_FACULTY_PASSWORD", "Faculty", faculty.id, {}, role=user.role)
    db.commit()
    return {"ok": True}
