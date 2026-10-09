"""Isolated API tests for campus report workflows; never use the shared campus DB."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.deps import get_db
from app.main import app
from app.models import Block, Floor, Room, User
from app.security import create_access_token


@pytest.fixture()
def action_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    users = [
        User(id="u-management", email="manager@test.local", hashed_password="unused", role="MANAGEMENT", display_name="Manager", active=True, can_view_incidents=False),
        User(id="u-student", email="student@test.local", hashed_password="unused", role="STUDENT", display_name="Student", active=True, can_view_incidents=False),
        User(id="u-student-2", email="student2@test.local", hashed_password="unused", role="STUDENT", display_name="Other Student", active=True, can_view_incidents=False),
        User(id="u-faculty", email="faculty@test.local", hashed_password="unused", role="FACULTY", display_name="Faculty", active=True, can_view_incidents=False),
    ]
    db.add_all(users)
    db.add(Block(id="block_A", code="A", name="Block A", is_active=True, is_pilot=True))
    db.add(Floor(id="floor_A_1", block_id="block_A", level=1, name="1st Floor"))
    db.add(Room(
        id="room_A101", block_id="block_A", floor_id="floor_A_1", code="A101",
        display_name="Classroom A101", aliases=[], resource_type="CLASSROOM",
        capacity=60, allocatable_for_classes=True, reservable_for_events=False,
        facilities=[], status="ACTIVE", is_spare=False,
    ))
    db.commit()
    db.close()

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
        yield client, {
            "management": headers("u-management", "MANAGEMENT"),
            "student": headers("u-student", "STUDENT"),
            "student2": headers("u-student-2", "STUDENT"),
            "faculty": headers("u-faculty", "FACULTY"),
        }, Session

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_maintenance_report_assignment_resolution_and_history(action_client):
    client, tokens, Session = action_client
    created = client.post("/api/reports", headers=tokens["student"], json={
        "report_type": "MAINTENANCE",
        "category": "PROJECTOR / SMART BOARD",
        "description": "Projector is not displaying.",
        "room_id": "room_A101",
    })
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["code"].startswith("ISS-")
    assert report["status"] == "OPEN"
    assert report["priority"] == "MEDIUM"
    assert report["location"].endswith("A101")

    summary = client.get("/api/reports/summary", headers=tokens["management"])
    assert summary.status_code == 200, summary.text
    assert summary.json()["total"] == 1
    assert summary.json()["by_type"]["MAINTENANCE"] == 1

    listed = client.get("/api/reports", headers=tokens["management"])
    assert listed.status_code == 200
    assert any(item["id"] == report["id"] for item in listed.json())

    assigned = client.patch(f"/api/reports/{report['code']}", headers=tokens["management"], json={"assigned_to": "Facilities Team", "status": "ASSIGNED"})
    assert assigned.status_code == 200, assigned.text
    progress = client.patch(f"/api/reports/{report['code']}", headers=tokens["management"], json={"status": "IN_PROGRESS"})
    assert progress.status_code == 200
    resolved = client.patch(f"/api/reports/{report['code']}", headers=tokens["management"], json={"status": "RESOLVED", "resolution_note": "Replaced the projector cable."})
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"]

    mine = client.get("/api/reports", headers=tokens["student"])
    assert any(item["code"] == report["code"] and item["status"] == "RESOLVED" for item in mine.json())
    history = client.get(f"/api/reports/{report['code']}/history", headers=tokens["student"])
    assert history.status_code == 200
    assert {entry["event"] for entry in history.json()} >= {"CREATED", "ASSIGNED", "STATUS_CHANGED"}
    assert all(entry["note"] is None for entry in history.json())

    with Session() as db:
        notification_count = db.query(__import__("app.models.workflow", fromlist=["Notification"]).Notification).filter_by(audience_id="u-student").count()
        assert notification_count >= 3


def test_anonymous_safety_report_is_private_and_encrypted(action_client):
    client, tokens, Session = action_client
    created = client.post("/api/reports", headers=tokens["student"], json={
        "report_type": "SAFETY",
        "category": "Harassment",
        "description": "Repeated harassment near the second-floor corridor.",
        "location_text": "Block A second-floor corridor",
        "anonymous": True,
    })
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["reporter"] == "Anonymous Reporter"
    assert report["severity"] == "MEDIUM"

    inaccessible = client.get(f"/api/reports/{report['code']}", headers=tokens["student2"])
    assert inaccessible.status_code == 404
    detail = client.get(f"/api/reports/{report['code']}", headers=tokens["management"])
    assert detail.status_code == 200
    assert detail.json()["reporter"] == "Anonymous Reporter"
    assert "Repeated harassment" in detail.json()["description"]

    with Session() as db:
        from app.models.safety import Incident
        incident = db.query(Incident).filter_by(id=report["id"]).one()
        assert "Repeated harassment" not in incident.description_enc
        assert incident.status == "SUBMITTED"

    forbidden = client.patch(f"/api/reports/{report['code']}", headers=tokens["student"], json={"status": "RESOLVED"})
    assert forbidden.status_code == 403
    private_note = client.post(f"/api/reports/{report['code']}/notes", headers=tokens["management"], json={"note": "Confidential management note."})
    assert private_note.status_code == 201
    owner_history = client.get(f"/api/reports/{report['code']}/history", headers=tokens["student"])
    assert all("Confidential management note" not in (entry["note"] or "") for entry in owner_history.json())
    manager_history = client.get(f"/api/reports/{report['code']}/history", headers=tokens["management"])
    assert any(entry["note"] == "Confidential management note." for entry in manager_history.json())


def test_emergency_lifecycle_and_rbac(action_client):
    client, tokens, _ = action_client
    created = client.post("/api/emergency", headers=tokens["faculty"], json={
        "category": "Medical Emergency",
        "description": "Immediate medical assistance is required.",
        "room_id": "room_A101",
    })
    assert created.status_code == 201, created.text
    emergency = created.json()
    assert emergency["code"].startswith("ER-")
    assert emergency["status"] == "OPEN"
    assert emergency["severity"] == "CRITICAL"
    reporter_notifications = client.get("/api/notifications", headers=tokens["faculty"])
    assert reporter_notifications.status_code == 200
    assert any("No external emergency service is contacted" in (item.get("body") or "") for item in reporter_notifications.json())

    blocked = client.patch(f"/api/reports/{emergency['code']}", headers=tokens["faculty"], json={"status": "ACKNOWLEDGED"})
    assert blocked.status_code == 403
    assert client.get("/api/reports/summary", headers=tokens["student"]).status_code == 403
    acknowledged = client.patch(f"/api/reports/{emergency['code']}", headers=tokens["management"], json={"status": "ACKNOWLEDGED"})
    assert acknowledged.status_code == 200
    responding = client.patch(f"/api/reports/{emergency['code']}", headers=tokens["management"], json={"status": "RESPONDING"})
    assert responding.status_code == 200
    resolved = client.patch(f"/api/reports/{emergency['code']}", headers=tokens["management"], json={"status": "RESOLVED"})
    assert resolved.status_code == 200
    reporter_reports = client.get("/api/reports", headers=tokens["faculty"])
    assert any(item["code"] == emergency["code"] and item["status"] == "RESOLVED" for item in reporter_reports.json())


def test_student_emergency_contacts_are_private_and_persistent(action_client):
    client, tokens, _Session = action_client
    created = client.post("/api/emergency-contacts", headers=tokens["student"], json={
        "name": "Parent",
        "relationship": "Father",
        "phone_number": "+1 555-0100",
    })
    assert created.status_code == 201, created.text
    contact = created.json()

    refreshed = client.get("/api/emergency-contacts", headers=tokens["student"])
    assert refreshed.status_code == 200
    assert refreshed.json() == [contact]

    assert client.get("/api/emergency-contacts", headers=tokens["student2"]).json() == []
    assert client.patch(
        f"/api/emergency-contacts/{contact['id']}",
        headers=tokens["student2"],
        json={"name": "Hijack"},
    ).status_code == 404
    assert client.delete(
        f"/api/emergency-contacts/{contact['id']}",
        headers=tokens["student2"],
    ).status_code == 404
    assert client.get("/api/emergency-contacts", headers=tokens["management"]).status_code == 403

    updated = client.patch(
        f"/api/emergency-contacts/{contact['id']}",
        headers=tokens["student"],
        json={"relationship": "Guardian"},
    )
    assert updated.status_code == 200
    assert updated.json()["relationship"] == "Guardian"
    assert client.delete(
        f"/api/emergency-contacts/{contact['id']}",
        headers=tokens["student"],
    ).status_code == 204
    assert client.get("/api/emergency-contacts", headers=tokens["student"]).json() == []


def test_navigator_resolves_room_without_graph_node(action_client):
    client, tokens, _Session = action_client

    by_code = client.get("/api/nav/route", headers=tokens["student"], params={"target": "A101"})
    assert by_code.status_code == 200, by_code.text
    assert by_code.json()["location"]["code"] == "A101"
    assert by_code.json()["location"]["floor"] == "1st Floor"
    assert by_code.json()["route_available"] is False
    assert "No mapped turn-by-turn route" in by_code.json()["route"]

    by_id = client.get("/api/nav/route", headers=tokens["student"], params={"target": "room_A101"})
    assert by_id.status_code == 200
    assert by_id.json()["location"]["id"] == "room_A101"


def test_management_ai_uses_live_room_counts_and_is_role_scoped(action_client):
    client, tokens, _Session = action_client

    room_count = client.post("/api/ai/chat", headers=tokens["management"], json={
        "message": "How many campus rooms are registered?",
    })
    assert room_count.status_code == 200
    assert "1 campus rooms registered" in room_count.json()["response"]

    first_floor = client.post("/api/ai/chat", headers=tokens["management"], json={
        "message": "Which rooms are on the 1st floor?",
    })
    assert first_floor.status_code == 200
    assert first_floor.json()["response"] == "Rooms on the 1st floor: A101"

    active_rooms = client.post("/api/ai/chat", headers=tokens["management"], json={
        "message": "What rooms are available?",
    })
    assert active_rooms.json()["response"] == "Rooms marked active and allocatable: A101"

    forbidden = client.post("/api/ai/chat", headers=tokens["student"], json={
        "message": "How many campus rooms are registered?",
    })
    assert forbidden.status_code == 200
    assert "campus rooms registered" not in forbidden.json()["response"]


def test_additive_migration_preserves_existing_action_rows():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE maintenance_tickets (id VARCHAR PRIMARY KEY, code VARCHAR NOT NULL, room_id VARCHAR, category VARCHAR NOT NULL, description VARCHAR NOT NULL, priority VARCHAR, status VARCHAR, reported_by VARCHAR, assigned_to VARCHAR, created_at DATETIME NOT NULL)"))
        connection.execute(text("INSERT INTO maintenance_tickets (id, code, category, description, created_at) VALUES ('legacy-1', 'ISS-LEGACY', 'Other', 'kept', CURRENT_TIMESTAMP)"))
        connection.execute(text("CREATE TABLE incidents (id VARCHAR PRIMARY KEY, code VARCHAR NOT NULL, reporter_user_id VARCHAR, category VARCHAR NOT NULL, description_enc VARCHAR NOT NULL, location_enc VARCHAR, incident_dt DATETIME NOT NULL, evidence_path VARCHAR, status VARCHAR)"))
        connection.execute(text("CREATE TABLE emergency_events (id VARCHAR PRIMARY KEY, user_id VARCHAR, created_at DATETIME NOT NULL, location_text VARCHAR, location_shared BOOLEAN, status VARCHAR)"))

    from app.action_schema import migrate_action_columns
    migrate_action_columns(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("maintenance_tickets")}
    assert {"report_type", "location_text", "updated_at", "resolved_at", "resolution_note"} <= columns
    with engine.connect() as connection:
        assert connection.execute(text("SELECT description FROM maintenance_tickets WHERE id='legacy-1'")).scalar_one() == "kept"
    engine.dispose()


def test_food_menu_is_management_published_and_provenance_labeled(action_client):
    client, tokens, _ = action_client
    forbidden = client.post("/api/food/locations", headers=tokens["student"], json={
        "room_id": "room_A101", "name": "Test Cafe",
    })
    assert forbidden.status_code == 403
    location = client.post("/api/food/locations", headers=tokens["management"], json={
        "room_id": "room_A101", "name": "Test Cafe", "opening_hours": "08:00-17:00",
    })
    assert location.status_code == 201, location.text
    menu_item = client.post(f"/api/food/locations/{location.json()['id']}/menu", headers=tokens["management"], json={
        "menu_date": date.today().isoformat(), "item": "Test menu entry", "price": 35, "dietary": "VEGETARIAN",
    })
    assert menu_item.status_code == 201, menu_item.text
    menu = client.get("/api/food", headers=tokens["student"], params={"date": date.today().isoformat()})
    assert menu.status_code == 200
    entry = next(item for item in menu.json() if item["item"] == "Test menu entry")
    assert entry["room_code"] == "A101"
    assert entry["provenance"] == "MANAGEMENT_CURATED"
