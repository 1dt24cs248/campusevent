"""Auth schemas: login request, token response, user info."""
from pydantic import BaseModel
from pydantic import AliasChoices, Field
from typing import Optional


class LoginRequest(BaseModel):
    identifier: str = Field(validation_alias=AliasChoices("identifier", "email"))
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    display_name: Optional[str] = None
    active: bool = True
    student_id: Optional[str] = None
    usn: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[str] = None
    department: Optional[str] = None
    program: Optional[str] = None
    semester: Optional[int] = None
    section_id: Optional[str] = None
    section: Optional[str] = None
    admission_year: Optional[int] = None
    academic_status: Optional[str] = None
    profile: Optional[dict[str, str]] = None
    faculty_id: Optional[str] = None
    employee_id: Optional[str] = None
    designation: Optional[str] = None

    class Config:
        from_attributes = True
