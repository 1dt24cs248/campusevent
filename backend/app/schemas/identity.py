"""Schemas for institutional student and faculty identity management."""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


AcademicStatus = Literal["ACTIVE", "ON_LEAVE", "GRADUATED", "WITHDRAWN"]


def _required_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This field cannot be empty.")
    return value


def _email(value: str) -> str:
    value = _required_text(value).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Enter a valid college email address.")
    return value


class StudentCreate(BaseModel):
    usn: str = Field(min_length=1, max_length=40)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    department_id: str
    program: str = Field(min_length=1, max_length=120)
    semester: int = Field(ge=1, le=8)
    section_id: str
    admission_year: int = Field(ge=1900, le=2100)
    academic_status: AcademicStatus = "ACTIVE"
    profile: dict[str, str] | None = None

    @field_validator("usn")
    @classmethod
    def normalize_usn(cls, value: str) -> str:
        return _required_text(value).upper()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _email(value)

    @field_validator("name", "program")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("phone")
    @classmethod
    def trim_phone(cls, value: str | None) -> str | None:
        return _required_text(value) if value is not None else None


class StudentUpdate(BaseModel):
    usn: str | None = Field(default=None, min_length=1, max_length=40)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    department_id: str | None = None
    program: str | None = Field(default=None, min_length=1, max_length=120)
    semester: int | None = Field(default=None, ge=1, le=8)
    section_id: str | None = None
    admission_year: int | None = Field(default=None, ge=1900, le=2100)
    academic_status: AcademicStatus | None = None
    profile: dict[str, str] | None = None
    active: bool | None = None

    @field_validator("usn")
    @classmethod
    def normalize_usn(cls, value: str | None) -> str | None:
        return _required_text(value).upper() if value is not None else None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return _email(value) if value is not None else None

    @field_validator("name", "program")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return _required_text(value) if value is not None else None


class FacultyCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=40)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=160)
    department_id: str
    designation: str = Field(min_length=1, max_length=120)

    @field_validator("employee_id")
    @classmethod
    def normalize_employee_id(cls, value: str) -> str:
        return _required_text(value).upper()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _email(value)

    @field_validator("name", "designation")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return _required_text(value)


class FacultyUpdate(BaseModel):
    employee_id: str | None = Field(default=None, min_length=1, max_length=40)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    department_id: str | None = None
    designation: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None

    @field_validator("employee_id")
    @classmethod
    def normalize_employee_id(cls, value: str | None) -> str | None:
        return _required_text(value).upper() if value is not None else None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return _email(value) if value is not None else None

    @field_validator("name", "designation")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return _required_text(value) if value is not None else None


class PasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class StudentResponse(BaseModel):
    id: str
    user_id: str
    usn: str | None
    email: str
    name: str
    phone: str | None
    department_id: str
    department: str
    program: str | None
    semester: int | None
    section_id: str
    section: str
    admission_year: int | None
    academic_status: str | None
    profile: dict[str, str] | None
    active: bool
    synthetic_section: bool


class FacultyResponse(BaseModel):
    id: str
    user_id: str | None
    employee_id: str | None
    email: str | None
    name: str | None
    department_id: str
    department: str
    designation: str | None
    subjects_taught: list[str]
    sections_handled: list[str]
    active: bool
    account_provisioned: bool
    synthetic: bool
