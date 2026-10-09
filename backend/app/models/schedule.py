from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Boolean, JSON
from app.db import Base

class TimetableEntry(Base):
    __tablename__ = 'timetable_entries'
    id = Column(String, primary_key=True)
    section_id = Column(String, ForeignKey('sections.id'))
    subject_id = Column(String, ForeignKey('subjects.id'))
    faculty_id = Column(String, ForeignKey('faculties.id'))
    weekday = Column(Integer, nullable=False)
    start_slot = Column(String, nullable=False)
    duration_slots = Column(Integer, default=1)
    kind = Column(String, nullable=False)
    required_room_type = Column(String, nullable=True)
    required_lab_kind = Column(String, nullable=True)
    required_facilities = Column(JSON, default=list)
    base_room_id = Column(String, ForeignKey('rooms.id'), nullable=True)
    provenance = Column(String, nullable=True)

class SessionOverride(Base):
    __tablename__ = 'session_overrides'
    id = Column(String, primary_key=True)
    entry_id = Column(String, ForeignKey('timetable_entries.id'))
    date = Column(DateTime, nullable=False)
    room_id = Column(String, ForeignKey('rooms.id'))
    start_slot_override = Column(String, nullable=True)
    old_room_id = Column(String, ForeignKey('rooms.id'), nullable=True)
    version_id = Column(String, ForeignKey('published_versions.id'), nullable=True)
    reason = Column(String, nullable=True)
    active = Column(Boolean, default=True)

class SectionStrengthHistory(Base):
    __tablename__ = 'section_strength_histories'
    id = Column(String, primary_key=True)
    section_id = Column(String, ForeignKey('sections.id'))
    recorded_at = Column(DateTime, nullable=False)
    old_strength = Column(Integer, nullable=False)
    new_strength = Column(Integer, nullable=False)
    changed_by = Column(String, nullable=True)
    version_id = Column(String, ForeignKey('published_versions.id'), nullable=True)
