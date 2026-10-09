"""Focused management ERP tests using isolated in-memory SQLite."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.deps import get_db
from app.main import app
from app.models.academic import Department, Faculty, Section, Student, Subject
from app.models.campus import Block, Floor, Room
from app.models.identity import User
from app.models.schedule import TimetableEntry
from app.security import get_password_hash


@pytest.fixture()
def management_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        password_hash = get_password_hash("ManagementPass123")
        db.add_all([
            User(id="manager-user", email="manager@management.test", hashed_password=password_hash,
                 role="MANAGEMENT", display_name="MANAGER001", active=True),
            User(id="student-user", email="student@management.test", hashed_password=password_hash,
                 role="STUDENT", display_name="TEST001 Student", active=True),
            User(id="faculty-user", email="faculty@management.test", hashed_password=password_hash,
                 role="FACULTY", display_name="Faculty A", active=True),
            Department(id="management-dept-a", name="Computer Science"),
            Department(id="management-dept-b", name="Information Science"),
            Block(id="management-block-a", code="A", name="Block A", is_active=True, is_pilot=True),
            Floor(id="management-floor-1", block_id="management-block-a", level=1, name="1st Floor"),
            Floor(id="management-floor-2", block_id="management-block-a", level=2, name="2nd Floor"),
        ])
        db.flush()
        db.add_all([
            Room(
                id="management-room-a101", block_id="management-block-a", floor_id="management-floor-1",
                code="A101", display_name="Classroom A101", aliases=[], resource_type="CLASSROOM",
                capacity=60, allocatable_for_classes=True, reservable_for_events=False,
                facilities=[], status="ACTIVE", is_spare=False,
            ),
            Room(
                id="management-room-a201", block_id="management-block-a", floor_id="management-floor-2",
                code="A201", display_name="Classroom A201", aliases=[], resource_type="CLASSROOM",
                capacity=70, allocatable_for_classes=True, reservable_for_events=False,
                facilities=[], status="ACTIVE", is_spare=False,
            ),
            Section(id="management-section-a", department_id="management-dept-a", code="TEST-A",
                    name="Test Section A", year=3, strength=1, is_synthetic=True),
            Section(id="management-section-b", department_id="management-dept-b", code="TEST-B",
                    name="Test Section B", year=3, strength=1, is_synthetic=True),
            Subject(id="management-subject-a", code="TEST-A1", name="Synthetic Subject A",
                    department_id="management-dept-a", credits=3, is_synthetic=True),
            Faculty(id="management-faculty-a", user_id="faculty-user", department_id="management-dept-a",
                    employee_id="EMP001", name="Faculty A", designation="Lecturer", is_synthetic=True),
        ])
        db.flush()
        db.add_all([
            Student(id="management-student-a", user_id="student-user",
                    section_id="management-section-a", usn="TEST001", semester=5,
                    program="Synthetic B.E. CSE", academic_status="ACTIVE"),
            TimetableEntry(
                id="management-entry-a",
                section_id="management-section-a",
                subject_id="management-subject-a",
                faculty_id="management-faculty-a",
                weekday=date.today().weekday(),
                start_slot="P1",
                duration_slots=1,
                kind="THEORY",
                base_room_id="management-room-a101",
            ),
        ])
        db.commit()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _login(client: TestClient, identifier: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={
        "identifier": identifier,
        "password": "ManagementPass123",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_management_dashboard_counts_and_relationships_are_authoritative(management_client):
    client = management_client
    management = _login(client, "manager@management.test")
    overview = client.get("/api/management/overview", headers=management)
    assert overview.status_code == 200
    assert overview.json()["students"] == {"total": 1, "active": 1}
    assert overview.json()["faculty"] == {"total": 1, "active": 1}
    assert overview.json()["departments"] == 2
    assert overview.json()["today_classes"] == 1

    directory = client.get("/api/management/academics", headers=management)
    assert directory.status_code == 200
    relationship = directory.json()["faculty_subject_section_assignments"]
    assert relationship == [{
        "faculty_id": "management-faculty-a",
        "faculty_name": "Faculty A",
        "subject_id": "management-subject-a",
        "subject_code": "TEST-A1",
        "subject_name": "Synthetic Subject A",
        "section_id": "management-section-a",
        "section_code": "TEST-A",
        "timetable_entry_count": 1,
    }]


def test_scenario_result_includes_decision_rows_and_floor_uses_real_floor_id(management_client):
    management = _login(management_client, "manager@management.test")
    floors = management_client.get("/api/floors", headers=management)
    assert floors.status_code == 200
    assert {floor["id"] for floor in floors.json()} == {
        "management-floor-1", "management-floor-2",
    }

    room_scenario = management_client.post("/api/scenarios", headers=management, json={
        "name": "Close A101",
        "category": "ROOM_UNAVAILABLE",
        "changes": [{
            "type": "ROOM_UNAVAILABLE",
            "payload": {"room_ids": ["management-room-a101"], "time_from": "00:00", "time_to": "23:59"},
        }],
    })
    assert room_scenario.status_code == 200, room_scenario.text
    simulated = management_client.post(
        f"/api/scenarios/{room_scenario.json()['id']}/simulate",
        headers=management,
        json={"strategies": ["MIN_DISRUPTION"], "time_limit_sec": 2},
    )
    assert simulated.status_code == 200, simulated.text
    result = simulated.json()
    row = result["options"][0]["result_rows"][0]
    assert result["affected_count"] == 1
    assert row["timetable_entry_id"] == "management-entry-a"
    assert row["subject_code"] == "TEST-A1"
    assert row["subject_name"] == "Synthetic Subject A"
    assert row["section_code"] == "TEST-A"
    assert row["academic_year"] == 3
    assert row["faculty_name"] == "Faculty A"
    assert row["day"]
    assert row["start_time"] == "09:30"
    assert row["end_time"] == "10:25"
    assert row["original_room_code"] == "A101"
    assert row["assigned_room_code"] == "A201"
    assert row["class_strength"] == 1
    assert row["room_capacity"] == 70
    assert row["status"] == "REASSIGNED"
    assert row["reason"]

    floor_scenario = management_client.post("/api/scenarios", headers=management, json={
        "name": "Close actual first floor",
        "category": "FLOOR_UNAVAILABLE",
        "changes": [{
            "type": "FLOOR_UNAVAILABLE",
            "payload": {"floor_id": "management-floor-1"},
        }],
    })
    assert floor_scenario.status_code == 200, floor_scenario.text
    floor_simulation = management_client.post(
        f"/api/scenarios/{floor_scenario.json()['id']}/simulate",
        headers=management,
        json={"strategies": ["MIN_DISRUPTION"], "time_limit_sec": 2},
    )
    assert floor_simulation.status_code == 200, floor_simulation.text
    floor_result = floor_simulation.json()
    assert floor_result["affected_count"] == 1
    assert floor_result["options"][0]["result_rows"][0]["original_room_code"] == "A101"
    assert floor_result["options"][0]["result_rows"][0]["assigned_room_code"] == "A201"


def test_stress_test_reports_computed_conflicts_utilization_and_capacity(management_client):
    management = _login(management_client, "manager@management.test")
    scenario = management_client.post("/api/scenarios", headers=management, json={
        "name": "Five busiest rooms stress",
        "category": "STRESS_TEST",
        "changes": [{"type": "STRESS_TEST", "payload": {"k": 5}}],
    })
    assert scenario.status_code == 200, scenario.text
    simulated = management_client.post(
        f"/api/scenarios/{scenario.json()['id']}/simulate",
        headers=management,
        json={"strategies": ["MIN_DISRUPTION"], "time_limit_sec": 2},
    )
    assert simulated.status_code == 200, simulated.text
    metrics = simulated.json()["options"][0]["metrics"]
    assert "requested closure of 5 busiest rooms" in metrics["stress_condition"]
    assert metrics["conflict_count_before"] == 0
    assert metrics["conflict_count_after"] == 0
    assert metrics["utilization_before"] == 0.0167
    assert metrics["utilization_after"] == 0.0143
    assert metrics["capacity_pressure_before"] == 0
    assert metrics["capacity_pressure_after"] == 0


def test_management_can_create_update_and_audit_academic_master_data(management_client):
    client = management_client
    management = _login(client, "manager@management.test")

    department = client.post(
        "/api/management/departments",
        headers=management,
        json={"name": "  Applied Computing  "},
    )
    assert department.status_code == 201
    department_id = department.json()["id"]
    assert department.json()["name"] == "Applied Computing"

    section = client.post(
        "/api/management/sections",
        headers=management,
        json={
            "code": "NEW-A",
            "name": "New Section",
            "department_id": department_id,
            "year": 2,
            "strength": 30,
        },
    )
    assert section.status_code == 201
    updated_section = client.patch(
        f"/api/management/sections/{section.json()['id']}",
        headers=management,
        json={"strength": 32},
    )
    assert updated_section.status_code == 200
    assert updated_section.json()["strength"] == 32

    subject = client.post(
        "/api/management/subjects",
        headers=management,
        json={
            "code": "NEW101",
            "name": "Institutional Systems",
            "department_id": department_id,
            "credits": 4,
            "description": "Management-created master record.",
        },
    )
    assert subject.status_code == 201
    updated_subject = client.patch(
        f"/api/management/subjects/{subject.json()['id']}",
        headers=management,
        json={"credits": 5},
    )
    assert updated_subject.status_code == 200

    duplicate_section = client.post(
        "/api/management/sections",
        headers=management,
        json={
            "code": "new-a",
            "name": "Duplicate",
            "department_id": department_id,
            "year": 2,
            "strength": 20,
        },
    )
    assert duplicate_section.status_code == 409
    invalid_subject = client.post(
        "/api/management/subjects",
        headers=management,
        json={"code": "BAD", "name": "Bad Subject", "department_id": "missing"},
    )
    assert invalid_subject.status_code == 422

    audit = client.get("/api/management/audit-log", headers=management)
    assert audit.status_code == 200
    actions = {entry["action"] for entry in audit.json()["items"]}
    assert {"CREATE_DEPARTMENT", "CREATE_SECTION", "UPDATE_SECTION", "CREATE_SUBJECT", "UPDATE_SUBJECT"} <= actions


def test_management_cannot_reassign_department_while_section_has_students_or_classes(management_client):
    client = management_client
    management = _login(client, "manager@management.test")
    response = client.patch(
        "/api/management/sections/management-section-a",
        headers=management,
        json={"department_id": "management-dept-b"},
    )
    assert response.status_code == 409
    assert "Move students and timetable assignments" in response.json()["detail"]


def test_management_endpoints_deny_students_and_faculty(management_client):
    client = management_client
    for identifier in ("student@management.test", "faculty@management.test"):
        headers = _login(client, identifier)
        for path in (
            "/api/management/overview",
            "/api/management/audit-log",
            "/api/management/students",
            "/api/management/faculty",
            "/api/management/academics",
            "/api/management/sections",
            "/api/management/subjects",
        ):
            assert client.get(path, headers=headers).status_code == 403, path
        assert client.post(
            "/api/management/departments",
            headers=headers,
            json={"name": "Forbidden department"},
        ).status_code == 403
