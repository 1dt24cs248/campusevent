"""Isolated event workflow, audience privacy, and notification tests."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event as sqlalchemy_event
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.clock import get_now
from app.db import Base
from app.deps import get_db
from app.event_schema import migrate_event_columns
from app.main import app
from app.models.academic import Department, Faculty, Section, Student
from app.models.identity import User
from app.security import get_password_hash


@pytest.fixture()
def event_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @sqlalchemy_event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        db.add_all([
            User(id="event-faculty-a", email="faculty.a@events.test", hashed_password=get_password_hash("FacultyPass123"), role="FACULTY", display_name="Faculty Alpha", active=True),
            User(id="event-faculty-b", email="faculty.b@events.test", hashed_password=get_password_hash("FacultyPass123"), role="FACULTY", display_name="Faculty Beta", active=True),
            User(id="event-student-a", email="student.a@events.test", hashed_password=get_password_hash("StudentPass123"), role="STUDENT", display_name="Student Alpha", active=True),
            User(id="event-student-b", email="student.b@events.test", hashed_password=get_password_hash("StudentPass123"), role="STUDENT", display_name="Student Beta", active=True),
            User(id="event-management", email="manager@events.test", hashed_password=get_password_hash("ManagerPass123"), role="MANAGEMENT", display_name="Events Manager", active=True),
            Department(id="event-department", name="Computer Science"),
            Section(id="event-section-a", department_id="event-department", code="5CSE-A", name="Fifth Semester CSE-A", year=3, strength=50),
            Section(id="event-section-b", department_id="event-department", code="5CSE-B", name="Fifth Semester CSE-B", year=3, strength=48),
        ])
        db.flush()
        db.add_all([
            Faculty(id="event-faculty-record-a", user_id="event-faculty-a", department_id="event-department", name="Faculty Alpha", employee_id="EMP001"),
            Faculty(id="event-faculty-record-b", user_id="event-faculty-b", department_id="event-department", name="Faculty Beta", employee_id="EMP002"),
            Student(id="event-student-record-a", user_id="event-student-a", section_id="event-section-a", usn="TEST001"),
            Student(id="event-student-record-b", user_id="event-student-b", section_id="event-section-b", usn="TEST002"),
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


def auth_headers(client: TestClient, identifier: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def proposal_body(**overrides) -> dict:
    start = get_now() + timedelta(days=3)
    body = {
        "title": "Synthetic Campus Workshop",
        "category": "WORKSHOP",
        "description": "Synthetic validation event; not a real campus event.",
        "start_dt": start.replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
        "end_dt": start.replace(hour=11, minute=0, second=0, microsecond=0).isoformat(),
        "location": "Synthetic Room S101",
        "organizer": "Synthetic Faculty Validation",
        "audience": "STUDENTS",
        "notes": "Synthetic private management note.",
    }
    body.update(overrides)
    return body


def test_faculty_proposal_is_private_until_management_publishes_to_audience(event_client):
    client = event_client
    faculty_a = auth_headers(client, "EMP001", "FacultyPass123")
    faculty_b = auth_headers(client, "EMP002", "FacultyPass123")
    student_a = auth_headers(client, "TEST001", "StudentPass123")
    student_b = auth_headers(client, "TEST002", "StudentPass123")
    manager = auth_headers(client, "manager@events.test", "ManagerPass123")

    proposal = client.post("/api/faculty/events", headers=faculty_a, json=proposal_body())
    assert proposal.status_code == 201, proposal.text
    proposal_data = proposal.json()
    event_id = proposal_data["id"]
    assert client.post("/api/faculty/events", headers=faculty_a, json=proposal_body()).status_code == 409
    assert proposal_data["status"] == "PENDING_APPROVAL"
    assert proposal_data["audience"] == "STUDENTS"
    assert proposal_data["notes"] == "Synthetic private management note."
    assert client.get("/api/faculty/events/proposals", headers=faculty_a).json()[0]["id"] == event_id
    assert client.get("/api/faculty/events/proposals", headers=faculty_b).json() == []
    assert client.get(f"/api/events/{event_id}", headers=faculty_b).status_code == 404
    assert client.get("/api/management/events", headers=manager).json()[0]["created_by_name"] == "Faculty Alpha"
    assert client.get("/api/management/events", headers=faculty_a).status_code == 403
    assert client.get("/api/management/events", headers=student_a).status_code == 403
    assert client.post(f"/api/management/events/{event_id}/approve", headers=faculty_a).status_code == 403
    assert client.get("/api/events", headers=student_a).json() == []
    assert client.get("/api/events", headers=faculty_a).json() == []

    approved = client.post(f"/api/management/events/{event_id}/approve", headers=manager)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert any(
        item["title"] == "Event proposal: Synthetic Campus Workshop"
        for item in client.get("/api/notifications", headers=faculty_a).json()
    )
    assert not any(
        item["title"] == "Event proposal: Synthetic Campus Workshop"
        for item in client.get("/api/notifications", headers=faculty_b).json()
    )

    published = client.post(f"/api/management/events/{event_id}/publish", headers=manager)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "PUBLISHED"
    for student in (student_a, student_b):
        listed = client.get("/api/events", headers=student).json()
        assert [item["id"] for item in listed] == [event_id]
        assert listed[0]["notes"] is None
        assert client.get(f"/api/events/{event_id}", headers=student).status_code == 200
        assert any(
            item["title"] == "New event: Synthetic Campus Workshop"
            for item in client.get("/api/notifications", headers=student).json()
        )
    assert client.get("/api/events", headers=faculty_a).json() == []
    assert client.get(f"/api/events/{event_id}", headers=faculty_a).status_code == 404
    assert not any(
        item["title"] == "New event: Synthetic Campus Workshop"
        for item in client.get("/api/notifications", headers=faculty_a).json()
    )
    owner_proposals = client.get("/api/faculty/events/proposals", headers=faculty_a).json()
    assert owner_proposals[0]["status"] == "PUBLISHED"


def test_faculty_only_event_is_not_visible_to_students(event_client):
    client = event_client
    faculty = auth_headers(client, "EMP002", "FacultyPass123")
    student = auth_headers(client, "TEST002", "StudentPass123")
    manager = auth_headers(client, "manager@events.test", "ManagerPass123")
    created = client.post(
        "/api/faculty/events",
        headers=faculty,
        json=proposal_body(title="Synthetic Faculty Seminar", audience="FACULTY"),
    )
    event_id = created.json()["id"]
    assert client.post(f"/api/management/events/{event_id}/approve", headers=manager).status_code == 200
    assert client.post(f"/api/management/events/{event_id}/publish", headers=manager).status_code == 200

    faculty_events = client.get("/api/events", headers=faculty).json()
    assert [item["id"] for item in faculty_events] == [event_id]
    assert client.get("/api/events", headers=student).json() == []
    assert client.get(f"/api/events/{event_id}", headers=student).status_code == 404
    assert any(
        item["title"] == "New event: Synthetic Faculty Seminar"
        for item in client.get("/api/notifications", headers=faculty).json()
    )
    assert not any(
        item["title"] == "New event: Synthetic Faculty Seminar"
        for item in client.get("/api/notifications", headers=student).json()
    )


def test_rejection_reason_and_event_validation_are_enforced(event_client):
    client = event_client
    faculty = auth_headers(client, "EMP001", "FacultyPass123")
    manager = auth_headers(client, "manager@events.test", "ManagerPass123")

    invalid_range = proposal_body()
    invalid_range["end_dt"] = invalid_range["start_dt"]
    assert client.post("/api/faculty/events", headers=faculty, json=invalid_range).status_code == 422
    assert client.post(
        "/api/faculty/events",
        headers=faculty,
        json=proposal_body(title="   "),
    ).status_code == 422
    assert client.post("/api/faculty/events", headers=manager, json=proposal_body()).status_code == 403

    created = client.post("/api/faculty/events", headers=faculty, json=proposal_body())
    event_id = created.json()["id"]
    rejected = client.post(
        f"/api/management/events/{event_id}/reject",
        headers=manager,
        json={"reason": "Please choose a different campus date."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["decision_reason"] == "Please choose a different campus date."
    owner_events = client.get("/api/faculty/events/proposals", headers=faculty).json()
    assert owner_events[0]["decision_reason"] == "Please choose a different campus date."
    assert any(
        "was rejected" in item["body"]
        for item in client.get("/api/notifications", headers=faculty).json()
    )
    assert client.post(f"/api/management/events/{event_id}/publish", headers=manager).status_code == 409


def test_legacy_event_schema_migration_preserves_existing_rows():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE events (id VARCHAR PRIMARY KEY, title VARCHAR NOT NULL, "
            "category VARCHAR NOT NULL, description VARCHAR NOT NULL, start_dt DATETIME NOT NULL, "
            "end_dt DATETIME NOT NULL, audience JSON, status VARCHAR NOT NULL)"
        ))
        connection.execute(text(
            "INSERT INTO events (id, title, category, description, start_dt, end_dt, audience, status) "
            "VALUES ('legacy-event', 'Legacy Event', 'MEETING', 'Existing row', "
            "'2030-01-01 10:00:00', '2030-01-01 11:00:00', '[\"FACULTY\"]', 'PUBLISHED')"
        ))
    migrate_event_columns(engine)
    migrate_event_columns(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("events")}
    assert {"location", "organizer", "created_by", "created_at", "updated_at", "notes"}.issubset(columns)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT id, title, status FROM events")).one()
    assert row == ("legacy-event", "Legacy Event", "PUBLISHED")
    engine.dispose()
