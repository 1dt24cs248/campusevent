"""Syllabus, learning resources, and published student marks."""
from sqlalchemy import (
    Column,
    DateTime,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from app.db import Base


class SyllabusModule(Base):
    __tablename__ = "syllabus_modules"
    __table_args__ = (
        UniqueConstraint("subject_id", "module_number", name="uq_syllabus_subject_module"),
    )

    id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False, index=True)
    module_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    sequence = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="DRAFT")
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    is_synthetic = Column(Boolean, nullable=False, default=False)
    provenance = Column(String, nullable=True)


class AcademicResource(Base):
    __tablename__ = "academic_resources"

    id = Column(String, primary_key=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False, index=True)
    section_id = Column(String, ForeignKey("sections.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    resource_type = Column(String, nullable=False)
    url = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="DRAFT")
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    is_synthetic = Column(Boolean, nullable=False, default=False)
    provenance = Column(String, nullable=True)


class AcademicMark(Base):
    __tablename__ = "academic_marks"
    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id", name="uq_academic_mark_student_assessment"),
    )

    id = Column(String, primary_key=True)
    assessment_id = Column(String, ForeignKey("assessments.id"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    marks = Column(Numeric(8, 2), nullable=False)
    updated_by = Column(String, ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime, nullable=False)
