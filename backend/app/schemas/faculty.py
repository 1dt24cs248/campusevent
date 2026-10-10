from datetime import date, time
from typing import Literal

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
    assignment_status: str
    weekly_periods: int
    weekly_hours: float
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


class FacultySubjectRequestItemCreate(BaseModel):
    subject_id: str
    preferred_section_ids: list[str] = Field(default_factory=list, max_length=20)
    availability: dict[str, list[str]] = Field(default_factory=dict)
    periods_per_week: int = Field(ge=1, le=7)

    @model_validator(mode="after")
    def validate_preferences(self):
        if len(self.preferred_section_ids) != len(set(self.preferred_section_ids)):
            raise ValueError("Preferred sections must be unique.")
        valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT"}
        valid_slots = {f"P{period}" for period in range(1, 8)}
        for day, slots in self.availability.items():
            if day.upper() not in valid_days:
                raise ValueError("Availability days must be MON through SAT.")
            if len(slots) != len(set(slots)) or any(slot not in valid_slots for slot in slots):
                raise ValueError("Availability must contain unique P1-P7 slots.")
        return self


class FacultySubjectRequestCreate(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    items: list[FacultySubjectRequestItemCreate] = Field(min_length=1, max_length=20)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def unique_subjects(self):
        subject_ids = [item.subject_id for item in self.items]
        if len(subject_ids) != len(set(subject_ids)):
            raise ValueError("A subject can only appear once in a request.")
        return self


class FacultyTeachingEligibilityUpdate(BaseModel):
    academic_years: list[int] = Field(default_factory=list, max_length=8)
    section_ids: list[str] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_unique_targets(self):
        if len(self.academic_years) != len(set(self.academic_years)):
            raise ValueError("Academic years must be unique.")
        if len(self.section_ids) != len(set(self.section_ids)):
            raise ValueError("Eligible sections must be unique.")
        return self


class FacultySubjectRequestDecision(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.reason is not None:
            self.reason = self.reason.strip() or None
        if self.status == "REJECTED" and not self.reason:
            raise ValueError("A reason is required when rejecting a subject request.")
        return self


class FacultySubjectAssignmentCreate(BaseModel):
    section_id: str
    room_id: str
    weekday: int = Field(ge=0, le=5)
    start_slot: str
    duration_slots: int = Field(default=1, ge=1, le=2)

    @field_validator("start_slot")
    @classmethod
    def validate_slot(cls, value: str) -> str:
        if value not in {f"P{period}" for period in range(1, 8)}:
            raise ValueError("Choose a teaching slot from P1 through P7.")
        return value


class FacultySubjectAssignmentsUpdate(BaseModel):
    assignments: list[FacultySubjectAssignmentCreate] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def unique_slots(self):
        slots = [(item.weekday, item.start_slot) for item in self.assignments]
        if len(slots) != len(set(slots)):
            raise ValueError("Assignments cannot repeat the same day and start slot.")
        return self


class FacultySubjectAssignmentResponse(BaseModel):
    id: str
    section_id: str
    section_code: str
    room_id: str
    room_code: str
    weekday: int
    start_slot: str
    duration_slots: int
    published: bool


class FacultySubjectRequestItemResponse(BaseModel):
    id: str
    subject_id: str
    subject_code: str
    subject_name: str
    subject_kind: str | None
    subject_lab_kind: str | None
    required_facilities: list[str]
    preferred_section_ids: list[str]
    preferred_sections: list[dict[str, str]]
    eligible_sections: list[dict[str, str | int]]
    availability: dict[str, list[str]]
    periods_per_week: int
    status: str
    decision_reason: str | None
    assignments: list[FacultySubjectAssignmentResponse]


class FacultySubjectRequestResponse(BaseModel):
    id: str
    faculty_id: str
    faculty_name: str
    department: str | None
    designation: str | None
    note: str | None
    status: str
    created_at: str
    items: list[FacultySubjectRequestItemResponse]


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
