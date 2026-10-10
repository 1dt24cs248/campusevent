"""Isolated end-to-end tests for scenario publication, rollback, and scoping."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.clock import get_now
from app.deps import get_db
from app.main import app
from app.models import (
    Block,
    Department,
    Faculty,
    FacultyTeachingEligibility,
    Floor,
    Room,
    Section,
    Student,
    Subject,
    User,
)
from app.models.identity import AuditLog
from app.models.schedule import SessionOverride, TimetableEntry
from app.models.faculty_work import (
    FacultySubjectAssignment,
    FacultySubjectRequest,
    FacultySubjectRequestItem,
)
from app.models.scenario import PublishedVersion
from app.models.workflow import Notification
from app.security import create_access_token
from app.timetable_lock import acquire_timetable_state_lock
from app.routers.scenarios import _timetable_state_fingerprint


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
                code="A101", display_name="Classroom A101", aliases=[],
                resource_type="CLASSROOM", capacity=50, capacity_provenance="PROVIDED",
                allocatable_for_classes=True,
                reservable_for_events=False, facilities=[], status="ACTIVE", is_spare=False,
            ),
            Room(
                id="life-room-201", block_id="life-block", floor_id="life-floor-2",
                code="V201", display_name="Validation Room 201", aliases=[],
                resource_type="CLASSROOM", capacity=60, capacity_provenance="PROVIDED",
                allocatable_for_classes=True,
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
        client, manager, "Close A101", "ROOM_UNAVAILABLE", "ROOM_UNAVAILABLE",
        {
            "room_ids": ["life-room-101"],
            "weekdays": [0, 1, 2, 3, 4, 5],
            "time_from": "08:00",
            "time_to": "18:00",
        },
    )
    assert simulation["affected_count"] == 1
    result = simulation["options"][0]
    assert result["run_id"]
    assert result["result_rows"][0]["status"] == "REASSIGNED"
    assert result["result_rows"][0]["subject_code"] == "VAL101"
    assert result["result_rows"][0]["original_room_code"] == "A101"
    assert result["result_rows"][0]["assigned_room_code"] == "V201"
    assert result["result_rows"][0]["original_room_capacity_provenance"] == "PROVIDED"
    assert result["result_rows"][0]["room_capacity_provenance"] == "PROVIDED"
    assert result["result_rows"][0]["reason"]
    with session_factory() as db:
        assert db.query(TimetableEntry).filter_by(id="life-entry").one().base_room_id == "life-room-101"
        assert db.query(SessionOverride).count() == 0

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
        scheduled_date = override.date.date().isoformat()
        assert date.fromisoformat(scheduled_date).weekday() == date.today().weekday()
        assert db.query(AuditLog).filter_by(
            action="APPROVE_PUBLISH", entity_id=publication["version_id"],
        ).count() == 1

    published_timetable = client.get(
        "/api/timetable/me", headers=tokens["student"], params={"date": scheduled_date},
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
        "/api/timetable/me", headers=tokens["student"], params={"date": scheduled_date},
    )
    assert reverted_timetable.status_code == 200, reverted_timetable.text
    assert reverted_timetable.json()[0]["effective_room_code"] == "A101"

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
    assert floor_row["original_room_code"] == "A101"
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


def test_move_class_slot_is_returned_and_published(scenario_client):
    client, tokens, session_factory = scenario_client
    manager = tokens["management"]
    scenario, simulation = _create_and_simulate(
        client, manager, "Move validation class", "MOVE_CLASS", "MOVE_CLASS",
        {"entry_id": "life-entry", "new_start_slot": "P2"},
    )
    result = simulation["options"][0]
    assert result["status"] == "FEASIBLE"
    assert result["result_rows"][0]["start_slot"] == "P2"
    assert result["result_rows"][0]["start_time"] == "10:25"

    published = client.post(
        f"/api/scenarios/{scenario['id']}/approve-publish",
        headers=manager,
        json={"run_id": result["run_id"], "comment": "Publish slot change."},
    )
    assert published.status_code == 200, published.text
    assert published.json()["overrides_created"] == 1
    assert published.json()["notifications_created"] == 2
    with session_factory() as db:
        override = db.query(SessionOverride).filter_by(
            version_id=published.json()["version_id"], entry_id="life-entry",
        ).one()
        assert override.room_id == "life-room-101"
        assert override.start_slot_override == "P2"
        assert {
            notice.type for notice in db.query(Notification).all()
        } == {"CLASS_TIME_CHANGED"}


def test_affected_classes_reject_section_faculty_and_occupied_room_conflicts(scenario_client):
    client, tokens, session_factory = scenario_client
    with session_factory() as db:
        db.add(TimetableEntry(
            id="life-conflicting-entry",
            section_id="life-section",
            subject_id="life-subject",
            faculty_id="life-faculty-record",
            weekday=date.today().weekday(),
            start_slot="P1",
            duration_slots=1,
            kind="THEORY",
            base_room_id="life-room-201",
            required_facilities=[],
        ))
        db.commit()

    scenario, simulation = _create_and_simulate(
        client, tokens["management"], "Close conflicted room",
        "ROOM_UNAVAILABLE", "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101"], "time_from": "00:00", "time_to": "23:59"},
    )
    result = simulation["options"][0]
    assert result["status"] == "PARTIAL"
    unresolved = result["unresolved"][0]
    assert "Faculty conflict" in unresolved["reason"]
    assert "Section conflict" in unresolved["reason"]
    occupied_room = next(
        candidate for candidate in unresolved["near_miss_rooms"]
        if candidate["room"] == "V201"
    )
    assert any("occupied during" in reason for reason in occupied_room["reasons"])
    rejected_publish = client.post(
        f"/api/scenarios/{scenario['id']}/approve-publish",
        headers=tokens["management"],
        json={"run_id": result["run_id"]},
    )
    assert rejected_publish.status_code == 400


def test_insufficient_verified_capacity_leaves_class_unresolved(scenario_client):
    client, tokens, session_factory = scenario_client
    with session_factory() as db:
        db.query(Room).filter_by(id="life-room-201").one().capacity = 30
        db.commit()

    _, simulation = _create_and_simulate(
        client, tokens["management"], "Close A101 with undersized alternative",
        "ROOM_UNAVAILABLE", "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101"], "weekdays": [0, 1, 2, 3, 4, 5],
         "time_from": "08:00", "time_to": "18:00"},
    )
    result = simulation["options"][0]
    assert simulation["affected_count"] == 1
    assert result["status"] == "PARTIAL"
    assert result["assignments"] == {}
    assert result["unresolved"][0]["entry_id"] == "life-entry"
    alternative = next(
        room for room in result["unresolved"][0]["near_miss_rooms"]
        if room["room"] == "V201"
    )
    assert "capacity 30 < strength 40" in alternative["reasons"]


def test_no_suitable_room_returns_unresolved_and_cannot_be_published(scenario_client):
    client, tokens, _ = scenario_client
    scenario, simulation = _create_and_simulate(
        client, tokens["management"], "Close A101 and only alternative",
        "ROOM_UNAVAILABLE", "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101", "life-room-201"],
         "weekdays": [0, 1, 2, 3, 4, 5],
         "time_from": "08:00", "time_to": "18:00"},
    )
    result = simulation["options"][0]
    assert simulation["affected_count"] == 1
    assert result["status"] == "PARTIAL"
    assert result["unresolved"][0]["entry_id"] == "life-entry"
    unavailable_alternative = next(
        room for room in result["unresolved"][0]["near_miss_rooms"]
        if room["room"] == "V201"
    )
    assert any("unavailable" in reason for reason in unavailable_alternative["reasons"])
    response = client.post(
        f"/api/scenarios/{scenario['id']}/approve-publish",
        headers=tokens["management"],
        json={"run_id": result["run_id"]},
    )
    assert response.status_code == 400


def test_zero_affected_classes_are_explained_and_cannot_be_published(scenario_client):
    client, tokens, session_factory = scenario_client
    with session_factory() as db:
        db.query(TimetableEntry).filter_by(id="life-entry").one().base_room_id = None
        db.commit()

    scenario, simulation = _create_and_simulate(
        client, tokens["management"], "Close empty A101",
        "ROOM_UNAVAILABLE", "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101"], "weekdays": [0, 1, 2, 3, 4, 5],
         "time_from": "08:00", "time_to": "18:00"},
    )
    result = simulation["options"][0]
    assert simulation["affected_count"] == 0
    assert "0 classes affected" in simulation["change_descriptions"][0]
    response = client.post(
        f"/api/scenarios/{scenario['id']}/approve-publish",
        headers=tokens["management"],
        json={"run_id": result["run_id"]},
    )
    assert response.status_code == 400
    assert "No scheduled classes were affected" in response.json()["detail"]


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

    refreshed_simulation = client.post(
        f"/api/scenarios/{stale['id']}/simulate",
        headers=manager,
        json={"strategies": ["MIN_DISRUPTION"], "time_limit_sec": 2},
    )
    assert refreshed_simulation.status_code == 200, refreshed_simulation.text
    publish_refreshed = client.post(
        f"/api/scenarios/{stale['id']}/approve-publish",
        headers=manager,
        json={"run_id": refreshed_simulation.json()["options"][0]["run_id"]},
    )
    assert publish_refreshed.status_code == 200, publish_refreshed.text


def test_changed_floor_level_after_simulation_requires_resimulation(scenario_client):
    client, tokens, session_factory = scenario_client
    scenario, simulation = _create_and_simulate(
        client, tokens["management"], "Changed floor level", "ROOM_UNAVAILABLE",
        "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101"], "time_from": "00:00", "time_to": "23:59"},
    )
    with session_factory() as db:
        original_fingerprint = _timetable_state_fingerprint(db)
        floor = db.query(Floor).filter_by(id="life-floor-2").one()
        floor.level = 3
        db.commit()
        changed_fingerprint = _timetable_state_fingerprint(db)

    assert changed_fingerprint != original_fingerprint
    response = client.post(
        f"/api/scenarios/{scenario['id']}/approve-publish",
        headers=tokens["management"],
        json={"run_id": simulation["options"][0]["run_id"]},
    )
    assert response.status_code == 409
    assert "Run the simulation again" in response.json()["detail"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("faculty_id", "life-other-faculty-record"),
        ("section_id", "life-other-section"),
        ("base_room_id", "life-room-201"),
        ("start_slot", "P2"),
    ],
    ids=["faculty-assignment", "section-assignment", "room-assignment", "time-slot"],
)
def test_timetable_assignment_changes_after_simulation_require_resimulation(
    scenario_client, field, value
):
    client, tokens, session_factory = scenario_client
    scenario, simulation = _create_and_simulate(
        client, tokens["management"], "Outdated timetable", "ROOM_UNAVAILABLE",
        "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101"], "time_from": "00:00", "time_to": "23:59"},
    )
    with session_factory() as db:
        entry = db.query(TimetableEntry).filter_by(id="life-entry").one()
        setattr(entry, field, value)
        db.commit()

    response = client.post(
        f"/api/scenarios/{scenario['id']}/approve-publish",
        headers=tokens["management"],
        json={"run_id": simulation["options"][0]["run_id"]},
    )
    assert response.status_code == 409
    assert "Run the simulation again" in response.json()["detail"]


def test_faculty_subject_publication_after_simulation_requires_resimulation(scenario_client):
    client, tokens, session_factory = scenario_client
    scenario, simulation = _create_and_simulate(
        client, tokens["management"], "Outdated faculty assignment", "ROOM_UNAVAILABLE",
        "ROOM_UNAVAILABLE",
        {"room_ids": ["life-room-101"], "time_from": "00:00", "time_to": "23:59"},
    )
    with session_factory() as db:
        request = FacultySubjectRequest(
            id="life-fsr",
            faculty_id="life-other-faculty-record",
            status="PENDING",
            created_at=get_now(),
            updated_at=get_now(),
        )
        item = FacultySubjectRequestItem(
            id="life-fsri",
            request_id=request.id,
            subject_id="life-subject",
            preferred_section_ids=[],
            availability={},
            periods_per_week=1,
            status="ASSIGNED",
            created_at=request.created_at,
            updated_at=request.updated_at,
        )
        db.add_all([
            request,
            item,
            FacultyTeachingEligibility(
                id="life-eligibility",
                faculty_id="life-other-faculty-record",
                academic_year=2,
                section_id=None,
            ),
            FacultySubjectAssignment(
                id="life-fsa",
                request_item_id=item.id,
                section_id="life-section",
                room_id="life-room-201",
                weekday=date.today().weekday(),
                start_slot="P3",
                duration_slots=1,
                timetable_entry_id=None,
                created_at=request.created_at,
            ),
        ])
        db.commit()

    workflow_publish = client.post(
        "/api/management/faculty-subject-requests/life-fsr/items/life-fsri/publish",
        headers=tokens["management"],
    )
    assert workflow_publish.status_code == 200, workflow_publish.text
    assert workflow_publish.json()["items"][0]["status"] == "PUBLISHED"
    with session_factory() as db:
        assert db.query(TimetableEntry).filter_by(
            faculty_id="life-other-faculty-record",
            section_id="life-section",
        ).count() == 1

    response = client.post(
        f"/api/scenarios/{scenario['id']}/approve-publish",
        headers=tokens["management"],
        json={"run_id": simulation["options"][0]["run_id"]},
    )
    assert response.status_code == 409
    assert "Run the simulation again" in response.json()["detail"]

    refreshed_simulation = client.post(
        f"/api/scenarios/{scenario['id']}/simulate",
        headers=tokens["management"],
        json={"strategies": ["MIN_DISRUPTION"], "time_limit_sec": 2},
    )
    assert refreshed_simulation.status_code == 200, refreshed_simulation.text
    publish_refreshed = client.post(
        f"/api/scenarios/{scenario['id']}/approve-publish",
        headers=tokens["management"],
        json={"run_id": refreshed_simulation.json()["options"][0]["run_id"]},
    )
    assert publish_refreshed.status_code == 200, publish_refreshed.text


def test_timetable_lock_serializes_concurrent_writers(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'timetable-lock.db'}",
        connect_args={"timeout": 0.05},
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    first = session_factory()
    second = session_factory()
    try:
        acquire_timetable_state_lock(first)
        with pytest.raises(OperationalError, match="locked"):
            acquire_timetable_state_lock(second)
        first.commit()
        acquire_timetable_state_lock(second)
        second.commit()
    finally:
        first.close()
        second.close()
        engine.dispose()
