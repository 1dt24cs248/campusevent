from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Boolean, Numeric, Text
from app.db import Base

class MaintenanceTicket(Base):
    __tablename__ = 'maintenance_tickets'
    id = Column(String, primary_key=True)
    code = Column(String, nullable=False)
    room_id = Column(String, ForeignKey('rooms.id'))
    category = Column(String, nullable=False)
    description = Column(String, nullable=False)
    report_type = Column(String, nullable=True)
    location_text = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    status = Column(String, default='Reported')
    reported_by = Column(String, ForeignKey('users.id'))
    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(String, nullable=True)

class TicketHistory(Base):
    __tablename__ = 'ticket_histories'
    id = Column(String, primary_key=True)
    ticket_id = Column(String, ForeignKey('maintenance_tickets.id'))
    old_status = Column(String, nullable=False)
    new_status = Column(String, nullable=False)
    changed_by = Column(String, ForeignKey('users.id'), nullable=True)
    changed_at = Column(DateTime, nullable=False)
    note = Column(String, nullable=True)

class Event(Base):
    __tablename__ = 'events'
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, nullable=False)
    start_dt = Column(DateTime, nullable=False)
    end_dt = Column(DateTime, nullable=False)
    audience = Column(JSON, nullable=True)
    status = Column(String, nullable=False)
    location = Column(String, nullable=True)
    organizer = Column(String, nullable=True)
    created_by = Column(String, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    decision_reason = Column(String, nullable=True)
    decided_by = Column(String, ForeignKey('users.id'), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)

class EventRoom(Base):
    __tablename__ = 'event_rooms'
    event_id = Column(String, ForeignKey('events.id'), primary_key=True)
    room_id = Column(String, ForeignKey('rooms.id'), primary_key=True)

class Opportunity(Base):
    __tablename__ = 'opportunities'
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    organizer = Column(String, nullable=False)
    description = Column(String, nullable=False)
    eligibility_years = Column(JSON, nullable=False)
    eligibility_depts = Column(JSON, nullable=False)
    deadline = Column(DateTime, nullable=True)
    link = Column(String, nullable=True)

class Announcement(Base):
    __tablename__ = 'announcements'
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    body = Column(String, nullable=False)
    audience = Column(JSON, nullable=True)
    section_id = Column(String, ForeignKey('sections.id'), nullable=True)
    created_by = Column(String, ForeignKey('users.id'), nullable=True)
    published_at = Column(DateTime, nullable=False)

class Assessment(Base):
    __tablename__ = 'assessments'
    id = Column(String, primary_key=True)
    section_id = Column(String, ForeignKey('sections.id'))
    subject_id = Column(String, ForeignKey('subjects.id'), nullable=True)
    title = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    kind = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    maximum_marks = Column(Numeric(8, 2), nullable=True)
    created_by = Column(String, ForeignKey('users.id'), nullable=True)
    status = Column(String, nullable=False, default="DRAFT")
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    is_synthetic = Column(Boolean, nullable=False, default=False)
    provenance = Column(String, nullable=True)

class CampusFAQ(Base):
    __tablename__ = 'campus_faqs'
    id = Column(String, primary_key=True)
    topic = Column(String, nullable=False)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    approved = Column(Boolean, default=False)
