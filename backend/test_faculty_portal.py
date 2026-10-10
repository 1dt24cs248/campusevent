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
                id="faculty-user-c",
                email="faculty.c@faculty.test",
                hashed_password=get_password_hash("FacultyPass123"),
                role="FACULTY",
                display_name="Faculty Gamma",
                active=True,
            ),
            User(
                id="faculty-user-first-year",
                email="faculty.firstyear@faculty.test",
                hashed_password=get_password_hash("FacultyPass123"),
                role="FACULTY",
                display_name="First Year Faculty",
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
            Department(id="faculty-dept-first-year", name="FIRST_YEAR"),
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
            Section(
                id="faculty-section-first-year",
                department_id="faculty-dept-first-year",
                code="1-FIRST-A",
                name="First Year A",
                year=1,
                strength=50,
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
            Faculty(
                id="faculty-record-c",
                user_id="faculty-user-c",
                department_id="faculty-dept-cse",
                name="Faculty Gamma",
                employee_id="EMP003",
                designation="Assistant Professor",
            ),
            Faculty(
                id="faculty-record-first-year",
                user_id="faculty-user-first-year",
                department_id="faculty-dept-first-year",
                name="First Year Faculty",
                employee_id="EMP004",
                designation="Assistant Professor",
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
            Subject(
                id="faculty-subject-c",
                code="BCS503",
                name="Computer Networks",
                department_id="faculty-dept-cse",
                kind="THEORY",
                required_facilities=[],
            ),
            Subject(
                id="faculty-subject-d",
                code="BCS504",
                name="Digital Logic",
                department_id="faculty-dept-cse",
                kind="THEORY",
                required_facilities=["PROJECTOR"],
            ),
            Subject(
                id="faculty-subject-lab",
                code="BCS505-LAB",
                name="Networks Laboratory",
                department_id="faculty-dept-cse",
                kind="LAB",
                lab_kind="COMPUTER",
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
            Room(
                id="faculty-room-no-projector",
                block_id="faculty-block",
                floor_id="faculty-floor",
                code="A104",
                display_name="Classroom A104",
                resource_type="CLASSROOM",
                capacity=70,
                facilities=[],
                status="ACTIVE",
            ),
            Room(
                id="faculty-room-computer-lab",
                block_id="faculty-block",
                floor_id="faculty-floor",
                code="A105",
                display_name="Computer Laboratory A105",
                resource_type="LAB",
                lab_kind="COMPUTER",
                capacity=30,
                facilities=[],
                status="ACTIVE",
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
            TimetableEntry(
                id="faculty-entry-section-conflict",
                section_id="faculty-section-a",
                subject_id="faculty-subject-a",
                faculty_id="faculty-record-c",
                weekday=weekday,
                start_slot="P4",
                duration_slots=1,
                kind="THEORY",
                required_room_type="CLASSROOM",
                base_room_id="faculty-room-a101",
            ),
            TimetableEntry(
                id="faculty-entry-subject-c-offering",
                section_id="faculty-section-a",
                subject_id="faculty-subject-c",
                faculty_id="faculty-record-c",
                weekday=weekday,
                start_slot="P6",
                duration_slots=1,
                kind="THEORY",
                required_room_type="CLASSROOM",
                base_room_id="faculty-room-a101",
            ),
            TimetableEntry(
                id="faculty-entry-subject-d-offering",
                section_id="faculty-section-a",
                subject_id="faculty-subject-d",
                faculty_id="faculty-record-c",
                weekday=(weekday + 1) % 6,
                start_slot="P6",
                duration_slots=1,
                kind="THEORY",
                required_room_type="CLASSROOM",
                base_room_id="faculty-room-a101",
            ),
            TimetableEntry(
                id="faculty-entry-subject-lab-offering",
                section_id="faculty-section-a",
                subject_id="faculty-subject-lab",
                faculty_id="faculty-record-c",
                weekday=(weekday + 1) % 6,
                start_slot="P7",
                duration_slots=1,
                kind="LAB",
                required_room_type="LAB",
                required_lab_kind="COMPUTER",
                base_room_id="faculty-room-computer-lab",
            ),
            TimetableEntry(
                id="faculty-entry-first-year-subject-c",
                section_id="faculty-section-first-year",
                subject_id="faculty-subject-c",
                faculty_id="faculty-record-c",
                weekday=(weekday + 1) % 6,
                start_slot="P5",
                duration_slots=1,
                kind="THEORY",
                required_room_type="CLASSROOM",
                base_room_id="faculty-room-a101",
            ),
            TimetableEntry(
                id="faculty-entry-first-year-subject-d",
                section_id="faculty-section-first-year",
                subject_id="faculty-subject-d",
                faculty_id="faculty-record-c",
                weekday=(weekday + 1) % 6,
                start_slot="P6",
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


def subject_request_body(**overrides) -> dict:
    today_code = ("MON", "TUE", "WED", "THU", "FRI", "SAT")[date.today().weekday()]
    data = {
        "note": "Requesting the remaining Computer Networks teaching assignment.",
        "items": [{
            "subject_id": "faculty-subject-c",
            "preferred_section_ids": ["faculty-section-a"],
            "availability": {today_code: ["P1", "P2", "P3"]},
            "periods_per_week": 1,
        }],
    }
    data.update(overrides)
    return data


def subject_request_headers(client: TestClient) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    faculty = login_headers(client, "EMP001", "FacultyPass123")
    manager = login_headers(client, "manager@faculty.test", "ManagerPass123")
    student = login_headers(client, "student@faculty.test", "StudentPass123")
    designated = client.put(
        "/api/management/faculty/faculty-record-a/teaching-eligibility",
        headers=manager,
        json={"academic_years": [3], "section_ids": []},
    )
    assert designated.status_code == 200, designated.text
    return faculty, manager, student


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


def test_faculty_subject_request_approval_assignment_and_publish(faculty_portal_client):
    client = faculty_portal_client
    faculty, manager, student = subject_request_headers(client)

    catalog = client.get("/api/faculty/subject-catalog", headers=faculty)
    assert catalog.status_code == 200
    assert catalog.json()["department"] == "Computer Science"
    assert {item["code"] for item in catalog.json()["subjects"]} == {
        "BCS501", "BIS502", "BCS503", "BCS504", "BCS505-LAB"
    }
    assert client.get("/api/faculty/subject-catalog", headers=student).status_code == 403

    submitted = client.post(
        "/api/faculty/subject-requests",
        headers=faculty,
        json=subject_request_body(),
    )
    assert submitted.status_code == 201, submitted.text
    request = submitted.json()
    request_id = request["id"]
    item = request["items"][0]
    item_id = item["id"]
    assert (request["status"], item["status"]) == ("PENDING", "PENDING")
    pending_subject = next(
        subject for subject in client.get("/api/faculty/subjects", headers=faculty).json()
        if subject["code"] == "BCS503"
    )
    assert pending_subject["assignment_status"] == "PENDING"
    faculty_requests = client.get("/api/faculty/subject-requests", headers=faculty)
    assert faculty_requests.status_code == 200
    assert faculty_requests.json()[0]["status"] == "PENDING"
    assert client.get("/api/faculty/subject-requests", headers=student).status_code == 403
    catalog_with_active_request = client.get("/api/faculty/subject-catalog", headers=faculty).json()
    requested_subject = next(
        subject for subject in catalog_with_active_request["subjects"]
        if subject["code"] == "BCS503"
    )
    assert requested_subject["active_request_status"] == "PENDING"
    assert client.get("/api/management/faculty-subject-requests", headers=faculty).status_code == 403
    assert client.post(
        f"/api/management/faculty-subject-requests/{request_id}/items/{item_id}/review",
        headers=faculty,
        json={"status": "APPROVED"},
    ).status_code == 403
    assert client.post(
        "/api/faculty/subject-requests",
        headers=faculty,
        json=subject_request_body(items=[{
            "subject_id": "faculty-subject-d",
            "preferred_section_ids": ["faculty-section-b"],
            "periods_per_week": 1,
        }]),
    ).status_code == 422
    assert client.post(
        "/api/faculty/subject-requests",
        headers=faculty,
        json=subject_request_body(items=[{
            "subject_id": "faculty-subject-a",
            "periods_per_week": 1,
        }]),
    ).status_code == 409
    assert client.post(
        "/api/faculty/subject-requests",
        headers=faculty,
        json=subject_request_body(),
    ).status_code == 409

    management_list = client.get("/api/management/faculty-subject-requests", headers=manager)
    assert management_list.status_code == 200
    assert management_list.json()[0]["faculty_name"] == "Faculty Alpha"

    approved = client.post(
        f"/api/management/faculty-subject-requests/{request_id}/items/{item_id}/review",
        headers=manager,
        json={"status": "APPROVED"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["items"][0]["status"] == "APPROVED"
    assert client.get("/api/faculty/subject-requests", headers=faculty).json()[0]["status"] == "APPROVED"
    approved_subject = next(
        subject for subject in client.get("/api/faculty/subjects", headers=faculty).json()
        if subject["code"] == "BCS503"
    )
    assert approved_subject["assignment_status"] == "APPROVED"
    assert approved_subject["weekly_periods"] == 1
    assert approved_subject["weekly_hours"] == 0.92
    assert not any(entry["subject_code"] == "BCS503" for entry in client.get(
        "/api/faculty/timetable", headers=faculty
    ).json())

    listed_item = management_list.json()[0]["items"][0]
    assert listed_item["periods_per_week"] == 1
    assert [row["code"] for row in listed_item["eligible_sections"]] == ["5CSE-A"]
    room_options = client.get("/api/management/classroom-requests/rooms", headers=manager)
    assert room_options.status_code == 200
    assert "faculty-room-a101" in {row["id"] for row in room_options.json()}

    assignment_url = f"/api/management/faculty-subject-requests/{request_id}/items/{item_id}/assignments"
    faculty_conflict = client.put(assignment_url, headers=manager, json={"assignments": [{
        "section_id": "faculty-section-a", "room_id": "faculty-room-a101",
        "weekday": date.today().weekday(), "start_slot": "P1", "duration_slots": 1,
    }]})
    assert faculty_conflict.status_code == 409
    room_conflict = client.put(assignment_url, headers=manager, json={"assignments": [{
        "section_id": "faculty-section-a", "room_id": "faculty-room-a101",
        "weekday": date.today().weekday(), "start_slot": "P2", "duration_slots": 1,
    }]})
    assert room_conflict.status_code == 409
    capacity_conflict = client.put(assignment_url, headers=manager, json={"assignments": [{
        "section_id": "faculty-section-a", "room_id": "faculty-room-small",
        "weekday": date.today().weekday(), "start_slot": "P3", "duration_slots": 1,
    }]})
    assert capacity_conflict.status_code == 422

    section_schedule_before_staging = client.get(
        "/api/timetable/section/faculty-section-a", headers=student
    ).json()
    staged = client.put(assignment_url, headers=manager, json={"assignments": [{
        "section_id": "faculty-section-a", "room_id": "faculty-room-a101",
        "weekday": date.today().weekday(), "start_slot": "P3", "duration_slots": 1,
    }]})
    assert staged.status_code == 200, staged.text
    assert staged.json()["items"][0]["status"] == "ASSIGNED"
    assert staged.json()["items"][0]["assignments"][0]["published"] is False
    staged_subject = next(
        subject for subject in client.get("/api/faculty/subjects", headers=faculty).json()
        if subject["code"] == "BCS503"
    )
    assert staged_subject["assignment_status"] == "ASSIGNED"
    assert staged_subject["sections"] == ["5CSE-A"]
    assert not any(entry["subject_code"] == "BCS503" for entry in client.get(
        "/api/faculty/timetable", headers=faculty
    ).json())
    assert client.get(
        "/api/timetable/section/faculty-section-a", headers=student
    ).json() == section_schedule_before_staging

    publish_url = f"/api/management/faculty-subject-requests/{request_id}/items/{item_id}/publish"
    assert client.post(publish_url, headers=faculty).status_code == 403
    assert client.post(publish_url, headers=student).status_code == 403
    published = client.post(publish_url, headers=manager)
    assert published.status_code == 200, published.text
    assert published.json()["items"][0]["status"] == "PUBLISHED"
    assert published.json()["status"] == "COMPLETED"
    assert published.json()["items"][0]["assignments"][0]["published"] is True

    faculty_schedule = client.get("/api/faculty/timetable", headers=faculty).json()
    section_schedule = client.get(
        "/api/timetable/section/faculty-section-a", headers=student
    ).json()
    published_entry = next(entry for entry in faculty_schedule if entry["subject_code"] == "BCS503")
    assert (published_entry["weekday"], published_entry["start_time"], published_entry["end_time"]) == (
        date.today().weekday(), "11:35", "12:30"
    )
    assert published_entry["section_code"] == "5CSE-A"
    assert published_entry["effective_room_code"] == "A101"
    assert any(entry["subject_code"] == "BCS503" for entry in section_schedule)
    published_subject = next(
        subject for subject in client.get("/api/faculty/subjects", headers=faculty).json()
        if subject["code"] == "BCS503"
    )
    assert published_subject["assignment_status"] == "PUBLISHED"
    assert published_subject["weekly_periods"] == 1
    faculty_sections = client.get("/api/faculty/sections", headers=faculty).json()
    assert [section["code"] for section in faculty_sections] == ["5CSE-A"]
    assert faculty_sections[0]["subjects"] == ["BCS501", "BCS503"]
    assert any(item["title"] == "Teaching assignment published" for item in client.get(
        "/api/notifications", headers=faculty
    ).json())
    assert any(item["title"] == "New class added to your timetable" for item in client.get(
        "/api/notifications", headers=student
    ).json())


def test_management_year_eligibility_exposes_existing_offerings_without_department_match(faculty_portal_client):
    client = faculty_portal_client
    first_year_faculty = login_headers(client, "EMP004", "FacultyPass123")
    manager = login_headers(client, "manager@faculty.test", "ManagerPass123")
    assert client.get(
        "/api/management/faculty-teaching-eligibility",
        headers=first_year_faculty,
    ).status_code == 403
    designated = client.put(
        "/api/management/faculty/faculty-record-first-year/teaching-eligibility",
        headers=manager,
        json={"academic_years": [1], "section_ids": []},
    )
    assert designated.status_code == 200, designated.text
    assert designated.json()["academic_years"] == [1]

    catalog = client.get("/api/faculty/subject-catalog", headers=first_year_faculty)
    assert catalog.status_code == 200
    assert catalog.json()["department"] == "FIRST_YEAR"
    assert catalog.json()["eligible_academic_years"] == [1]
    subjects = {subject["code"]: subject for subject in catalog.json()["subjects"]}
    assert set(subjects) == {"BCS503", "BCS504"}
    assert subjects["BCS503"]["eligible_sections"] == [{
        "id": "faculty-section-first-year", "code": "1-FIRST-A"
    }]
    assert all(subject["id"] for subject in subjects.values())

    assert client.post(
        "/api/faculty/subject-requests",
        headers=first_year_faculty,
        json=subject_request_body(items=[{
            "subject_id": "faculty-subject-a",
            "periods_per_week": 1,
        }]),
    ).status_code == 422
    submitted = client.post(
        "/api/faculty/subject-requests",
        headers=first_year_faculty,
        json=subject_request_body(items=[
            {
                "subject_id": "faculty-subject-c",
                "preferred_section_ids": ["faculty-section-first-year"],
                "periods_per_week": 1,
            },
            {
                "subject_id": "faculty-subject-d",
                "preferred_section_ids": ["faculty-section-first-year"],
                "periods_per_week": 1,
            },
        ]),
    )
    assert submitted.status_code == 201, submitted.text
    assert {item["subject_code"] for item in submitted.json()["items"]} == {"BCS503", "BCS504"}


def test_lab_subject_requires_a_compatible_lab_for_publication(faculty_portal_client):
    client = faculty_portal_client
    faculty, manager, _student = subject_request_headers(client)
    weekday = (date.today().weekday() + 1) % 6
    weekday_code = ("MON", "TUE", "WED", "THU", "FRI", "SAT")[weekday]
    created = client.post(
        "/api/faculty/subject-requests",
        headers=faculty,
        json=subject_request_body(items=[{
            "subject_id": "faculty-subject-lab",
            "preferred_section_ids": ["faculty-section-a"],
            "availability": {weekday_code: ["P3"]},
            "periods_per_week": 1,
        }]),
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    item_id = created.json()["items"][0]["id"]
    review = client.post(
        f"/api/management/faculty-subject-requests/{request_id}/items/{item_id}/review",
        headers=manager,
        json={"status": "APPROVED"},
    )
    assert review.status_code == 200, review.text
    assignment_url = f"/api/management/faculty-subject-requests/{request_id}/items/{item_id}/assignments"
    invalid_room = client.put(assignment_url, headers=manager, json={"assignments": [{
        "section_id": "faculty-section-a",
        "room_id": "faculty-room-a101",
        "weekday": weekday,
        "start_slot": "P3",
        "duration_slots": 1,
    }]})
    assert invalid_room.status_code == 422
    staged = client.put(assignment_url, headers=manager, json={"assignments": [{
        "section_id": "faculty-section-a",
        "room_id": "faculty-room-computer-lab",
        "weekday": weekday,
        "start_slot": "P3",
        "duration_slots": 1,
    }]})
    assert staged.status_code == 200, staged.text
    published = client.post(
        f"/api/management/faculty-subject-requests/{request_id}/items/{item_id}/publish",
        headers=manager,
    )
    assert published.status_code == 200, published.text
    entry = next(
        item for item in client.get("/api/faculty/timetable", headers=faculty).json()
        if item["subject_code"] == "BCS505-LAB"
    )
    assert entry["effective_room_code"] == "A105"


def test_management_rejection_requires_reason_and_notifies_faculty(faculty_portal_client):
    client = faculty_portal_client
    faculty, manager, _student = subject_request_headers(client)
    created = client.post(
        "/api/faculty/subject-requests",
        headers=faculty,
        json=subject_request_body(),
    )
    assert created.status_code == 201, created.text
    request = created.json()
    item_id = request["items"][0]["id"]
    url = f"/api/management/faculty-subject-requests/{request['id']}/items/{item_id}/review"
    assert client.post(url, headers=manager, json={"status": "REJECTED"}).status_code == 422
    rejected = client.post(url, headers=manager, json={
        "status": "REJECTED", "reason": "The requested section has no available teaching slot."
    })
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "COMPLETED"
    assert rejected.json()["items"][0]["status"] == "REJECTED"
    assert rejected.json()["items"][0]["decision_reason"] == "The requested section has no available teaching slot."
    assert "BCS503" not in {item["code"] for item in client.get(
        "/api/faculty/subjects", headers=faculty
    ).json()}
    assert any(item["title"] == "Subject request rejected" for item in client.get(
        "/api/notifications", headers=faculty
    ).json())


def test_management_subject_assignment_rejects_section_and_facility_conflicts(faculty_portal_client):
    client = faculty_portal_client
    faculty, manager, _student = subject_request_headers(client)
    today_code = ("MON", "TUE", "WED", "THU", "FRI", "SAT")[date.today().weekday()]
    request_body_value = subject_request_body(items=[
        {
            "subject_id": "faculty-subject-c",
            "preferred_section_ids": ["faculty-section-a"],
            "availability": {today_code: ["P1", "P2", "P3", "P4", "P5"]},
            "periods_per_week": 1,
        },
        {
            "subject_id": "faculty-subject-d",
            "preferred_section_ids": ["faculty-section-a"],
            "availability": {today_code: ["P1", "P2", "P3", "P4", "P5"]},
            "periods_per_week": 1,
        },
    ])
    created = client.post("/api/faculty/subject-requests", headers=faculty, json=request_body_value)
    assert created.status_code == 201, created.text
    request = created.json()
    items_by_code = {item["subject_code"]: item for item in request["items"]}
    for item in request["items"]:
        reviewed = client.post(
            f"/api/management/faculty-subject-requests/{request['id']}/items/{item['id']}/review",
            headers=manager,
            json={"status": "APPROVED"},
        )
        assert reviewed.status_code == 200, reviewed.text

    base_url = f"/api/management/faculty-subject-requests/{request['id']}/items"
    section_conflict = client.put(
        f"{base_url}/{items_by_code['BCS503']['id']}/assignments",
        headers=manager,
        json={"assignments": [{
            "section_id": "faculty-section-a", "room_id": "faculty-room-no-projector",
            "weekday": date.today().weekday(), "start_slot": "P4", "duration_slots": 1,
        }]},
    )
    assert section_conflict.status_code == 409

    facility_conflict = client.put(
        f"{base_url}/{items_by_code['BCS504']['id']}/assignments",
        headers=manager,
        json={"assignments": [{
            "section_id": "faculty-section-a", "room_id": "faculty-room-no-projector",
            "weekday": date.today().weekday(), "start_slot": "P5", "duration_slots": 1,
        }]},
    )
    assert facility_conflict.status_code == 422


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
