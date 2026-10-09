"""Authenticated student profile and academic information."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.clock import get_now
from app.deps import get_db, require_roles
from app.models.academic import Department, Faculty, Section, Student, Subject
from app.models.identity import User
from app.models.academic_content import AcademicMark, AcademicResource, SyllabusModule
from app.models.faculty_work import AttendanceRecord, AttendanceSession
from app.models.operations import Assessment
from app.models.operations import Announcement
from app.announcement_access import announcement_visible
from app.models.schedule import TimetableEntry
from app.schemas.student import (
    StudentAcademicResource,
    StudentAssessment,
    StudentAcademicsResponse,
    StudentAttendanceSummary,
    StudentMark,
    StudentProfileResponse,
    StudentSyllabusModule,
    StudentSubjectDetailResponse,
    StudentSubjectResponse,
)

router = APIRouter(prefix="/student")


def _get_student(db: Session, user: User) -> Student:
    student = db.query(Student).filter(Student.user_id == user.id).first()
    if student is None:
        raise HTTPException(status_code=404, detail="Student profile is not provisioned.")
    return student


def _attendance_summary(
    db: Session, student: Student, subject_id: str
) -> StudentAttendanceSummary | None:
    rows = db.query(AttendanceRecord.status).join(
        AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id
    ).filter(
        AttendanceRecord.student_id == student.id,
        AttendanceSession.section_id == student.section_id,
        AttendanceSession.subject_id == subject_id,
    ).all()
    if not rows:
        return None
    present = sum(1 for row in rows if row.status.upper() == "PRESENT")
    absent = sum(1 for row in rows if row.status.upper() == "ABSENT")
    total = present + absent
    if total == 0:
        return None
    return StudentAttendanceSummary(
        total_classes=total,
        present=present,
        absent=absent,
        percentage=round((present / total) * 100, 2),
    )


def _assessment_response(assessment: Assessment, is_synthetic: bool) -> StudentAssessment:
    return StudentAssessment(
        id=assessment.id,
        title=assessment.title,
        kind=assessment.kind,
        date=assessment.date.isoformat(),
        description=assessment.description,
        maximum_marks=float(assessment.maximum_marks) if assessment.maximum_marks is not None else None,
        status=assessment.status,
        is_synthetic=is_synthetic,
    )


def _student_subjects(db: Session, student: Student):
    section = db.query(Section).filter(Section.id == student.section_id).first()
    if section is None:
        return None, []

    entries = db.query(TimetableEntry).filter(
        TimetableEntry.section_id == section.id
    ).all()
    subject_entries: dict[str, list[TimetableEntry]] = {}
    for entry in entries:
        if entry.subject_id:
            subject_entries.setdefault(entry.subject_id, []).append(entry)

    subjects = []
    for subject_id, assignments in subject_entries.items():
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if subject is None:
            continue
        faculty_ids = {entry.faculty_id for entry in assignments if entry.faculty_id}
        faculty_names = sorted({
            faculty.name
            for faculty in db.query(Faculty).filter(Faculty.id.in_(faculty_ids)).all()
            if faculty.name
        }) if faculty_ids else []
        provenance = [entry.provenance or "" for entry in assignments]
        demo_data = bool(
            section.is_synthetic
            or subject.is_synthetic
            or any(
                "demo" in value.casefold() or "synthetic" in value.casefold()
                for value in provenance
            )
        )
        subjects.append(StudentSubjectResponse(
            id=subject.id,
            code=subject.code,
            name=subject.name,
            kind=subject.kind,
            faculty=faculty_names,
            demo_data=demo_data,
            credits=subject.credits,
            description=subject.description,
            attendance=_attendance_summary(db, student, subject.id),
            upcoming_assessments=db.query(Assessment).filter(
                Assessment.section_id == section.id,
                Assessment.subject_id == subject.id,
                Assessment.status == "PUBLISHED",
                Assessment.date >= get_now(),
            ).count(),
            resources_count=db.query(AcademicResource).filter(
                AcademicResource.section_id == section.id,
                AcademicResource.subject_id == subject.id,
                AcademicResource.status == "PUBLISHED",
            ).count(),
        ))
    subjects.sort(key=lambda item: (item.code.casefold(), item.name.casefold()))
    return section, subjects


@router.get("/profile", response_model=StudentProfileResponse)
def get_student_profile(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["STUDENT"])),
):
    student = _get_student(db, user)
    section = db.query(Section).filter(Section.id == student.section_id).first()
    department = db.query(Department).filter(
        Department.id == (section.department_id if section else None)
    ).first()
    return StudentProfileResponse(
        full_name=user.display_name or user.email,
        usn=student.usn,
        email=user.email,
        phone=student.phone,
        program=student.program,
        department=department.name if department else None,
        semester=student.semester,
        section=section.code if section else None,
        admission_year=student.admission_year,
        academic_status=student.academic_status,
    )


@router.get("/academics", response_model=StudentAcademicsResponse)
def get_student_academics(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["STUDENT"])),
):
    student = _get_student(db, user)
    section, subjects = _student_subjects(db, student)
    department = db.query(Department).filter(
        Department.id == (section.department_id if section else None)
    ).first()
    upcoming = db.query(Assessment).filter(
        Assessment.section_id == student.section_id,
        Assessment.status == "PUBLISHED",
        Assessment.date >= get_now(),
    ).order_by(Assessment.date).all()
    assessment_subject_ids = {item.subject_id for item in upcoming if item.subject_id}
    subjects_by_id = {
        item.id: item
        for item in db.query(Subject).filter(Subject.id.in_(assessment_subject_ids)).all()
    } if assessment_subject_ids else {}
    return StudentAcademicsResponse(
        subjects=subjects,
        message=None if subjects else "Academic information has not been published yet.",
        program=student.program,
        department=department.name if department else None,
        semester=student.semester,
        section=section.code if section else None,
        attendance_available=any(subject.attendance is not None for subject in subjects),
        upcoming_assessments=[
            _assessment_response(
                assessment,
                bool(
                    assessment.is_synthetic
                    or (section.is_synthetic if section else False)
                    or (
                        subjects_by_id.get(assessment.subject_id).is_synthetic
                        if assessment.subject_id in subjects_by_id else False
                    )
                ),
            )
            for assessment in upcoming
        ],
        announcements=[
            {
                "id": item.id,
                "title": item.title,
                "body": item.body,
                "published_at": item.published_at.isoformat(),
            }
            for item in db.query(Announcement).order_by(
                Announcement.published_at.desc()
            ).all()
            if announcement_visible(item, "STUDENT", student.section_id)
        ],
    )


@router.get("/academics/{subject_id}", response_model=StudentSubjectDetailResponse)
def get_student_subject(
    subject_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["STUDENT"])),
):
    student = _get_student(db, user)
    section, subjects = _student_subjects(db, student)
    subject = next((item for item in subjects if item.id == subject_id), None)
    if subject is None or section is None:
        raise HTTPException(status_code=404, detail="Subject not found in your section.")
    modules = db.query(SyllabusModule).filter(
        SyllabusModule.subject_id == subject_id,
        SyllabusModule.status == "PUBLISHED",
    ).order_by(SyllabusModule.sequence, SyllabusModule.module_number).all()
    resources = db.query(AcademicResource).filter(
        AcademicResource.subject_id == subject_id,
        AcademicResource.section_id == section.id,
        AcademicResource.status == "PUBLISHED",
    ).order_by(AcademicResource.created_at.desc()).all()
    assessments = db.query(Assessment).filter(
        Assessment.subject_id == subject_id,
        Assessment.section_id == section.id,
        Assessment.status == "PUBLISHED",
    ).order_by(Assessment.date).all()
    published_assessment_ids = [assessment.id for assessment in assessments]
    mark_rows = db.query(AcademicMark, Assessment).join(
        Assessment, Assessment.id == AcademicMark.assessment_id
    ).filter(
        AcademicMark.student_id == student.id,
        AcademicMark.assessment_id.in_(published_assessment_ids),
    ).all() if published_assessment_ids else []
    marks = [
        StudentMark(
            assessment_id=assessment.id,
            assessment_title=assessment.title,
            kind=assessment.kind,
            date=assessment.date.isoformat(),
            marks=float(mark.marks),
            maximum_marks=float(assessment.maximum_marks),
            percentage=round(float(mark.marks) / float(assessment.maximum_marks) * 100, 2),
        )
        for mark, assessment in mark_rows
        if assessment.maximum_marks is not None and assessment.maximum_marks > 0
    ]
    attendance = _attendance_summary(db, student, subject_id)
    return StudentSubjectDetailResponse(
        **subject.model_dump(),
        section=section.code,
        syllabus_published=bool(modules),
        resources_published=bool(resources),
        syllabus=[
            StudentSyllabusModule(
                module_number=module.module_number,
                title=module.title,
                description=module.description,
                sequence=module.sequence,
                is_synthetic=bool(module.is_synthetic),
            )
            for module in modules
        ],
        resources=[
            StudentAcademicResource(
                id=resource.id,
                title=resource.title,
                description=resource.description,
                resource_type=resource.resource_type,
                url=resource.url,
                is_synthetic=bool(resource.is_synthetic),
            )
            for resource in resources
        ],
        assessments=[
            _assessment_response(assessment, bool(assessment.is_synthetic or subject.demo_data))
            for assessment in assessments
        ],
        marks=marks,
        attendance_message=(
            "Attendance records have not been entered yet."
            if attendance is None
            else None
        ),
    )
