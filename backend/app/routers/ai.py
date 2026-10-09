from datetime import datetime, time, timedelta
import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.clock import get_now
from app.deps import get_current_user, get_db
from app.engine.slots import PERIOD_SLOTS, SLOTS
from app.models.academic import Department, Faculty, Section, Student, Subject
from app.models.academic_content import AcademicMark, AcademicResource, SyllabusModule
from app.models.campus import Floor, Room
from app.models.faculty_work import AttendanceRecord, AttendanceSession
from app.models.identity import User
from app.models.operations import Assessment
from app.models.operations import Announcement
from app.announcement_access import announcement_visible
from app.models.schedule import SessionOverride, TimetableEntry

router = APIRouter()


@router.post("/ai/chat")
def ai_chat(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    message = body.get("message", "").lower()
    now = get_now()

    if user.role == "MANAGEMENT":
        if "room" in message and any(word in message for word in ("how many", "count", "registered", "total")):
            count = db.query(Room).count()
            return {"response": f"There are {count} campus rooms registered."}
        if "section" in message and any(word in message for word in ("how many", "count", "total")):
            count = db.query(Section).count()
            return {"response": f"There are {count} sections registered."}
        if "faculty" in message and any(word in message for word in ("how many", "count", "active", "total")):
            count = db.query(Faculty).join(User, User.id == Faculty.user_id).filter(User.active.is_(True)).count()
            return {"response": f"There are {count} active faculty members."}
        if "student" in message and any(word in message for word in ("how many", "count", "active", "total")):
            count = db.query(Student).join(User, User.id == Student.user_id).filter(User.active.is_(True)).count()
            return {"response": f"There are {count} active students."}
        if "room" in message and "available" in message:
            rooms = db.query(Room).filter(
                Room.status == "ACTIVE",
                Room.allocatable_for_classes.is_(True),
            ).order_by(Room.code).all()
            return {
                "response": (
                    "Rooms marked active and allocatable: "
                    + ", ".join(room.code for room in rooms)
                    if rooms else "No rooms are currently marked active and allocatable."
                )
            }
        if "room" in message and (
            "1st floor" in message or "first floor" in message or "floor 1" in message
        ):
            floor_ids = [
                floor.id for floor in db.query(Floor).filter(Floor.level == 1).all()
            ]
            rooms = db.query(Room).filter(Room.floor_id.in_(floor_ids)).order_by(Room.code).all() if floor_ids else []
            return {
                "response": (
                    "Rooms on the 1st floor: " + ", ".join(room.code for room in rooms)
                    if rooms else "No rooms are recorded on the 1st floor."
                )
            }
        return {
            "response": "I can answer grounded campus counts, active room listings, and 1st-floor room lookups."
        }

    student = None
    faculty = None
    section_id = None
    if user.role == "STUDENT":
        student = db.query(Student).filter(Student.user_id == user.id).first()
        section_id = student.section_id if student else None
    elif user.role == "FACULTY":
        faculty = db.query(Faculty).filter(Faculty.user_id == user.id).first()

    if student and section_id:
        timetable_entries = db.query(TimetableEntry).filter(
            TimetableEntry.section_id == section_id
        ).all()
    elif faculty:
        timetable_entries = db.query(TimetableEntry).filter(
            TimetableEntry.faculty_id == faculty.id
        ).all()
    else:
        timetable_entries = []

    identity_context = {
        "user_id": user.id,
        "role": user.role,
        "student_id": student.id if student else None,
        "section_id": section_id,
        "timetable_entry_ids": [entry.id for entry in timetable_entries],
    }
    if faculty:
        subject_ids = {entry.subject_id for entry in timetable_entries if entry.subject_id}
        section_ids = {entry.section_id for entry in timetable_entries if entry.section_id}
        department = db.query(Department).filter(
            Department.id == faculty.department_id
        ).first()
        identity_context.update({
            "faculty_id": faculty.id,
            "faculty_name": faculty.name or user.display_name,
            "department": department.name if department else None,
            "subject_ids": sorted(subject_ids),
            "section_ids": sorted(section_ids),
        })

    academic_request = student and any(
        phrase in message
        for phrase in (
            "subject", "attendance", "classes have i attended", "assessment",
            "syllabus", "module", "resource", "notes", "marks", "my score", "announcement",
        )
    )
    if academic_request:
        unavailable = "I don't have that academic information available yet."
        if "announcement" in message:
            announcements = [
                item for item in db.query(Announcement).order_by(
                    Announcement.published_at.desc()
                ).all()
                if announcement_visible(item, "STUDENT", student.section_id)
            ]
            return {
                "response": (
                    "Academic announcements: " + "; ".join(
                        f"{item.title}: {item.body}" for item in announcements
                    )
                    if announcements else unavailable
                )
            }
        if any(phrase in message for phrase in (
            "what subjects", "which subjects", "my subjects",
            "subjects do i", "subject list",
        )) or ("semester" in message and not any(
            phrase in message for phrase in ("module", "syllabus", "resource", "assessment")
        )):
            section_subject_ids = sorted({
                entry.subject_id for entry in timetable_entries if entry.subject_id
            })
            subjects = db.query(Subject).filter(
                Subject.id.in_(section_subject_ids)
            ).order_by(Subject.code).all() if section_subject_ids else []
            return {
                "response": (
                    "Your subjects are: " + ", ".join(
                        f"{subject.code} — {subject.name}" for subject in subjects
                    )
                    if subjects else unavailable
                )
            }

        if "attendance" in message or "classes have i attended" in message:
            rows = db.query(AttendanceRecord.status).join(
                AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id
            ).filter(
                AttendanceRecord.student_id == student.id,
                AttendanceSession.section_id == student.section_id,
            ).all()
            present = sum(1 for row in rows if row.status.upper() == "PRESENT")
            absent = sum(1 for row in rows if row.status.upper() == "ABSENT")
            total = present + absent
            return {
                "response": (
                    f"You have attended {present} of {total} recorded classes; "
                    f"{absent} recorded classes are marked absent."
                    if total else unavailable
                )
            }

        if "assessment" in message:
            assessments = db.query(Assessment).filter(
                Assessment.section_id == student.section_id,
                Assessment.status == "PUBLISHED",
                Assessment.date >= now,
            ).order_by(Assessment.date).all()
            return {
                "response": (
                    "Your upcoming assessments are: " + "; ".join(
                        f"{item.title} on {item.date.strftime('%Y-%m-%d')}" for item in assessments
                    )
                    if assessments else unavailable
                )
            }

        subject_ids = sorted({
            entry.subject_id for entry in timetable_entries if entry.subject_id
        })
        student_subjects = db.query(Subject).filter(
            Subject.id.in_(subject_ids)
        ).all() if subject_ids else []
        matching_subject = next(
            (
                subject for subject in student_subjects
                if subject.code.casefold() in message
                or subject.name.casefold() in message
            ),
            student_subjects[0] if len(student_subjects) == 1 else None,
        )

        if "syllabus" in message or "module" in message:
            if matching_subject is None:
                return {"response": unavailable}
            module_match = re.search(r"\bmodule\s*(\d+)\b", message)
            modules_query = db.query(SyllabusModule).filter(
                SyllabusModule.subject_id == matching_subject.id,
                SyllabusModule.status == "PUBLISHED",
            )
            if module_match:
                modules_query = modules_query.filter(
                    SyllabusModule.module_number == int(module_match.group(1))
                )
            modules = modules_query.order_by(SyllabusModule.sequence).all()
            return {
                "response": (
                    "Published syllabus: " + "; ".join(
                        f"Module {item.module_number}: {item.title}"
                        + (f" — {item.description}" if item.description else "")
                        for item in modules
                    )
                    if modules else unavailable
                )
            }

        if "resource" in message or "notes" in message:
            resource_query = db.query(AcademicResource).filter(
                AcademicResource.section_id == student.section_id,
                AcademicResource.status == "PUBLISHED",
            )
            if matching_subject:
                resource_query = resource_query.filter(
                    AcademicResource.subject_id == matching_subject.id
                )
            resources = resource_query.order_by(AcademicResource.created_at.desc()).all()
            return {
                "response": (
                    "Available academic resources: " + "; ".join(
                        f"{item.title} ({item.resource_type})"
                        + (f" — {item.url}" if item.url else "")
                        for item in resources
                    )
                    if resources else unavailable
                )
            }

        if "mark" in message or "score" in message:
            query = db.query(AcademicMark, Assessment).join(
                Assessment, Assessment.id == AcademicMark.assessment_id
            ).filter(
                AcademicMark.student_id == student.id,
                Assessment.section_id == student.section_id,
                Assessment.status == "PUBLISHED",
            )
            if matching_subject:
                query = query.filter(Assessment.subject_id == matching_subject.id)
            rows = query.order_by(Assessment.date.desc()).all()
            published_marks = [
                f"{assessment.title}: {float(mark.marks)} / {float(assessment.maximum_marks)}"
                for mark, assessment in rows
                if assessment.maximum_marks is not None
            ]
            return {
                "response": (
                    "Published marks: " + "; ".join(published_marks)
                    if published_marks else unavailable
                )
            }
        return {"response": unavailable}

    if faculty and any(keyword in message for keyword in ("my subjects", "subjects do i teach", "what subjects")):
        subjects = db.query(Subject).filter(
            Subject.id.in_(identity_context["subject_ids"])
        ).order_by(Subject.code).all() if identity_context["subject_ids"] else []
        if not subjects:
            return {"response": "No subjects are linked to your teaching timetable yet."}
        return {"response": "Your assigned subjects are: " + ", ".join(
            f"{subject.code} — {subject.name}" for subject in subjects
        )}

    if faculty and any(keyword in message for keyword in ("my sections", "which sections", "sections do i teach")):
        sections = db.query(Section).filter(
            Section.id.in_(identity_context["section_ids"])
        ).order_by(Section.code).all() if identity_context["section_ids"] else []
        if not sections:
            return {"response": "No sections are linked to your teaching timetable yet."}
        return {"response": "Your assigned sections are: " + ", ".join(
            section.code for section in sections
        )}

    if any(keyword in message for keyword in ("why", "change", "happened", "room change")):
        if not identity_context["timetable_entry_ids"]:
            return {"response": "No timetable is linked to your account yet."}
        day_start = datetime.combine(now.date(), time.min)
        next_day = day_start + timedelta(days=1)
        overrides = db.query(SessionOverride).filter(
            SessionOverride.entry_id.in_(identity_context["timetable_entry_ids"]),
            SessionOverride.active.is_(True),
            SessionOverride.date >= day_start,
            SessionOverride.date < next_day,
        ).order_by(SessionOverride.date.desc()).all()
        if not overrides:
            return {"response": "No classroom changes are currently active for your schedule today."}

        entries_by_id = {entry.id: entry for entry in timetable_entries}
        changes = []
        for override in overrides:
            entry = entries_by_id.get(override.entry_id)
            if entry is None:
                continue
            subject = db.query(Subject).filter(Subject.id == entry.subject_id).first()
            old_room = db.query(Room).filter(Room.id == override.old_room_id).first()
            new_room = db.query(Room).filter(Room.id == override.room_id).first()
            subject_name = (
                f"{subject.code} — {subject.name}"
                if subject
                else "Scheduled class"
            )
            changes.append(
                f"{subject_name}: {old_room.code if old_room else 'unassigned'} → "
                f"{new_room.code if new_room else 'unassigned'}"
                + (f" because {override.reason}" if override.reason else "")
            )
        if not changes:
            return {"response": "No classroom changes are currently active for your schedule today."}
        return {"response": "Your schedule changes today: " + "; ".join(changes)}

    if any(keyword in message for keyword in ("where", "next class", "assigned to", "which room")):
        today = now.weekday()
        now_minutes = now.hour * 60 + now.minute
        ordered = sorted(
            timetable_entries,
            key=lambda entry: (
                (entry.weekday - today) % 7,
                PERIOD_SLOTS.index(entry.start_slot) if entry.start_slot in SLOTS else len(PERIOD_SLOTS),
            ),
        )
        entry = None
        for candidate in ordered:
            day_offset = (candidate.weekday - today) % 7
            slot_index = PERIOD_SLOTS.index(candidate.start_slot) if candidate.start_slot in SLOTS else -1
            if day_offset == 0 and slot_index >= 0:
                final_index = slot_index + (candidate.duration_slots or 1) - 1
                end_time = SLOTS[PERIOD_SLOTS[final_index]][1] if final_index < len(PERIOD_SLOTS) else None
                if end_time is not None and end_time.hour * 60 + end_time.minute <= now_minutes:
                    continue
            entry = candidate
            break

        if entry:
            today_start = datetime.combine(now.date(), time.min)
            tomorrow = today_start + timedelta(days=1)
            override = None
            if entry.weekday == today:
                override = db.query(SessionOverride).filter(
                    SessionOverride.entry_id == entry.id,
                    SessionOverride.active.is_(True),
                    SessionOverride.date >= today_start,
                    SessionOverride.date < tomorrow,
                ).order_by(SessionOverride.date.desc()).first()
            room_id = override.room_id if override else entry.base_room_id
            room = db.query(Room).filter(Room.id == room_id).first() if room_id else None
            subject = db.query(Subject).filter(Subject.id == entry.subject_id).first()
            subject_name = (
                f"{subject.code} — {subject.name}"
                if subject
                else "a scheduled class"
            )
            start_time = SLOTS.get(entry.start_slot)
            time_label = (
                f" at {start_time[0].strftime('%H:%M')}"
                if start_time
                else ""
            )
            return {
                "response": (
                    f"Your next scheduled class is {subject_name}{time_label}"
                    + (f" in room {room.code}" if room else " and no classroom is assigned.")
                )
            }

        return {"response": "I couldn't find another class in your timetable."}

    return {"response": "I'm sorry, I can only answer questions about your classroom assignments and changes at the moment."}
