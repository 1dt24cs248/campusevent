"""Identity-isolated tests for academic records and faculty authorization."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.deps import get_db
from app.main import app
from app.models.academic import Department, Faculty, Section, Student, Subject
from app.models.identity import User
from app.models.schedule import TimetableEntry
from app.security import get_password_hash
from app.academic_schema import migrate_academic_schema


@pytest.fixture()
def academic_client():
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
            User(id="academic-student-a-user", email="a@academic.test", hashed_password=get_password_hash("AcademicPass123"), role="STUDENT", display_name="Student A", active=True),
            User(id="academic-student-a2-user", email="a2@academic.test", hashed_password=get_password_hash("AcademicPass123"), role="STUDENT", display_name="Student A2", active=True),
            User(id="academic-student-b-user", email="b@academic.test", hashed_password=get_password_hash("AcademicPass123"), role="STUDENT", display_name="Student B", active=True),
            User(id="academic-faculty-a-user", email="fa@academic.test", hashed_password=get_password_hash("AcademicPass123"), role="FACULTY", display_name="Faculty A", active=True),
            User(id="academic-faculty-b-user", email="fb@academic.test", hashed_password=get_password_hash("AcademicPass123"), role="FACULTY", display_name="Faculty B", active=True),
            User(id="academic-management-user", email="manager@academic.test", hashed_password=get_password_hash("AcademicPass123"), role="MANAGEMENT", display_name="Manager", active=True),
            Department(id="academic-dept-a", name="Computer Science"),
            Department(id="academic-dept-b", name="Information Science"),
            Section(id="academic-section-a", department_id="academic-dept-a", code="TEST-A", name="Test Section A", year=3, strength=2, is_synthetic=True),
            Section(id="academic-section-b", department_id="academic-dept-b", code="TEST-B", name="Test Section B", year=3, strength=1, is_synthetic=True),
        ])
        db.flush()
        db.add_all([
            Student(id="academic-student-a", user_id="academic-student-a-user", section_id="academic-section-a", usn="TEST001", semester=5, program="Test Program"),
            Student(id="academic-student-a2", user_id="academic-student-a2-user", section_id="academic-section-a", usn="TEST002", semester=5, program="Test Program"),
            Student(id="academic-student-b", user_id="academic-student-b-user", section_id="academic-section-b", usn="TEST003", semester=5, program="Other Program"),
            Faculty(id="academic-faculty-a", user_id="academic-faculty-a-user", department_id="academic-dept-a", name="Faculty A", employee_id="EMP001", is_synthetic=True),
            Faculty(id="academic-faculty-b", user_id="academic-faculty-b-user", department_id="academic-dept-b", name="Faculty B", employee_id="EMP002", is_synthetic=True),
            Subject(id="academic-subject-a", code="TEST-A", name="Subject A", department_id="academic-dept-a", is_synthetic=True),
            Subject(id="academic-subject-b", code="TEST-B", name="Subject B", department_id="academic-dept-b", is_synthetic=True),
        ])
        db.flush()
        today = date.today()
        db.add_all([
            TimetableEntry(id="academic-entry-a", section_id="academic-section-a", subject_id="academic-subject-a", faculty_id="academic-faculty-a", weekday=today.weekday(), start_slot="P1", duration_slots=1, kind="THEORY", provenance="synthetic test"),
            TimetableEntry(id="academic-entry-b", section_id="academic-section-b", subject_id="academic-subject-b", faculty_id="academic-faculty-b", weekday=today.weekday(), start_slot="P2", duration_slots=1, kind="THEORY", provenance="synthetic test"),
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


def _headers(client: TestClient, identifier: str, role: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={
        "identifier": identifier,
        "password": "AcademicPass123",
    })
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    current_user = client.get("/api/auth/me", headers=headers)
    assert current_user.status_code == 200
    assert current_user.json()["role"] == role
    return headers


def test_students_only_see_their_section_subjects_and_details(academic_client):
    student_a = _headers(academic_client, "a@academic.test", "STUDENT")
    student_b = _headers(academic_client, "b@academic.test", "STUDENT")
    academics_a = academic_client.get("/api/student/academics", headers=student_a).json()
    academics_b = academic_client.get("/api/student/academics", headers=student_b).json()
    assert [item["code"] for item in academics_a["subjects"]] == ["TEST-A"]
    assert [item["code"] for item in academics_b["subjects"]] == ["TEST-B"]
    assert academic_client.get("/api/student/academics/academic-subject-b", headers=student_a).status_code == 404
    assert academic_client.get("/api/student/academics/academic-subject-a", headers=student_b).status_code == 404


def test_attendance_session_requires_exact_roster_and_updates_own_student_summary(academic_client):
    faculty_a = _headers(academic_client, "EMP001", "FACULTY")
    student_a = _headers(academic_client, "a@academic.test", "STUDENT")
    student_a2 = _headers(academic_client, "a2@academic.test", "STUDENT")
    student_b = _headers(academic_client, "b@academic.test", "STUDENT")
    started = academic_client.post("/api/faculty/attendance", headers=faculty_a, json={
        "timetable_entry_id": "academic-entry-a",
        "session_date": date.today().isoformat(),
    })
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    incomplete = academic_client.put(
        f"/api/faculty/attendance/{session_id}/records",
        headers=faculty_a,
        json={"records": [{"student_id": "academic-student-a", "status": "PRESENT"}]},
    )
    assert incomplete.status_code == 422
    saved = academic_client.put(
        f"/api/faculty/attendance/{session_id}/records",
        headers=faculty_a,
        json={"records": [
            {"student_id": "academic-student-a", "status": "PRESENT"},
            {"student_id": "academic-student-a2", "status": "ABSENT"},
        ]},
    )
    assert saved.status_code == 200, saved.text
    details_a = academic_client.get("/api/student/academics/academic-subject-a", headers=student_a).json()
    details_a2 = academic_client.get("/api/student/academics/academic-subject-a", headers=student_a2).json()
    assert details_a["attendance"]["percentage"] == 100
    assert details_a2["attendance"]["percentage"] == 0
    details_b = academic_client.get("/api/student/academics/academic-subject-b", headers=student_b).json()
    assert details_b["attendance"] is None
    assert academic_client.get("/api/student/academics/academic-subject-b", headers=student_a).status_code == 404


def test_faculty_attendance_and_academic_writes_are_identity_scoped(academic_client):
    faculty_a = _headers(academic_client, "EMP001", "FACULTY")
    faculty_b = _headers(academic_client, "EMP002", "FACULTY")
    assignments_a = academic_client.get("/api/faculty/academic-assignments", headers=faculty_a).json()
    assignments_b = academic_client.get("/api/faculty/academic-assignments", headers=faculty_b).json()
    assert {(item["subject_id"], item["section_id"]) for item in assignments_a} == {("academic-subject-a", "academic-section-a")}
    assert {(item["subject_id"], item["section_id"]) for item in assignments_b} == {("academic-subject-b", "academic-section-b")}
    forbidden_resource = academic_client.post("/api/faculty/resources", headers=faculty_a, json={
        "subject_id": "academic-subject-b", "section_id": "academic-section-b",
        "title": "Private", "resource_type": "NOTES", "description": "test",
    })
    forbidden_assessment = academic_client.post("/api/faculty/assessments", headers=faculty_a, json={
        "subject_id": "academic-subject-b", "section_id": "academic-section-b",
        "title": "Private", "kind": "QUIZ", "date": (datetime.now() + timedelta(days=1)).isoformat(),
        "maximum_marks": 10,
    })
    assert forbidden_resource.status_code == 403
    assert forbidden_assessment.status_code == 403
    assert academic_client.get("/api/faculty/academic-content", headers=faculty_a).json() == {
        "assessments": [], "resources": [], "syllabus": [],
    }


def test_other_faculty_cannot_read_or_mark_attendance_session(academic_client):
    faculty_a = _headers(academic_client, "EMP001", "FACULTY")
    faculty_b = _headers(academic_client, "EMP002", "FACULTY")
    started = academic_client.post("/api/faculty/attendance", headers=faculty_a, json={
        "timetable_entry_id": "academic-entry-a",
        "session_date": date.today().isoformat(),
    })
    session_id = started.json()["id"]
    assert academic_client.get(f"/api/faculty/attendance/{session_id}", headers=faculty_b).status_code == 404
    assert academic_client.put(
        f"/api/faculty/attendance/{session_id}/records",
        headers=faculty_b,
        json={"records": [
            {"student_id": "academic-student-a", "status": "PRESENT"},
            {"student_id": "academic-student-a2", "status": "ABSENT"},
        ]},
    ).status_code == 404


def test_draft_assessments_and_marks_are_hidden_until_published(academic_client):
    faculty_a = _headers(academic_client, "EMP001", "FACULTY")
    student_a = _headers(academic_client, "a@academic.test", "STUDENT")
    created = academic_client.post("/api/faculty/assessments", headers=faculty_a, json={
        "subject_id": "academic-subject-a",
        "section_id": "academic-section-a",
        "title": "Internal 1",
        "kind": "INTERNAL",
        "date": (datetime.now() + timedelta(days=1)).isoformat(),
        "maximum_marks": 40,
    })
    assert created.status_code == 201, created.text
    assessment_id = created.json()["id"]
    details = academic_client.get("/api/student/academics/academic-subject-a", headers=student_a).json()
    assert details["assessments"] == []
    saved = academic_client.put(f"/api/faculty/assessments/{assessment_id}/marks", headers=faculty_a, json={
        "records": [{"student_id": "academic-student-a", "marks": 32}],
    })
    assert saved.status_code == 200, saved.text
    still_hidden = academic_client.get("/api/student/academics/academic-subject-a", headers=student_a).json()
    assert still_hidden["marks"] == []
    published = academic_client.post(f"/api/faculty/assessments/{assessment_id}/publish", headers=faculty_a)
    assert published.status_code == 200
    visible = academic_client.get("/api/student/academics/academic-subject-a", headers=student_a).json()
    assert visible["assessments"][0]["title"] == "Internal 1"
    assert visible["marks"][0]["marks"] == 32
    assert visible["marks"][0]["maximum_marks"] == 40


def test_resources_and_syllabus_are_authorized_and_identity_scoped(academic_client):
    faculty_a = _headers(academic_client, "EMP001", "FACULTY")
    student_a = _headers(academic_client, "a@academic.test", "STUDENT")
    student_b = _headers(academic_client, "b@academic.test", "STUDENT")
    module = academic_client.post("/api/faculty/syllabus", headers=faculty_a, json={
        "subject_id": "academic-subject-a",
        "module_number": 1,
        "title": "Test Module",
        "description": "Synthetic isolated test content",
        "sequence": 1,
        "status": "PUBLISHED",
    })
    resource = academic_client.post("/api/faculty/resources", headers=faculty_a, json={
        "subject_id": "academic-subject-a",
        "section_id": "academic-section-a",
        "title": "Test Notes",
        "resource_type": "NOTES",
        "description": "Synthetic isolated test content",
        "status": "PUBLISHED",
    })
    assert module.status_code == 201, module.text
    assert resource.status_code == 201, resource.text
    detail_a = academic_client.get("/api/student/academics/academic-subject-a", headers=student_a).json()
    assert [item["title"] for item in detail_a["syllabus"]] == ["Test Module"]
    assert [item["title"] for item in detail_a["resources"]] == ["Test Notes"]
    assert detail_a["syllabus"][0]["is_synthetic"] is True
    assert academic_client.get("/api/student/academics/academic-subject-a", headers=student_b).status_code == 404
    unsafe_resource = academic_client.post("/api/faculty/resources", headers=faculty_a, json={
        "subject_id": "academic-subject-a",
        "section_id": "academic-section-a",
        "title": "Unsafe link",
        "resource_type": "LINK",
        "url": "javascript:alert(1)",
    })
    assert unsafe_resource.status_code == 422


def test_student_academic_ai_uses_identity_scoped_data_and_honest_empty_state(academic_client):
    student_a = _headers(academic_client, "a@academic.test", "STUDENT")
    student_b = _headers(academic_client, "b@academic.test", "STUDENT")
    response_a = academic_client.post("/api/ai/chat", headers=student_a, json={"message": "What subjects do I have this semester?"})
    response_b = academic_client.post("/api/ai/chat", headers=student_b, json={"message": "What subjects do I have this semester?"})
    assert "TEST-A — Subject A" in response_a.json()["response"]
    assert "TEST-B — Subject B" not in response_a.json()["response"]
    assert "TEST-B — Subject B" in response_b.json()["response"]
    empty = academic_client.post("/api/ai/chat", headers=student_a, json={"message": "What is Module 1 in Subject A syllabus?"})
    assert empty.json()["response"] == "I don't have that academic information available yet."


def test_management_academic_directory_is_role_protected_and_shows_real_assignments(academic_client):
    manager = _headers(academic_client, "manager@academic.test", "MANAGEMENT")
    student = _headers(academic_client, "a@academic.test", "STUDENT")
    overview = academic_client.get("/api/management/academics", headers=manager)
    assert overview.status_code == 200
    data = overview.json()
    assert {item["code"] for item in data["subjects"]} == {"TEST-A", "TEST-B"}
    assert any(item["usn"] == "TEST001" and item["section_id"] == "academic-section-a" for item in data["student_section_assignments"])
    assert len(data["faculty_subject_section_assignments"]) == 2
    assert academic_client.get("/api/management/academics", headers=student).status_code == 403


def test_marks_are_limited_to_the_assessment_section_and_maximum(academic_client):
    faculty_a = _headers(academic_client, "EMP001", "FACULTY")
    faculty_b = _headers(academic_client, "EMP002", "FACULTY")
    created = academic_client.post("/api/faculty/assessments", headers=faculty_a, json={
        "subject_id": "academic-subject-a",
        "section_id": "academic-section-a",
        "title": "Roster check",
        "kind": "QUIZ",
        "date": (datetime.now() + timedelta(days=1)).isoformat(),
        "maximum_marks": 10,
    })
    assert created.status_code == 201
    assessment_id = created.json()["id"]
    wrong_section = academic_client.put(f"/api/faculty/assessments/{assessment_id}/marks", headers=faculty_a, json={
        "records": [{"student_id": "academic-student-b", "marks": 5}],
    })
    above_maximum = academic_client.put(f"/api/faculty/assessments/{assessment_id}/marks", headers=faculty_a, json={
        "records": [{"student_id": "academic-student-a", "marks": 11}],
    })
    assert wrong_section.status_code == 422
    assert above_maximum.status_code == 422
    assert academic_client.get(f"/api/faculty/assessments/{assessment_id}/marks", headers=faculty_b).status_code == 403


def test_ai_reports_unavailable_attendance_without_manufacturing_zero(academic_client):
    student_a = _headers(academic_client, "a@academic.test", "STUDENT")
    response = academic_client.post("/api/ai/chat", headers=student_a, json={"message": "How many classes have I attended?"})
    assert response.json()["response"] == "I don't have that academic information available yet."


def test_student_with_no_attendance_gets_null_summary_not_zero(academic_client):
    student_a = _headers(academic_client, "a@academic.test", "STUDENT")
    detail = academic_client.get("/api/student/academics/academic-subject-a", headers=student_a).json()
    assert detail["attendance"] is None
    assert detail["attendance_message"] == "Attendance records have not been entered yet."


def test_announcement_audience_and_section_scope_are_enforced(academic_client):
    manager = _headers(academic_client, "manager@academic.test", "MANAGEMENT")
    student_a = _headers(academic_client, "a@academic.test", "STUDENT")
    student_b = _headers(academic_client, "b@academic.test", "STUDENT")
    faculty_a = _headers(academic_client, "EMP001", "FACULTY")
    created = academic_client.post("/api/management/announcements", headers=manager, json={
        "title": "Section A update",
        "body": "Synthetic isolated announcement",
        "audience": ["STUDENT", "FACULTY"],
        "section_id": "academic-section-a",
    })
    assert created.status_code == 201, created.text
    academics_a = academic_client.get("/api/student/academics", headers=student_a).json()
    academics_b = academic_client.get("/api/student/academics", headers=student_b).json()
    faculty_announcements = academic_client.get("/api/faculty/announcements", headers=faculty_a).json()
    assert [item["title"] for item in academics_a["announcements"]] == ["Section A update"]
    assert academics_b["announcements"] == []
    assert [item["title"] for item in faculty_announcements] == ["Section A update"]


def test_management_ai_answers_from_live_counts_without_cross_role_exposure(academic_client):
    management = _headers(academic_client, "manager@academic.test", "MANAGEMENT")
    student = _headers(academic_client, "a@academic.test", "STUDENT")
    cases = (
        ("How many sections are there?", "There are 2 sections registered."),
        ("How many faculty members are active?", "There are 2 active faculty members."),
        ("How many students are active?", "There are 3 active students."),
    )
    for question, expected in cases:
        response = academic_client.post(
            "/api/ai/chat", headers=management, json={"message": question}
        )
        assert response.status_code == 200
        assert response.json()["response"] == expected

    restricted = academic_client.post(
        "/api/ai/chat",
        headers=student,
        json={"message": "How many faculty members are active?"},
    )
    assert restricted.status_code == 200
    assert "active faculty members" not in restricted.json()["response"]


def test_academic_migration_is_additive_and_idempotent():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE subjects (id VARCHAR PRIMARY KEY, code VARCHAR NOT NULL, name VARCHAR NOT NULL)"))
        connection.execute(text("CREATE TABLE assessments (id VARCHAR PRIMARY KEY, section_id VARCHAR, subject_id VARCHAR, title VARCHAR NOT NULL, date DATETIME NOT NULL, kind VARCHAR NOT NULL)"))
        connection.execute(text("CREATE TABLE announcements (id VARCHAR PRIMARY KEY, title VARCHAR NOT NULL, body VARCHAR NOT NULL, audience JSON, created_by VARCHAR, published_at DATETIME NOT NULL)"))
        connection.execute(text("INSERT INTO subjects (id, code, name) VALUES ('old-subject', 'OLD1', 'Legacy subject')"))
        connection.execute(text("INSERT INTO assessments (id, title, date, kind) VALUES ('old-assessment', 'Legacy assessment', '2026-01-01 09:00:00', 'EXAM')"))
        connection.execute(text("INSERT INTO announcements (id, title, body, published_at) VALUES ('old-announcement', 'Legacy note', 'Retained', '2026-01-01 09:00:00')"))
    migrate_academic_schema(engine)
    migrate_academic_schema(engine)
    with engine.connect() as connection:
        subject = connection.execute(text("SELECT name, credits FROM subjects WHERE id='old-subject'")).one()
        assessment = connection.execute(text("SELECT title, status, maximum_marks FROM assessments WHERE id='old-assessment'")).one()
        announcement = connection.execute(text("SELECT title, section_id FROM announcements WHERE id='old-announcement'")).one()
    assert subject == ("Legacy subject", None)
    assert assessment == ("Legacy assessment", "PUBLISHED", None)
    assert announcement == ("Legacy note", None)
    assert "provenance" in {column["name"] for column in inspect(engine).get_columns("assessments")}
    engine.dispose()
