"""Faculty portal isolation, attendance foundation, and classroom request tests."""
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.deps import get_db
from app.main import app
from app.models.academic import Department, Faculty, Section, Student, Subject
from app.models.availability import RoomUnavailability
from app.models.campus import Block, Floor, Room
from app.models.faculty_work import AttendanceSession
from app.models.identity import User
from app.models.schedule import TimetableEntry
from app.security import get_password_hash


@pytest.fixture()
def faculty_portal_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    weekday = date.today().weekday()
    with session_factory() as db:
        db.add_all([
            User(
                id="faculty-user-a",
                email="faculty.a@faculty.test",
                hashed_password=get_password_hash("FacultyPass123"),
                role="FACULTY",
                display_name="Faculty Alpha",
                active=True,
            ),
            User(
                id="faculty-user-b",
                email="faculty.b@faculty.test",
                hashed_password=get_password_hash("FacultyPass123"),
                role="FACULTY",
                display_name="Faculty Beta",
                active=True,
            ),
            User(
                id="faculty-manager",
                email="manager@faculty.test",
                hashed_password=get_password_hash("ManagerPass123"),
                role="MANAGEMENT",
                display_name="Manager",
                active=True,
            ),
            User(
                id="faculty-student",
                email="student@faculty.test",
                hashed_password=get_password_hash("StudentPass123"),
                role="STUDENT",
                display_name="Student",
                active=True,
            ),
            Department(id="faculty-dept-cse", name="Computer Science"),
            Department(id="faculty-dept-ise", name="Information Science"),
            Section(
                id="faculty-section-a",
                department_id="faculty-dept-cse",
                code="5CSE-A",
                name="Fifth Semester CSE-A",
                year=3,
                strength=50,
            ),
            Section(
                id="faculty-section-b",
                department_id="faculty-dept-ise",
                code="5ISE-B",
                name="Fifth Semester ISE-B",
                year=3,
                strength=40,
            ),
            Block(id="faculty-block", code="A", name="Block A"),
        ])
        db.flush()
        db.add_all([
            Faculty(
                id="faculty-record-a",
                user_id="faculty-user-a",
                department_id="faculty-dept-cse",
                name="Faculty Alpha",
                employee_id="EMP001",
                designation="Assistant Professor",
            ),
            Faculty(
                id="faculty-record-b",
                user_id="faculty-user-b",
                department_id="faculty-dept-ise",
                name="Faculty Beta",
                employee_id="EMP002",
                designation="Associate Professor",
            ),
            Student(
                id="faculty-test-student",
                user_id="faculty-student",
                section_id="faculty-section-a",
                usn="STU001",
            ),
            Floor(
                id="faculty-floor",
                block_id="faculty-block",
                level=1,
                name="First Floor",
            ),
            Subject(
                id="faculty-subject-a",
                code="BCS501",
                name="Database Systems",
                department_id="faculty-dept-cse",
                kind="THEORY",
            ),
            Subject(
                id="faculty-subject-b",
                code="BIS502",
                name="Information Systems",
                department_id="faculty-dept-ise",
                kind="THEORY",
            ),
        ])
        db.flush()
        db.add_all([
            Room(
                id="faculty-room-a101",
                block_id="faculty-block",
                floor_id="faculty-floor",
                code="A101",
                display_name="Classroom A101",
                resource_type="CLASSROOM",
                capacity=60,
                status="ACTIVE",
            ),
            Room(
                id="faculty-room-small",
                block_id="faculty-block",
                floor_id="faculty-floor",
                code="A102",
                display_name="Classroom A102",
                resource_type="CLASSROOM",
                capacity=15,
                status="ACTIVE",
            ),
            Room(
                id="faculty-room-inactive",
                block_id="faculty-block",
                floor_id="faculty-floor",
                code="A103",
                display_name="Classroom A103",
                resource_type="CLASSROOM",
                capacity=70,
                status="MAINTENANCE",
            ),
        ])
        db.flush()
        db.add_all([
            TimetableEntry(
                id="faculty-entry-a",
                section_id="faculty-section-a",
                subject_id="faculty-subject-a",
                faculty_id="faculty-record-a",
                weekday=weekday,
                start_slot="P1",
                duration_slots=1,
                kind="THEORY",
                required_room_type="CLASSROOM",
                base_room_id="faculty-room-a101",
                provenance="validation synthetic data",
            ),
            TimetableEntry(
                id="faculty-entry-b",
                section_id="faculty-section-b",
                subject_id="faculty-subject-b",
                faculty_id="faculty-record-b",
                weekday=weekday,
                start_slot="P2",
                duration_slots=1,
                kind="THEORY",
                required_room_type="CLASSROOM",
                base_room_id="faculty-room-a101",
                provenance="validation synthetic data",
            ),
            TimetableEntry(
                id="faculty-entry-conflict",
                section_id="faculty-section-b",
                subject_id="faculty-subject-b",
                faculty_id="faculty-record-b",
                weekday=weekday,
                start_slot="P7",
                duration_slots=1,
                kind="THEORY",
                required_room_type="CLASSROOM",
                base_room_id="faculty-room-a101",
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


def login_headers(client: TestClient, identifier: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={
        "identifier": identifier,
        "password": password,
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def request_date() -> str:
    today = date.today()
    days_until_same_weekday = (today.weekday() - today.weekday()) % 7 or 7
    return (today + timedelta(days=days_until_same_weekday)).isoformat()


def request_body(**overrides) -> dict:
    data = {
        "subject_id": "faculty-subject-a",
        "section_id": "faculty-section-a",
        "requested_date": request_date(),
        "start_time": "17:00",
        "end_time": "17:30",
        "expected_strength": 30,
        "reason": "Additional revision class requested.",
    }
    data.update(overrides)
    return data


def test_faculty_identity_teaching_subject_section_and_timetable_are_isolated(faculty_portal_client):
    client = faculty_portal_client
    faculty_a = login_headers(client, "EMP001", "FacultyPass123")
    faculty_b = login_headers(client, "EMP002", "FacultyPass123")

    profile_a = client.get("/api/faculty/profile", headers=faculty_a)
    profile_b = client.get("/api/faculty/profile", headers=faculty_b)
    assert profile_a.status_code == profile_b.status_code == 200
    assert (profile_a.json()["employee_id"], profile_a.json()["department"]) == (
        "EMP001",
        "Computer Science",
    )
    assert (profile_b.json()["employee_id"], profile_b.json()["department"]) == (
        "EMP002",
        "Information Science",
    )

    subjects_a = client.get("/api/faculty/subjects", headers=faculty_a).json()
    subjects_b = client.get("/api/faculty/subjects", headers=faculty_b).json()
    sections_a = client.get("/api/faculty/sections", headers=faculty_a).json()
    sections_b = client.get("/api/faculty/sections", headers=faculty_b).json()
    timetable_a = client.get("/api/faculty/timetable", headers=faculty_a).json()
    timetable_b = client.get("/api/faculty/timetable", headers=faculty_b).json()

    assert [item["code"] for item in subjects_a] == ["BCS501"]
    assert [item["code"] for item in subjects_b] == ["BIS502"]
    assert [item["code"] for item in sections_a] == ["5CSE-A"]
    assert [item["code"] for item in sections_b] == ["5ISE-B"]
    assert {item["section_code"] for item in timetable_a} == {"5CSE-A"}
    assert {item["section_code"] for item in timetable_b} == {"5ISE-B"}

    assert client.get("/api/faculty/profile", headers=login_headers(
        client, "manager@faculty.test", "ManagerPass123"
    )).status_code == 403
    assert client.get("/api/management/classroom-requests", headers=faculty_a).status_code == 403


def test_faculty_classroom_requests_are_private_and_require_owned_assignment(faculty_portal_client):
    client = faculty_portal_client
    faculty_a = login_headers(client, "EMP001", "FacultyPass123")
    faculty_b = login_headers(client, "EMP002", "FacultyPass123")
    student = login_headers(client, "student@faculty.test", "StudentPass123")
    manager = login_headers(client, "manager@faculty.test", "ManagerPass123")

    created = client.post(
        "/api/faculty/classroom-requests",
        headers=faculty_a,
        json=request_body(),
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["status"] == "PENDING"
    assert client.get("/api/faculty/classroom-requests", headers=faculty_b).json() == []
    assert client.post(
        f"/api/faculty/classroom-requests/{request_id}/cancel",
        headers=faculty_b,
    ).status_code == 404
    assert client.get("/api/faculty/classroom-requests", headers=student).status_code == 403
    assert client.get("/api/management/classroom-requests", headers=student).status_code == 403
    assert client.post(
        f"/api/management/classroom-requests/{request_id}/approve",
        headers=faculty_a,
        json={"room_id": "faculty-room-a101"},
    ).status_code == 403
    assert client.post(
        "/api/faculty/classroom-requests",
        headers=faculty_a,
        json=request_body(subject_id="faculty-subject-b", section_id="faculty-section-b"),
    ).status_code == 403
    assert client.get("/api/management/classroom-requests", headers=manager).json()[0]["id"] == request_id


def test_management_approval_validates_capacity_status_and_timetable_conflicts(faculty_portal_client):
    client = faculty_portal_client
    faculty_a = login_headers(client, "EMP001", "FacultyPass123")
    manager = login_headers(client, "manager@faculty.test", "ManagerPass123")

    request = client.post(
        "/api/faculty/classroom-requests",
        headers=faculty_a,
        json=request_body(),
    ).json()
    capacity_failure = client.post(
        f"/api/management/classroom-requests/{request['id']}/approve",
        headers=manager,
        json={"room_id": "faculty-room-small"},
    )
    assert capacity_failure.status_code == 422
    status_failure = client.post(
        f"/api/management/classroom-requests/{request['id']}/approve",
        headers=manager,
        json={"room_id": "faculty-room-inactive"},
    )
    assert status_failure.status_code == 422

    conflict_request = client.post(
        "/api/faculty/classroom-requests",
        headers=faculty_a,
        json=request_body(start_time="16:30", end_time="17:00"),
    ).json()
    conflict = client.post(
        f"/api/management/classroom-requests/{conflict_request['id']}/approve",
        headers=manager,
        json={"room_id": "faculty-room-a101"},
    )
    assert conflict.status_code == 409

    approved = client.post(
        f"/api/management/classroom-requests/{request['id']}/approve",
        headers=manager,
        json={"room_id": "faculty-room-a101"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["approved_room_code"] == "A101"
    faculty_schedule = client.get(
        "/api/faculty/timetable",
        headers=faculty_a,
        params={"date": request["requested_date"]},
    ).json()
    student_schedule = client.get(
        "/api/timetable/me",
        headers=login_headers(client, "student@faculty.test", "StudentPass123"),
        params={"date": request["requested_date"]},
    ).json()
    other_faculty_schedule = client.get(
        "/api/faculty/timetable",
        headers=login_headers(client, "EMP002", "FacultyPass123"),
        params={"date": request["requested_date"]},
    ).json()
    assert any(item["is_extra_class"] and item["effective_room_code"] == "A101" for item in faculty_schedule)
    assert any(item["is_extra_class"] and item["subject_code"] == "BCS501" for item in student_schedule)
    assert not any(item["is_extra_class"] for item in other_faculty_schedule)

    faculty_notifications = client.get("/api/notifications", headers=faculty_a).json()
    student_notifications = client.get("/api/notifications", headers=login_headers(
        client, "student@faculty.test", "StudentPass123"
    )).json()
    assert any(item["title"] == "Classroom request approved" for item in faculty_notifications)
    assert any(item["title"] == "Extra class scheduled" for item in student_notifications)
    assert not any(item["title"] == "Classroom request approved" for item in student_notifications)


def test_room_unavailability_and_attendance_session_are_enforced(faculty_portal_client):
    client = faculty_portal_client
    faculty_a = login_headers(client, "EMP001", "FacultyPass123")
    faculty_b = login_headers(client, "EMP002", "FacultyPass123")
    manager = login_headers(client, "manager@faculty.test", "ManagerPass123")
    date_value = date.fromisoformat(request_date())

    db_dependency = app.dependency_overrides[get_db]()
    db = next(db_dependency)
    try:
        db.add(RoomUnavailability(
            id="faculty-unavailable-room",
            room_id="faculty-room-a101",
            start_dt=datetime.combine(date_value, time(17, 0)),
            end_dt=datetime.combine(date_value, time(18, 0)),
            reason_type="MAINTENANCE",
            active=True,
        ))
        db.commit()
    finally:
        next(db_dependency, None)

    request = client.post(
        "/api/faculty/classroom-requests",
        headers=faculty_a,
        json=request_body(),
    ).json()
    unavailable = client.post(
        f"/api/management/classroom-requests/{request['id']}/approve",
        headers=manager,
        json={"room_id": "faculty-room-a101"},
    )
    assert unavailable.status_code == 409

    today = date.today().isoformat()
    started = client.post(
        "/api/faculty/attendance",
        headers=faculty_a,
        json={"timetable_entry_id": "faculty-entry-a", "session_date": today},
    )
    assert started.status_code == 201, started.text
    assert started.json()["records_entered"] == 0
    duplicate = client.post(
        "/api/faculty/attendance",
        headers=faculty_a,
        json={"timetable_entry_id": "faculty-entry-a", "session_date": today},
    )
    assert duplicate.status_code == 409
    other_faculty = client.post(
        "/api/faculty/attendance",
        headers=faculty_b,
        json={"timetable_entry_id": "faculty-entry-a", "session_date": today},
    )
    assert other_faculty.status_code == 403
    sessions_a = client.get("/api/faculty/attendance", headers=faculty_a).json()
    sessions_b = client.get("/api/faculty/attendance", headers=faculty_b).json()
    assert [session["id"] for session in sessions_a] == [started.json()["id"]]
    assert sessions_b == []


def test_faculty_ai_context_is_scoped_to_signed_in_teaching_assignments(faculty_portal_client):
    client = faculty_portal_client
    faculty_a = login_headers(client, "EMP001", "FacultyPass123")
    faculty_b = login_headers(client, "EMP002", "FacultyPass123")
    response_a = client.post(
        "/api/ai/chat",
        headers=faculty_a,
        json={"message": "What subjects do I teach?"},
    )
    response_b = client.post(
        "/api/ai/chat",
        headers=faculty_b,
        json={"message": "Which sections do I teach?"},
    )
    assert response_a.status_code == response_b.status_code == 200
    assert "BCS501" in response_a.json()["response"]
    assert "5ISE-B" not in response_a.json()["response"]
    assert "5ISE-B" in response_b.json()["response"]
    assert "5CSE-A" not in response_b.json()["response"]
