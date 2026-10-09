"""Isolated tests for institutional identity and management provisioning APIs."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.deps import get_db
from app.identity_schema import migrate_identity_columns
from app.main import app
from app.models.academic import Department, Section
from app.models.identity import User
from app.security import create_access_token, get_password_hash


@pytest.fixture()
def identity_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        db.add_all([
            User(
                id="identity-manager",
                email="manager@test.local",
                hashed_password=get_password_hash("ManagerPass123"),
                role="MANAGEMENT",
                display_name="Manager",
                active=True,
                can_view_incidents=False,
            ),
            Department(id="dept_cse", name="CSE"),
            Department(id="dept_ise", name="ISE"),
            Section(
                id="section_cse_a",
                department_id="dept_cse",
                code="5CSE-A",
                name="5th Semester CSE-A",
                year=3,
                strength=60,
                is_synthetic=False,
            ),
            Section(
                id="section_ise_a",
                department_id="dept_ise",
                code="5ISE-A",
                name="5th Semester ISE-A",
                year=3,
                strength=55,
                is_synthetic=True,
            ),
        ])
        db.commit()

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    def headers(user_id: str, role: str):
        token = create_access_token({"sub": user_id, "role": role})
        return {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        yield client, headers("identity-manager", "MANAGEMENT")

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def student_payload(**overrides):
    return {
        "usn": "1DS23CS001",
        "email": "student@campus.test",
        "password": "StudentPass123",
        "name": "Student One",
        "phone": "9876543210",
        "department_id": "dept_cse",
        "program": "B.E. Computer Science",
        "semester": 5,
        "section_id": "section_cse_a",
        "admission_year": 2023,
        "academic_status": "ACTIVE",
        **overrides,
    }


def test_management_creates_student_and_login_resolves_usn_and_email(identity_client):
    client, manager = identity_client
    created = client.post(
        "/api/management/students",
        headers=manager,
        json=student_payload(usn=" 1ds23cs001 "),
    )
    assert created.status_code == 201, created.text
    student = created.json()
    assert student["usn"] == "1DS23CS001"
    assert student["section"] == "5CSE-A"
    assert student["department"] == "CSE"

    for identifier in ("1ds23cs001", "student@campus.test"):
        login = client.post("/api/auth/login", json={
            "identifier": identifier,
            "password": "StudentPass123",
        })
        assert login.status_code == 200, login.text
        profile = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert profile.status_code == 200
        assert profile.json()["usn"] == "1DS23CS001"
        assert profile.json()["section"] == "5CSE-A"

    legacy_login_shape = client.post("/api/auth/login", json={
        "email": "student@campus.test",
        "password": "StudentPass123",
    })
    assert legacy_login_shape.status_code == 200


def test_each_student_receives_only_its_own_profile(identity_client):
    client, manager = identity_client
    first = client.post("/api/management/students", headers=manager, json=student_payload())
    second = client.post(
        "/api/management/students",
        headers=manager,
        json=student_payload(
            usn="1DS23CS002",
            email="student2@campus.test",
            name="Student Two",
            phone="9123456780",
        ),
    )
    assert first.status_code == 201
    assert second.status_code == 201

    login = client.post("/api/auth/login", json={
        "identifier": "1DS23CS002",
        "password": "StudentPass123",
    })
    profile = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert profile.status_code == 200
    assert profile.json()["usn"] == "1DS23CS002"
    assert profile.json()["email"] == "student2@campus.test"
    assert profile.json()["phone"] == "9123456780"


def test_management_validates_student_department_section_duplicates_and_semester(identity_client):
    client, manager = identity_client
    invalid_section = client.post(
        "/api/management/students",
        headers=manager,
        json=student_payload(section_id="section_ise_a"),
    )
    assert invalid_section.status_code == 422

    invalid_department = client.post(
        "/api/management/students",
        headers=manager,
        json=student_payload(department_id="missing"),
    )
    assert invalid_department.status_code == 422

    invalid_semester = client.post(
        "/api/management/students",
        headers=manager,
        json=student_payload(semester=9),
    )
    assert invalid_semester.status_code == 422

    first = client.post("/api/management/students", headers=manager, json=student_payload())
    assert first.status_code == 201
    duplicate_usn = client.post(
        "/api/management/students",
        headers=manager,
        json=student_payload(email="another@campus.test"),
    )
    assert duplicate_usn.status_code == 409
    duplicate_email = client.post(
        "/api/management/students",
        headers=manager,
        json=student_payload(usn="1DS23CS002"),
    )
    assert duplicate_email.status_code == 409


def test_student_filters_update_deactivation_and_password_reset(identity_client):
    client, manager = identity_client
    created = client.post("/api/management/students", headers=manager, json=student_payload())
    assert created.status_code == 201
    student = created.json()

    filtered = client.get(
        "/api/management/students",
        headers=manager,
        params={"department_id": "dept_cse", "semester": 5, "section_id": "section_cse_a"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    updated = client.patch(
        f"/api/management/students/{student['id']}",
        headers=manager,
        json={"name": "Updated Student", "active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Student"
    assert updated.json()["active"] is False

    disabled_login = client.post("/api/auth/login", json={
        "identifier": "1DS23CS001",
        "password": "StudentPass123",
    })
    assert disabled_login.status_code == 403

    reactivated = client.patch(
        f"/api/management/students/{student['id']}",
        headers=manager,
        json={"active": True},
    )
    assert reactivated.status_code == 200
    reset = client.post(
        f"/api/management/students/{student['id']}/password",
        headers=manager,
        json={"password": "ChangedPass123"},
    )
    assert reset.status_code == 200
    changed_login = client.post("/api/auth/login", json={
        "identifier": "1DS23CS001",
        "password": "ChangedPass123",
    })
    assert changed_login.status_code == 200
    existing_token = changed_login.json()["access_token"]
    disabled = client.patch(
        f"/api/management/students/{student['id']}",
        headers=manager,
        json={"active": False},
    )
    assert disabled.status_code == 200
    blocked_session = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {existing_token}"},
    )
    assert blocked_session.status_code == 403


def test_faculty_management_and_employee_id_login(identity_client):
    client, manager = identity_client
    created = client.post("/api/management/faculty", headers=manager, json={
        "employee_id": "emp-cse-17",
        "email": "faculty@campus.test",
        "password": "FacultyPass123",
        "name": "Faculty One",
        "department_id": "dept_cse",
        "designation": "Assistant Professor",
    })
    assert created.status_code == 201, created.text
    faculty = created.json()
    assert faculty["employee_id"] == "EMP-CSE-17"
    assert faculty["account_provisioned"] is True

    login = client.post("/api/auth/login", json={
        "identifier": "emp-cse-17",
        "password": "FacultyPass123",
    })
    assert login.status_code == 200
    profile = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert profile.json()["employee_id"] == "EMP-CSE-17"
    assert profile.json()["designation"] == "Assistant Professor"

    updated = client.patch(
        f"/api/management/faculty/{faculty['id']}",
        headers=manager,
        json={"designation": "Associate Professor", "active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["designation"] == "Associate Professor"
    assert updated.json()["active"] is False


def test_management_routes_reject_student_role(identity_client):
    client, _manager = identity_client
    student = client.post("/api/management/students", headers=_manager, json=student_payload())
    assert student.status_code == 201
    login = client.post("/api/auth/login", json={
        "identifier": "1DS23CS001",
        "password": "StudentPass123",
    })
    token = login.json()["access_token"]
    denied = client.get(
        "/api/management/students",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code == 403


def test_identity_migration_adds_columns_and_preserves_existing_rows():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE students (id VARCHAR PRIMARY KEY, user_id VARCHAR, "
            "section_id VARCHAR, anon_code VARCHAR)"
        ))
        connection.execute(text(
            "CREATE TABLE faculties (id VARCHAR PRIMARY KEY, user_id VARCHAR, "
            "department_id VARCHAR, name VARCHAR, is_synthetic BOOLEAN)"
        ))
        connection.execute(text(
            "INSERT INTO students (id, user_id, section_id, anon_code) "
            "VALUES ('legacy-student', 'legacy-user', 'legacy-section', 'anon')"
        ))
        connection.execute(text(
            "INSERT INTO faculties (id, user_id, department_id, name, is_synthetic) "
            "VALUES ('legacy-faculty', 'legacy-faculty-user', 'dept_cse', 'Faculty', 1)"
        ))

    Base.metadata.create_all(bind=engine)
    migrate_identity_columns(engine)

    with engine.connect() as connection:
        student = connection.execute(text(
            "SELECT id, user_id, section_id, usn FROM students WHERE id = 'legacy-student'"
        )).one()
        faculty = connection.execute(text(
            "SELECT id, user_id, department_id, employee_id FROM faculties "
            "WHERE id = 'legacy-faculty'"
        )).one()
    assert student == ("legacy-student", "legacy-user", "legacy-section", None)
    assert faculty == ("legacy-faculty", "legacy-faculty-user", "dept_cse", None)
    assert {index["name"] for index in inspect(engine).get_indexes("students")} >= {"uq_students_usn"}
    assert {index["name"] for index in inspect(engine).get_indexes("students")} >= {"uq_students_user_id"}
    assert {index["name"] for index in inspect(engine).get_indexes("faculties")} >= {"uq_faculties_employee_id"}
    assert {index["name"] for index in inspect(engine).get_indexes("faculties")} >= {"uq_faculties_user_id"}
    engine.dispose()
