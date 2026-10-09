from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from app.db import Base

class RoomUnavailability(Base):
    __tablename__ = 'room_unavailability'
    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey('rooms.id'))
    start_dt = Column(DateTime, nullable=False)
    end_dt = Column(DateTime, nullable=False)
    reason_type = Column(String, nullable=False)
    ref_type = Column(String, nullable=True)
    ref_id = Column(String, nullable=True)
    version_id = Column(String, ForeignKey('published_versions.id'), nullable=True)
    active = Column(Boolean, default=True)
    created_by = Column(String, ForeignKey('users.id'), nullable=True)
