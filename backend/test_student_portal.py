"""Student self-service isolation tests using an isolated synthetic database."""
from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.deps import get_db
from app.main import app
from app.models.academic import Department, Faculty, Section, Student, Subject
from app.models.campus import Block, Floor, Room
from app.models.identity import User
from app.models.schedule import SessionOverride, TimetableEntry
from app.models.workflow import Notification
from app.security import get_password_hash


@pytest.fixture()
def student_portal_client():
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
    with session_factory() as db:
        db.add_all([
            User(
                id="portal-manager",
                email="manager@portal.test",
                hashed_password=get_password_hash("ManagerPass123"),
                role="MANAGEMENT",
                display_name="Portal Manager",
                active=True,
            ),
            User(
                id="portal-student-a",
                email="student.a@portal.test",
                hashed_password=get_password_hash("StudentPass123"),
                role="STUDENT",
                display_name="Student Alpha",
                active=True,
            ),
            User(
                id="portal-student-b",
                email="student.b@portal.test",
                hashed_password=get_password_hash("StudentPass123"),
                role="STUDENT",
                display_name="Student Beta",
                active=True,
            ),
            Department(id="portal-cse", name="Computer Science"),
            Department(id="portal-ise", name="Information Science"),
            Section(
                id="portal-section-a",
                department_id="portal-cse",
                code="5CSE-A",
                name="Fifth Semester CSE-A",
                year=3,
                strength=50,
                is_synthetic=False,
            ),
            Section(
                id="portal-section-b",
                department_id="portal-ise",
                code="5ISE-B",
                name="Fifth Semester ISE-B",
                year=3,
                strength=45,
                is_synthetic=False,
            ),
            Block(id="portal-block", code="A", name="Block A"),
        ])
        db.flush()
        db.add_all([
            Student(
                id="portal-student-record-a",
                user_id="portal-student-a",
                section_id="portal-section-a",
                usn="TEST001",
                phone="9000000001",
                program="B.E. Computer Science",
                semester=5,
                admission_year=2023,
                academic_status="ACTIVE",
            ),
            Student(
                id="portal-student-record-b",
                user_id="portal-student-b",
                section_id="portal-section-b",
                usn="TEST002",
                phone="9000000002",
                program="B.E. Information Science",
                semester=5,
                admission_year=2023,
                academic_status="ACTIVE",
            ),
            Floor(
                id="portal-floor",
                block_id="portal-block",
                level=1,
                name="First Floor",
            ),
            Faculty(
                id="portal-faculty-a",
                department_id="portal-cse",
                name="Faculty Alpha",
            ),
            Faculty(
                id="portal-faculty-b",
                department_id="portal-ise",
                name="Faculty Beta",
            ),
            Subject(
                id="portal-subject-a",
                code="BCS501",
                name="Database Systems",
                department_id="portal-cse",
                kind="THEORY",
            ),
            Subject(
                id="portal-subject-b",
                code="BIS502",
                name="Information Systems",
                department_id="portal-ise",
                kind="THEORY",
            ),
        ])
        db.flush()
        db.add_all([
            Room(
                id="portal-room-a101",
                block_id="portal-block",
                floor_id="portal-floor",
                code="A101",
                display_name="Classroom A101",
                resource_type="CLASSROOM",
                capacity=60,
            ),
            Room(
                id="portal-room-a107",
                block_id="portal-block",
                floor_id="portal-floor",
                code="A107",
                display_name="Classroom A107",
                resource_type="CLASSROOM",
                capacity=60,
            ),
            Room(
                id="portal-room-b201",
                block_id="portal-block",
                floor_id="portal-floor",
                code="B201",
                display_name="Classroom B201",
                resource_type="CLASSROOM",
                capacity=50,
            ),
        ])
        db.flush()
        weekday = (date.today().weekday())
        db.add_all([
            TimetableEntry(
                id="portal-entry-a",
                section_id="portal-section-a",
                subject_id="portal-subject-a",
                faculty_id="portal-faculty-a",
                weekday=weekday,
                start_slot="P1",
                duration_slots=1,
                kind="THEORY",
                base_room_id="portal-room-a101",
                provenance="validation synthetic data",
            ),
            TimetableEntry(
                id="portal-entry-b",
                section_id="portal-section-b",
                subject_id="portal-subject-b",
                faculty_id="portal-faculty-b",
                weekday=weekday,
                start_slot="P2",
                duration_slots=1,
                kind="THEORY",
                base_room_id="portal-room-b201",
                provenance="validation synthetic data",
            ),
        ])
        db.flush()
        db.add(
            SessionOverride(
                id="portal-override-a",
                entry_id="portal-entry-a",
                date=datetime.combine(date.today(), time.min),
                room_id="portal-room-a107",
                old_room_id="portal-room-a101",
                reason="Isolated validation change",
                active=True,
            )
        )
        db.add_all([
            Notification(
                id="portal-notification-a",
                audience_type="USER",
                audience_id="portal-student-a",
                type="TEST",
                title="Student A update",
                body="For Student A only",
                created_at=datetime.now(),
            ),
            Notification(
                id="portal-notification-b",
                audience_type="USER",
                audience_id="portal-student-b",
                type="TEST",
                title="Student B update",
                body="For Student B only",
                created_at=datetime.now(),
            ),
            Notification(
                id="portal-notification-section",
                audience_type="SECTION",
                audience_id="portal-section-a",
                type="TEST",
                title="Section A update",
                body="For section A",
                created_at=datetime.now(),
            ),
            Notification(
                id="portal-notification-mismatched-audience",
                audience_type="ROLE",
                audience_id="portal-student-a",
                type="TEST",
                title="Mis-typed private update",
                body="Must not be selected through an unrelated audience type",
                created_at=datetime.now(),
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


def student_token(client: TestClient, identifier: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={
        "identifier": identifier,
        "password": "StudentPass123",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_two_student_logins_resolve_to_distinct_profile_section_timetable_and_subjects(student_portal_client):
    client = student_portal_client
    headers_a = student_token(client, "TEST001")
    headers_b = student_token(client, "TEST002")

    profile_a = client.get("/api/student/profile", headers=headers_a)
    profile_b = client.get("/api/student/profile", headers=headers_b)
    assert profile_a.status_code == profile_b.status_code == 200
    assert (profile_a.json()["usn"], profile_a.json()["section"]) == ("TEST001", "5CSE-A")
    assert (profile_b.json()["usn"], profile_b.json()["section"]) == ("TEST002", "5ISE-B")
    assert profile_a.json()["full_name"] == "Student Alpha"
    assert profile_b.json()["full_name"] == "Student Beta"
    assert client.get("/api/auth/me", headers=headers_a).json()["student_id"] == "portal-student-record-a"

    today = date.today().isoformat()
    timetable_a = client.get("/api/timetable/me", headers=headers_a, params={"date": today})
    timetable_b = client.get("/api/timetable/me", headers=headers_b, params={"date": today})
    assert timetable_a.status_code == timetable_b.status_code == 200
    entry_a = timetable_a.json()[0]
    entry_b = timetable_b.json()[0]
    assert entry_a["section_code"] == "5CSE-A"
    assert entry_a["subject_code"] == "BCS501"
    assert entry_a["faculty_name"] == "Faculty Alpha"
    assert entry_a["base_room_code"] == "A101"
    assert entry_a["effective_room_code"] == "A107"
    assert entry_a["room_changed"] is True
    assert (entry_a["start_time"], entry_a["end_time"]) == ("09:30", "10:25")
    assert entry_b["section_code"] == "5ISE-B"
    assert entry_b["subject_code"] == "BIS502"
    assert entry_b["effective_room_code"] == "B201"
    assert entry_b["room_changed"] is False
    ai_change_a = client.post(
        "/api/ai/chat",
        headers=headers_a,
        json={"message": "Did my classroom change?"},
    )
    ai_change_b = client.post(
        "/api/ai/chat",
        headers=headers_b,
        json={"message": "Did my classroom change?"},
    )
    assert "BCS501" in ai_change_a.json()["response"]
    assert "A101 → A107" in ai_change_a.json()["response"]
    assert ai_change_b.json()["response"] == "No classroom changes are currently active for your schedule today."

    academics_a = client.get("/api/student/academics", headers=headers_a)
    academics_b = client.get("/api/student/academics", headers=headers_b)
    assert [subject["code"] for subject in academics_a.json()["subjects"]] == ["BCS501"]
    assert [subject["code"] for subject in academics_b.json()["subjects"]] == ["BIS502"]
    subject_detail = client.get(
        "/api/student/academics/portal-subject-a",
        headers=headers_a,
    )
    assert subject_detail.status_code == 200
    assert subject_detail.json()["syllabus_published"] is False
    assert subject_detail.json()["resources_published"] is False

    assert entry_a["start_slot"] == "P1"
    assert entry_b["start_slot"] == "P2"


def test_student_cannot_manipulate_profile_timetable_subject_or_notification_scope(student_portal_client):
    client = student_portal_client
    headers_a = student_token(client, "TEST001")

    other_timetable = client.get(
        "/api/timetable/section/portal-section-b",
        headers=headers_a,
    )
    other_subject = client.get(
        "/api/student/academics/portal-subject-b",
        headers=headers_a,
    )
    assert other_timetable.status_code == 403
    assert other_subject.status_code == 404

    notifications = client.get("/api/notifications", headers=headers_a)
    assert notifications.status_code == 200
    titles = {item["title"] for item in notifications.json()}
    assert titles == {"Student A update", "Section A update"}


def test_student_self_service_apis_reject_other_roles(student_portal_client):
    client = student_portal_client
    login = client.post("/api/auth/login", json={
        "identifier": "manager@portal.test",
        "password": "ManagerPass123",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/student/profile", headers=headers).status_code == 403
    assert client.get("/api/student/academics", headers=headers).status_code == 403
