"""Isolated end-to-end tests for scenario publication, rollback, and scoping."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.deps import get_db
from app.main import app
from app.models import Block, Department, Faculty, Floor, Room, Section, Student, Subject, User
from app.models.identity import AuditLog
from app.models.schedule import SessionOverride, TimetableEntry
from app.models.scenario import PublishedVersion
from app.models.workflow import Notification
from app.security import create_access_token


@pytest.fixture()
def scenario_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        db.add_all([
            User(id="life-manager", email="manager@lifecycle.test", hashed_password="unused",
                 role="MANAGEMENT", display_name="Lifecycle Manager", active=True,
                 can_view_incidents=False),
            User(id="life-student", email="student@lifecycle.test", hashed_password="unused",
                 role="STUDENT", display_name="Affected Student", active=True,
                 can_view_incidents=False),
            User(id="life-other-student", email="other@lifecycle.test", hashed_password="unused",
                 role="STUDENT", display_name="Unrelated Student", active=True,
                 can_view_incidents=False),
            User(id="life-faculty", email="faculty@lifecycle.test", hashed_password="unused",
                 role="FACULTY", display_name="Affected Faculty", active=True,
                 can_view_incidents=False),
            User(id="life-other-faculty", email="other-faculty@lifecycle.test",
                 hashed_password="unused", role="FACULTY", display_name="Unrelated Faculty",
                 active=True, can_view_incidents=False),
            Department(id="life-dept", name="Validation Department"),
            Block(id="life-block", code="V", name="Validation Block",
                  is_active=True, is_pilot=True),
            Floor(id="life-floor-1", block_id="life-block", level=1, name="1st Floor"),
            Floor(id="life-floor-2", block_id="life-block", level=2, name="2nd Floor"),
        ])
        db.add_all([
            Room(
                id="life-room-101", block_id="life-block", floor_id="life-floor-1",
                code="V101", display_name="Validation Room 101", aliases=[],
                resource_type="CLASSROOM", capacity=50, allocatable_for_classes=True,
                reservable_for_events=False, facilities=[], status="ACTIVE", is_spare=False,
            ),
            Room(
                id="life-room-201", block_id="life-block", floor_id="life-floor-2",
                code="V201", display_name="Validation Room 201", aliases=[],
                resource_type="CLASSROOM", capacity=60, allocatable_for_classes=True,
                reservable_for_events=False, facilities=[], status="ACTIVE", is_spare=False,
            ),
            Section(
                id="life-section", department_id="life-dept", code="VAL-A",
                name="Validation Section A", year=2, strength=40,
            ),
            Section(
                id="life-other-section", department_id="life-dept", code="VAL-B",
                name="Validation Section B", year=2, strength=20,
            ),
            Subject(id="life-subject", code="VAL101", name="Validation Subject",
                    department_id="life-dept", required_facilities=[]),
            Faculty(id="life-faculty-record", user_id="life-faculty",
                    department_id="life-dept", employee_id="LIFE-1",
                    name="Affected Faculty"),
            Faculty(id="life-other-faculty-record", user_id="life-other-faculty",
                    department_id="life-dept", employee_id="LIFE-2",
                    name="Unrelated Faculty"),
        ])
        db.flush()
        db.add_all([
            Student(id="life-student-record", user_id="life-student",
                    section_id="life-section", usn="LIFE001", semester=3,
                    academic_status="ACTIVE"),
            Student(id="life-other-student-record", user_id="life-other-student",
                    section_id="life-other-section", usn="LIFE002", semester=3,
                    academic_status="ACTIVE"),
            TimetableEntry(
                id="life-entry", section_id="life-section", subject_id="life-subject",
                faculty_id="life-faculty-record", weekday=date.today().weekday(),
                start_slot="P1", duration_slots=1, kind="THEORY",
                base_room_id="life-room-101", required_facilities=[],
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
    tokens = {
        alias: {
            "Authorization": f"Bearer {create_access_token({'sub': user_id, 'role': role})}"
        }
        for alias, user_id, role in (
            ("management", "life-manager", "MANAGEMENT"),
            ("student", "life-student", "STUDENT"),
            ("other_student", "life-other-student", "STUDENT"),
            ("faculty", "life-faculty", "FACULTY"),
            ("other_faculty", "life-other-faculty", "FACULTY"),
        )
    }
    with TestClient(app) as client:
        yield client, tokens, session_factory

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _create_and_simulate(client, management, name, category, change_type, payload):
    scenario_response = client.post("/api/scenarios", headers=management, json={
        "name": name,
        "category": category,
        "changes": [{"type": change_type, "payload": payload}],
    })
    assert scenario_response.status_code == 200, scenario_response.text
    scenario = scenario_response.json()
    simulation = client.post(
        f"/api/scenarios/{scenario['id']}/simulate",
        headers=management,
        json={"strategies": ["MIN_DISRUPTION"], "time_limit_sec": 2},
    )
    assert simulation.status_code == 200, simulation.text
    return scenario, simulation.json()


def test_room_unavailable_publish_revert_notifications_and_rbac(scenario_client):
    client, tokens, session_factory = scenario_client
    manager = tokens["management"]
    scenario, simulation = _create_and_simulate(
        client, manager, "Close V101", "ROOM_UNAVAILABLE", "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101"], "time_from": "00:00", "time_to": "23:59"},
    )
    assert simulation["affected_count"] == 1
    result = simulation["options"][0]
    assert result["run_id"]
    assert result["result_rows"][0]["status"] == "REASSIGNED"
    assert result["result_rows"][0]["subject_code"] == "VAL101"
    assert result["result_rows"][0]["original_room_code"] == "V101"
    assert result["result_rows"][0]["assigned_room_code"] == "V201"
    assert result["result_rows"][0]["reason"]

    assert client.post(
        f"/api/scenarios/{scenario['id']}/review", headers=manager,
    ).json()["status"] == "REVIEWED"
    published = client.post(
        f"/api/scenarios/{scenario['id']}/approve-publish",
        headers=manager,
        json={"run_id": result["run_id"], "comment": "Reviewed isolated validation result."},
    )
    assert published.status_code == 200, published.text
    publication = published.json()
    assert publication["overrides_created"] == 1
    assert publication["notifications_created"] == 2
    assert client.get("/api/scenarios", headers=manager).status_code == 200

    versions = client.get("/api/versions", headers=manager)
    assert versions.status_code == 200
    assert versions.json()[0]["id"] == publication["version_id"]
    with session_factory() as db:
        override = db.query(SessionOverride).filter_by(
            version_id=publication["version_id"], entry_id="life-entry",
        ).one()
        assert override.active is True
        assert override.old_room_id == "life-room-101"
        assert override.room_id == "life-room-201"
        assert db.query(AuditLog).filter_by(
            action="APPROVE_PUBLISH", entity_id=publication["version_id"],
        ).count() == 1

    today = date.today().isoformat()
    published_timetable = client.get(
        "/api/timetable/me", headers=tokens["student"], params={"date": today},
    )
    assert published_timetable.status_code == 200, published_timetable.text
    assert published_timetable.json()[0]["effective_room_code"] == "V201"

    affected_student_notifications = client.get(
        "/api/notifications", headers=tokens["student"],
    ).json()
    unrelated_student_notifications = client.get(
        "/api/notifications", headers=tokens["other_student"],
    ).json()
    assert any(item["type"] == "ROOM_CHANGED" for item in affected_student_notifications)
    assert not any(item["type"] == "ROOM_CHANGED" for item in unrelated_student_notifications)
    affected_faculty_notifications = client.get(
        "/api/notifications", headers=tokens["faculty"],
    ).json()
    unrelated_faculty_notifications = client.get(
        "/api/notifications", headers=tokens["other_faculty"],
    ).json()
    assert any(item["type"] == "ROOM_CHANGED" for item in affected_faculty_notifications)
    assert not any(item["type"] == "ROOM_CHANGED" for item in unrelated_faculty_notifications)

    reverted = client.post(
        f"/api/versions/{publication['version_id']}/revert", headers=manager,
    )
    assert reverted.status_code == 200, reverted.text
    assert reverted.json() == {"ok": True, "reverted_overrides": 1}
    with session_factory() as db:
        override = db.query(SessionOverride).filter_by(
            version_id=publication["version_id"], entry_id="life-entry",
        ).one()
        version = db.query(PublishedVersion).filter_by(id=publication["version_id"]).one()
        assert override.active is False
        assert version.reverted is True
        assert db.query(AuditLog).filter_by(
            action="REVERT_VERSION", entity_id=publication["version_id"],
        ).count() == 1
        revert_notifications = db.query(Notification).filter_by(
            type="VERSION_REVERTED",
        ).all()
        assert {
            (notification.audience_type, notification.audience_id)
            for notification in revert_notifications
        } == {
            ("SECTION", "life-section"),
            ("FACULTY", "life-faculty-record"),
        }
    reverted_timetable = client.get(
        "/api/timetable/me", headers=tokens["student"], params={"date": today},
    )
    assert reverted_timetable.status_code == 200, reverted_timetable.text
    assert reverted_timetable.json()[0]["effective_room_code"] == "V101"

    for role in ("student", "faculty"):
        affected_notifications = client.get(
            "/api/notifications", headers=tokens[role],
        ).json()
        unrelated_notifications = client.get(
            "/api/notifications", headers=tokens[f"other_{role}"],
        ).json()
        assert any(
            item["type"] == "VERSION_REVERTED"
            for item in affected_notifications
        )
        assert not any(
            item["type"] == "VERSION_REVERTED"
            for item in unrelated_notifications
        )

    for role in ("student", "faculty"):
        assert client.get("/api/scenarios", headers=tokens[role]).status_code == 403
        assert client.post(
            "/api/scenarios", headers=tokens[role], json={"name": "Denied", "changes": []},
        ).status_code == 403


def test_floor_unavailable_and_stress_metrics_are_data_derived(scenario_client):
    client, tokens, _ = scenario_client
    manager = tokens["management"]
    floor_scenario, floor_result = _create_and_simulate(
        client, manager, "Close floor 1", "FLOOR_UNAVAILABLE", "FLOOR_UNAVAILABLE",
        {"floor_id": "life-floor-1"},
    )
    assert floor_result["affected_count"] == 1
    floor_row = floor_result["options"][0]["result_rows"][0]
    assert floor_row["timetable_entry_id"] == "life-entry"
    assert floor_row["original_room_code"] == "V101"
    assert floor_row["status"] == "REASSIGNED"
    assert floor_row["assigned_room_code"] == "V201"
    assert floor_scenario["base_version_id"] is None

    _, stress_result = _create_and_simulate(
        client, manager, "Close busiest room", "STRESS_TEST", "STRESS_TEST", {"k": 1},
    )
    stress = stress_result["options"][0]
    metrics = stress["metrics"]
    assert stress_result["affected_count"] == 1
    assert metrics["stress_condition"]
    for key in (
        "conflict_count_before", "conflict_count_after",
        "utilization_before", "utilization_after",
        "capacity_pressure_before", "capacity_pressure_after",
        "reassigned_classes", "unchanged_classes", "unresolved_classes",
    ):
        assert key in metrics
    assert metrics["conflict_count_before"] == 0
    assert metrics["conflict_count_after"] == 0
    assert metrics["utilization_before"] == 0.8
    assert metrics["utilization_after"] == 0.6667
    assert metrics["capacity_pressure_before"] == 0
    assert metrics["capacity_pressure_after"] == 0
    assert metrics["reassigned_classes"] == 1
    assert metrics["unchanged_classes"] == 0
    assert metrics["unresolved_classes"] == 0
    assert stress["result_rows"][0]["status"] == "REASSIGNED"


def test_stale_scenario_publish_returns_conflict(scenario_client):
    client, tokens, _ = scenario_client
    manager = tokens["management"]
    stale, stale_simulation = _create_and_simulate(
        client, manager, "Stale close", "ROOM_UNAVAILABLE", "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101"], "time_from": "00:00", "time_to": "23:59"},
    )
    current, current_simulation = _create_and_simulate(
        client, manager, "Current close", "ROOM_UNAVAILABLE", "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101"], "time_from": "00:00", "time_to": "23:59"},
    )
    assert stale["base_version_id"] == current["base_version_id"]
    assert client.post(
        f"/api/scenarios/{current['id']}/review", headers=manager,
    ).status_code == 200
    publish_current = client.post(
        f"/api/scenarios/{current['id']}/approve-publish",
        headers=manager,
        json={"run_id": current_simulation["options"][0]["run_id"]},
    )
    assert publish_current.status_code == 200, publish_current.text

    assert client.post(
        f"/api/scenarios/{stale['id']}/review", headers=manager,
    ).status_code == 200
    publish_stale = client.post(
        f"/api/scenarios/{stale['id']}/approve-publish",
        headers=manager,
        json={"run_id": stale_simulation["options"][0]["run_id"]},
    )
    assert publish_stale.status_code == 409
    assert "Stale version" in publish_stale.json()["detail"]
