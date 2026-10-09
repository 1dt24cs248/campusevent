"""Student self-service API schemas."""
from typing import Optional

from pydantic import BaseModel, Field


class StudentProfileResponse(BaseModel):
    full_name: str
    usn: Optional[str] = None
    email: str
    phone: Optional[str] = None
    program: Optional[str] = None
    department: Optional[str] = None
    semester: Optional[int] = None
    section: Optional[str] = None
    admission_year: Optional[int] = None
    academic_status: Optional[str] = None


class StudentSubjectResponse(BaseModel):
    id: str
    code: str
    name: str
    kind: Optional[str] = None
    faculty: list[str]
    demo_data: bool = False
    credits: int | None = None
    description: str | None = None
    attendance: "StudentAttendanceSummary | None" = None
    upcoming_assessments: int = 0
    resources_count: int = 0


class StudentAttendanceSummary(BaseModel):
    total_classes: int
    present: int
    absent: int
    percentage: float | None = None


StudentSubjectResponse.model_rebuild()


class StudentSyllabusModule(BaseModel):
    module_number: int
    title: str
    description: str | None = None
    sequence: int
    is_synthetic: bool = False


class StudentAcademicResource(BaseModel):
    id: str
    title: str
    description: str | None = None
    resource_type: str
    url: str | None = None
    is_synthetic: bool = False


class StudentAssessment(BaseModel):
    id: str
    title: str
    kind: str
    date: str
    description: str | None = None
    maximum_marks: float | None = None
    status: str
    is_synthetic: bool = False


class StudentAnnouncement(BaseModel):
    id: str
    title: str
    body: str
    published_at: str


class StudentMark(BaseModel):
    assessment_id: str
    assessment_title: str
    kind: str
    date: str
    marks: float
    maximum_marks: float
    percentage: float


class StudentAcademicsResponse(BaseModel):
    subjects: list[StudentSubjectResponse]
    message: Optional[str] = None
    program: str | None = None
    department: str | None = None
    semester: int | None = None
    section: str | None = None
    attendance_available: bool = False
    upcoming_assessments: list[StudentAssessment] = Field(default_factory=list)
    announcements: list[StudentAnnouncement] = Field(default_factory=list)


class StudentSubjectDetailResponse(StudentSubjectResponse):
    section: str
    syllabus_published: bool = False
    resources_published: bool = False
    syllabus: list[StudentSyllabusModule] = Field(default_factory=list)
    resources: list[StudentAcademicResource] = Field(default_factory=list)
    assessments: list[StudentAssessment] = Field(default_factory=list)
    marks: list[StudentMark] = Field(default_factory=list)
    attendance_message: str | None = None
