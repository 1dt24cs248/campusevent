from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint

from app.db import Base


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
