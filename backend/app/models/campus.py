from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db import Base

class Block(Base):
    __tablename__ = 'blocks'
    id = Column(String, primary_key=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_pilot = Column(Boolean, default=False)
    floors = relationship("Floor", back_populates="block")

class Floor(Base):
    __tablename__ = 'floors'
    id = Column(String, primary_key=True)
    block_id = Column(String, ForeignKey('blocks.id'))
    level = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    label = Column(String, nullable=True)
    block = relationship("Block", back_populates="floors")
    rooms = relationship("Room", back_populates="floor")

class Room(Base):
    __tablename__ = 'rooms'
    id = Column(String, primary_key=True)
    block_id = Column(String, ForeignKey('blocks.id'))
    floor_id = Column(String, ForeignKey('floors.id'))
    code = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    aliases = Column(JSON, default=list)
    resource_type = Column(String, nullable=False)
    department = Column(String, nullable=True)
    capacity = Column(Integer, nullable=True)
    capacity_provenance = Column(String, nullable=True)
    allocatable_for_classes = Column(Boolean, default=True)
    reservable_for_events = Column(Boolean, default=False)
    lab_kind = Column(String, nullable=True)
    facilities = Column(JSON, default=list)
    accessible = Column(Boolean, nullable=True)
    status = Column(String, default='ACTIVE')
    is_spare = Column(Boolean, default=False)
    provenance = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    
    floor = relationship("Floor", back_populates="rooms")
    block = relationship("Block")
