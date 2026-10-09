from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, JSON, Index, Text
from sqlalchemy.orm import relationship
from app.db import Base

class Department(Base):
    __tablename__ = 'departments'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

class Section(Base):
    __tablename__ = 'sections'
    id = Column(String, primary_key=True)
    department_id = Column(String, ForeignKey('departments.id'))
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    strength = Column(Integer, nullable=False)
    strength_provenance = Column(String, nullable=True)
    home_room_id = Column(String, ForeignKey('rooms.id'), nullable=True)
    is_synthetic = Column(Boolean, default=False)
    provenance = Column(String, nullable=True)

class Subject(Base):
    __tablename__ = 'subjects'
    id = Column(String, primary_key=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    credits = Column(Integer, nullable=True)
    department_id = Column(String, ForeignKey('departments.id'))
    kind = Column(String, nullable=True)
    required_facilities = Column(JSON, default=list)
    lab_kind = Column(String, nullable=True)
    is_synthetic = Column(Boolean, default=False)

class Faculty(Base):
    __tablename__ = 'faculties'
    __table_args__ = (
        Index('uq_faculties_employee_id', 'employee_id', unique=True),
        Index('uq_faculties_user_id', 'user_id', unique=True),
    )

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    department_id = Column(String, ForeignKey('departments.id'))
    name = Column(String, nullable=True)
    employee_id = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    is_synthetic = Column(Boolean, default=False)

class Student(Base):
    __tablename__ = 'students'
    __table_args__ = (
        Index('uq_students_usn', 'usn', unique=True),
        Index('uq_students_user_id', 'user_id', unique=True),
    )

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    section_id = Column(String, ForeignKey('sections.id'))
    usn = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    program = Column(String, nullable=True)
    semester = Column(Integer, nullable=True)
    admission_year = Column(Integer, nullable=True)
    academic_status = Column(String, nullable=True)
    profile = Column(JSON, nullable=True)
    anon_code = Column(String, nullable=True)
