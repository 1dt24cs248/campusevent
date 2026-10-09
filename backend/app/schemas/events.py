from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


EventCategory = Literal[
    "HACKATHON",
    "TECHNICAL_EVENT",
    "WORKSHOP",
    "SEMINAR",
    "CONFERENCE",
    "GUEST_LECTURE",
    "PLACEMENT",
    "CLUB_ACTIVITY",
    "CULTURAL",
    "SPORTS",
    "WEBINAR",
    "CO_CURRICULAR",
    "MEETING",
    "OTHER",
]
EventAudience = Literal["STUDENTS", "FACULTY", "STUDENTS_AND_FACULTY"]


class EventProposalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: EventCategory
    description: str = Field(min_length=1, max_length=4000)
    start_dt: datetime
    end_dt: datetime
    location: str = Field(min_length=1, max_length=250)
    organizer: str = Field(min_length=1, max_length=200)
    audience: EventAudience
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("title", "description", "location", "organizer")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

class EventRejection(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Provide a reason for rejecting the event proposal.")
        return value


class EventDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class CampusEventResponse(BaseModel):
    id: str
    title: str
    category: str
    description: str
    start_dt: datetime
    end_dt: datetime
    location: str | None = None
    organizer: str | None = None
    audience: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    decision_reason: str | None = None
    notes: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
