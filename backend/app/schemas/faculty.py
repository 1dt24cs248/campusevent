from datetime import date, time

from pydantic import BaseModel, Field, field_validator, model_validator


class FacultyProfileResponse(BaseModel):
    full_name: str
    employee_id: str | None = None
    email: str
    department: str | None = None
    designation: str | None = None
    active: bool


class FacultySubjectResponse(BaseModel):
    id: str
    code: str
    name: str
    kind: str | None = None
    sections: list[str]
    semesters: list[int]
    demo_data: bool = False


class FacultySectionResponse(BaseModel):
    id: str
    code: str
    name: str
    department: str | None = None
    year: int
    strength: int
    subjects: list[str]
    demo_data: bool = False


class ClassroomRequestCreate(BaseModel):
    subject_id: str
    section_id: str
    requested_date: date
    start_time: time
    end_time: time
    expected_strength: int = Field(ge=1, le=1000)
    preferred_floor_id: str | None = None
    preferred_room_id: str | None = None
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Provide a clear reason for the classroom request.")
        return value

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be later than start time.")
        return self


class ClassroomRequestDecision(BaseModel):
    room_id: str


class ClassroomRequestRejection(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Provide a reason for rejecting the request.")
        return value


class FacultyClassroomOptionsResponse(BaseModel):
    floors: list[dict[str, str | int | None]]
    rooms: list[dict[str, str | int | None]]


class ClassroomRequestResponse(BaseModel):
    id: str
    faculty_id: str
    faculty_name: str
    employee_id: str | None = None
    subject_id: str
    subject_code: str
    subject_name: str
    section_id: str
    section_code: str
    requested_date: date
    start_time: time
    end_time: time
    expected_strength: int
    preferred_floor_id: str | None = None
    preferred_room_id: str | None = None
    preferred_room_code: str | None = None
    reason: str
    status: str
    approved_room_id: str | None = None
    approved_room_code: str | None = None
    decision_reason: str | None = None
    created_at: str


class AttendanceSessionCreate(BaseModel):
    timetable_entry_id: str
    session_date: date


class AttendanceSessionResponse(BaseModel):
    id: str
    timetable_entry_id: str
    session_date: date
    start_time: time
    status: str
    section_code: str
    subject_code: str
    subject_name: str
    records_entered: int


class FacultyEventResponse(BaseModel):
    id: str
    title: str
    category: str
    description: str
    start_dt: str
    end_dt: str
