from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON
from app.db import Base

class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(String, primary_key=True)
    audience_type = Column(String, nullable=False)
    audience_id = Column(String, nullable=False)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(String, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

class NotificationRead(Base):
    __tablename__ = 'notification_reads'
    notification_id = Column(String, ForeignKey('notifications.id'), primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), primary_key=True)
    read_at = Column(DateTime, nullable=False)
