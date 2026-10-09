"""Schemas for timetable, scenarios, and state APIs."""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


# --- Timetable Schemas ---

class TimetableEntryResponse(BaseModel):
    id: str
    section_id: str
    section_code: Optional[str] = None
    section_name: Optional[str] = None
    subject_id: Optional[str] = None
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    faculty_id: Optional[str] = None
    faculty_name: Optional[str] = None
    weekday: int
    start_slot: str
    effective_start_slot: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_slots: int
    kind: str
    required_room_type: Optional[str] = None
    base_room_id: Optional[str] = None
    base_room_code: Optional[str] = None
    effective_room_id: Optional[str] = None
    effective_room_code: Optional[str] = None
    room_changed: bool = False
    is_extra_class: bool = False
    change_reason: Optional[str] = None
    provenance: Optional[str] = None
    is_synthetic: bool = False

    class Config:
        from_attributes = True


class StateOverviewResponse(BaseModel):
    total_rooms: int
    allocatable_rooms: int
    total_entries: int
    allocated: int
    at_risk: int
    floating: int
    capacity_violations: int
    total_sections: int
    total_faculty: int


# --- Scenario Schemas ---

class ScenarioChangeCreate(BaseModel):
    type: str
    payload: Dict[str, Any]


class ScenarioCreate(BaseModel):
    name: str
    category: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    objective_preset: Optional[str] = None
    changes: List[ScenarioChangeCreate]


class ScenarioResponse(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    status: str
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    base_version_id: Optional[str] = None
    changes: List[Dict[str, Any]] = []

    class Config:
        from_attributes = True


class SimulationRequest(BaseModel):
    strategies: Optional[List[str]] = None
    time_limit_sec: Optional[int] = 8


class SolverResultResponse(BaseModel):
    run_id: Optional[str] = None
    status: str
    option_label: str
    strategy: str
    assignments: Dict[str, str] = {}
    unresolved: List[Dict[str, Any]] = []
    result_rows: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
    explanations: Dict[str, str] = {}
    recovery: List[Dict[str, Any]] = []
    solve_ms: int = 0


class SimulationResponse(BaseModel):
    scenario_id: str
    affected_count: int
    change_descriptions: List[str]
    options: List[SolverResultResponse]


# --- Approval/Publish Schemas ---

class ApprovalRequest(BaseModel):
    run_id: str
    comment: Optional[str] = None


class PublishResponse(BaseModel):
    version_id: str
    version_no: int
    summary: str
    overrides_created: int
    notifications_created: int


class VersionResponse(BaseModel):
    id: str
    version_no: int
    scenario_id: Optional[str] = None
    scenario_name: Optional[str] = None
    published_by: Optional[str] = None
    published_at: Optional[datetime] = None
    summary: Optional[str] = None
    reverted: bool = False

    class Config:
        from_attributes = True


# --- Notification Schemas ---

class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    body: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    read: bool = False

    class Config:
        from_attributes = True
