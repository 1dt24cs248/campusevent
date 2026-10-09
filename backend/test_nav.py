"""Isolated behavioral coverage for campus location lookup and map routing."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.deps import get_db
from app.main import app
from app.models import Block, Floor, Room, User
from app.models.navigation import NavEdge, NavNode
from app.security import create_access_token


@pytest.fixture()
def navigator_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        db.add(User(
            id="nav-student", email="nav-student@test.local",
            hashed_password="unused", role="STUDENT", active=True,
            can_view_incidents=False,
        ))
        db.add(Block(
            id="nav-block", code="V", name="Validation Block",
            is_active=True, is_pilot=True,
        ))
        db.add_all([
            Floor(id="nav-basement", block_id="nav-block", level=-1, name="-1st Floor"),
            Floor(id="nav-first", block_id="nav-block", level=1, name="1st Floor"),
            Floor(id="nav-second", block_id="nav-block", level=2, name="2nd Floor"),
        ])
        db.add_all([
            Room(
                id="room-v101", block_id="nav-block", floor_id="nav-first",
                code="V101", display_name="Validation Classroom",
                aliases=["Lab Annex"], resource_type="CLASSROOM", capacity=70,
                allocatable_for_classes=True, reservable_for_events=False,
                facilities=[], status="ACTIVE", is_spare=False,
            ),
            Room(
                id="room-v201", block_id="nav-block", floor_id="nav-second",
                code="V201", display_name="Validation Seminar Hall",
                aliases=[], resource_type="SEMINAR_HALL", capacity=90,
                allocatable_for_classes=True, reservable_for_events=True,
                facilities=[], status="ACTIVE", is_spare=False,
            ),
            Room(
                id="room-basement", block_id="nav-block", floor_id="nav-basement",
                code="B01", display_name="Basement Laboratory", aliases=[],
                resource_type="LAB", capacity=40, allocatable_for_classes=True,
                reservable_for_events=False, facilities=[], status="ACTIVE",
                is_spare=False,
            ),
        ])
        db.add_all([
            NavNode(
                id="nav-entrance", block_id="nav-block",
                floor_id="nav-first", kind="ENTRANCE",
            ),
            NavNode(
                id="nav-v101", block_id="nav-block",
                floor_id="nav-first", room_id="room-v101", kind="ROOM",
            ),
        ])
        db.add(NavEdge(
            id="nav-edge-1", from_node_id="nav-entrance",
            to_node_id="nav-v101", cost=2,
        ))
        db.commit()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    token = create_access_token({"sub": "nav-student", "role": "STUDENT"})
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        yield client, headers

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_room_lookup_by_code_and_id_includes_actual_block_and_floor(navigator_client):
    client, headers = navigator_client
    for target in ("V101", "room-v101"):
        response = client.get(
            "/api/nav/route", params={"target": target}, headers=headers,
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["location"]["id"] == "room-v101"
        assert result["location"]["block"] == "Validation Block"
        assert result["location"]["floor"] == "1st Floor"
        assert result["location"]["resource_type"] == "CLASSROOM"
        assert result["route_available"] is False
        assert "No mapped turn-by-turn route available." in result["route"]


def test_room_list_and_floor_filter_return_only_real_floor_records(navigator_client):
    client, _ = navigator_client
    all_rooms = client.get("/api/rooms")
    assert all_rooms.status_code == 200
    assert {room["id"] for room in all_rooms.json()} == {
        "room-v101", "room-v201", "room-basement",
    }

    first_floor = client.get("/api/rooms", params={"floor_id": "nav-first"})
    assert first_floor.status_code == 200
    assert [room["id"] for room in first_floor.json()] == ["room-v101"]

    unknown_floor = client.get("/api/rooms", params={"floor_id": "missing-floor"})
    assert unknown_floor.status_code == 404


def test_basement_location_and_existing_graph_route(navigator_client):
    client, headers = navigator_client
    basement = client.get(
        "/api/nav/route", params={"target": "room-basement"}, headers=headers,
    )
    assert basement.status_code == 200
    assert basement.json()["location"]["floor"] == "Basement"

    nodes = client.get("/api/nav/nodes", headers=headers)
    assert nodes.status_code == 200
    assert {node["id"] for node in nodes.json()} == {"nav-entrance", "nav-v101"}

    route = client.get(
        "/api/nav/route",
        params={"target": "V101", "start_node_id": "nav-entrance"},
        headers=headers,
    )
    assert route.status_code == 200
    assert route.json()["route_available"] is True
    assert route.json()["route"] == "Entrance -> V101"
