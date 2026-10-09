from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Boolean
from app.db import Base

class Incident(Base):
    __tablename__ = 'incidents'
    id = Column(String, primary_key=True)
    code = Column(String, nullable=False)
    reporter_user_id = Column(String, ForeignKey('users.id'))
    category = Column(String, nullable=False)
    description_enc = Column(String, nullable=False)
    location_enc = Column(String, nullable=True)
    location_room_id = Column(String, ForeignKey('rooms.id'), nullable=True)
    incident_dt = Column(DateTime, nullable=False)
    evidence_path = Column(String, nullable=True)
    status = Column(String, default='Submitted')
    anonymous = Column(Boolean, nullable=True)
    severity = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    assigned_to = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(String, nullable=True)

class IncidentStatusHistory(Base):
    __tablename__ = 'incident_status_histories'
    id = Column(String, primary_key=True)
    incident_id = Column(String, ForeignKey('incidents.id'))
    old_status = Column(String, nullable=False)
    new_status = Column(String, nullable=False)
    changed_by = Column(String, ForeignKey('users.id'), nullable=True)
    changed_at = Column(DateTime, nullable=False)
    note = Column(String, nullable=True)

class EmergencyConfig(Base):
    __tablename__ = 'emergency_configs'
    id = Column(String, primary_key=True)
    emergency_number = Column(String, default='NOT CONFIGURED')
    contacts = Column(JSON, default=list)
    test_mode = Column(Boolean, default=True)


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    relationship = Column("relationship", String, nullable=False)
    phone_number = Column(String, nullable=False)


class EmergencyEvent(Base):
    __tablename__ = 'emergency_events'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    created_at = Column(DateTime, nullable=False)
    location_text = Column(String, nullable=True)
    location_shared = Column(Boolean, default=False)
    status = Column(String, default='SENT')
    code = Column(String, nullable=True)
    category = Column(String, nullable=True)
    description_enc = Column(String, nullable=True)
    room_id = Column(String, ForeignKey('rooms.id'), nullable=True)
    severity = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    assigned_to = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(String, nullable=True)
