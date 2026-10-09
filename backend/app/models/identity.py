from sqlalchemy import Column, String, DateTime, JSON, Boolean
from app.db import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    can_view_incidents = Column(Boolean, default=False)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    role = Column(String, nullable=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    ts = Column('ts', DateTime, nullable=False)

class Setting(Base):
    __tablename__ = 'settings'
    id = Column(String, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(JSON, nullable=False)
