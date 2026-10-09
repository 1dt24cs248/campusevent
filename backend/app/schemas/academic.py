from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


class AttendanceMark(BaseModel):
    student_id: str
    status: Literal["PRESENT", "ABSENT"]


class AttendanceMarkRequest(BaseModel):
    records: list[AttendanceMark] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_students(self):
        student_ids = [record.student_id for record in self.records]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError("A student can appear only once in an attendance submission.")
        return self


class AttendanceStudentResponse(BaseModel):
    student_id: str
    usn: str | None
    name: str
    status: str | None


class AttendanceSessionDetailResponse(BaseModel):
    id: str
    subject_id: str
    subject_code: str
    subject_name: str
    section_id: str
    section_code: str
    session_date: date
    status: str
    records: list[AttendanceStudentResponse]


class SyllabusModuleCreate(BaseModel):
    subject_id: str
    module_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    sequence: int = Field(ge=1)
    status: Literal["DRAFT", "PUBLISHED"] = "DRAFT"

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title cannot be blank.")
        return normalized


class AcademicResourceCreate(BaseModel):
    subject_id: str
    section_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    resource_type: Literal["NOTES", "PDF", "LINK", "VIDEO", "ASSIGNMENT", "REFERENCE"]
    url: str | None = Field(default=None, max_length=2000)
    status: Literal["DRAFT", "PUBLISHED"] = "DRAFT"

    @model_validator(mode="after")
    def require_resource_content(self):
        if not (self.url and self.url.strip()) and not (self.description and self.description.strip()):
            raise ValueError("Provide a resource URL or text description.")
        return self

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Resource links must use http or https.")
        return normalized


class AssessmentCreate(BaseModel):
    subject_id: str
    section_id: str
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["INTERNAL", "QUIZ", "ASSIGNMENT", "LAB", "PROJECT", "EXAM", "OTHER"]
    date: datetime
    maximum_marks: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    description: str | None = Field(default=None, max_length=5000)
    status: Literal["DRAFT", "PUBLISHED"] = "DRAFT"

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title cannot be blank.")
        return normalized


class MarkEntry(BaseModel):
    student_id: str
    marks: Decimal = Field(ge=0, max_digits=8, decimal_places=2)


class MarkEntryRequest(BaseModel):
    records: list[MarkEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_students(self):
        ids = [record.student_id for record in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("A student can appear only once in a marks submission.")
        return self


class AcademicAnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    audience: list[Literal["STUDENT", "FACULTY", "MANAGEMENT", "ALL"]] = Field(
        default_factory=lambda: ["STUDENT"]
    )
    section_id: str | None = None

    @field_validator("title", "body")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field cannot be blank.")
        return normalized

    @field_validator("audience")
    @classmethod
    def require_audience(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Select at least one audience.")
        return value
