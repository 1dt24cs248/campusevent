from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text, Time, UniqueConstraint

from app.db import Base


class FacultySubjectRequest(Base):
    __tablename__ = "faculty_subject_requests"

    id = Column(String, primary_key=True)
    faculty_id = Column(String, ForeignKey("faculties.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="PENDING", index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class FacultySubjectRequestItem(Base):
    __tablename__ = "faculty_subject_request_items"

    id = Column(String, primary_key=True)
    request_id = Column(String, ForeignKey("faculty_subject_requests.id"), nullable=False, index=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    preferred_section_ids = Column(JSON, nullable=False, default=list)
    availability = Column(JSON, nullable=False, default=dict)
    periods_per_week = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="PENDING", index=True)
    decision_reason = Column(Text, nullable=True)
    decided_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class FacultySubjectAssignment(Base):
    __tablename__ = "faculty_subject_assignments"
    __table_args__ = (
        UniqueConstraint(
            "request_item_id", "weekday", "start_slot",
            name="uq_faculty_subject_assignment_item_slot",
        ),
    )

    id = Column(String, primary_key=True)
    request_item_id = Column(
        String, ForeignKey("faculty_subject_request_items.id"), nullable=False, index=True
    )
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    weekday = Column(Integer, nullable=False)
    start_slot = Column(String, nullable=False)
    duration_slots = Column(Integer, nullable=False, default=1)
    timetable_entry_id = Column(String, ForeignKey("timetable_entries.id"), nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False)


class ClassroomRequest(Base):
    __tablename__ = "classroom_requests"

    id = Column(String, primary_key=True)
    faculty_id = Column(String, ForeignKey("faculties.id"), nullable=False, index=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    requested_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    expected_strength = Column(Integer, nullable=False)
    preferred_floor_id = Column(String, ForeignKey("floors.id"), nullable=True)
    preferred_room_id = Column(String, ForeignKey("rooms.id"), nullable=True)
    reason = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING", index=True)
    approved_room_id = Column(String, ForeignKey("rooms.id"), nullable=True)
    decision_reason = Column(String, nullable=True)
    decided_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        UniqueConstraint("timetable_entry_id", "session_date", name="uq_attendance_entry_date"),
    )

    id = Column(String, primary_key=True)
    faculty_id = Column(String, ForeignKey("faculties.id"), nullable=False, index=True)
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    timetable_entry_id = Column(String, ForeignKey("timetable_entries.id"), nullable=False)
    session_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    status = Column(String, nullable=False, default="OPEN")
    created_at = Column(DateTime, nullable=False)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
    )

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    status = Column(String, nullable=False)
    marked_at = Column(DateTime, nullable=False)
    marked_by = Column(String, ForeignKey("users.id"), nullable=False)
