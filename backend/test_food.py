"""Isolated tests for the management-controlled campus food workflow."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.deps import get_db
from app.food_schema import migrate_food_schema
from app.main import app
from app.models import Block, Floor, Room, User
from app.models.actions import FoodMenu, FoodMenuItem
from app.models.workflow import Notification
from app.security import create_access_token


@pytest.fixture()
def food_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        db.add_all([
            User(id="food-manager", email="manager@food.test", hashed_password="unused", role="MANAGEMENT", display_name="Synthetic Manager", active=True, can_view_incidents=False),
            User(id="food-student-a", email="student-a@food.test", hashed_password="unused", role="STUDENT", display_name="Synthetic Student A", active=True, can_view_incidents=False),
            User(id="food-student-b", email="student-b@food.test", hashed_password="unused", role="STUDENT", display_name="Synthetic Student B", active=True, can_view_incidents=False),
            User(id="food-faculty-a", email="faculty-a@food.test", hashed_password="unused", role="FACULTY", display_name="Synthetic Faculty A", active=True, can_view_incidents=False),
            User(id="food-faculty-b", email="faculty-b@food.test", hashed_password="unused", role="FACULTY", display_name="Synthetic Faculty B", active=True, can_view_incidents=False),
        ])
        db.add(Block(id="food-block", code="SYN", name="Synthetic Block", is_active=True, is_pilot=True))
        db.add(Floor(id="food-floor", block_id="food-block", level=1, name="Synthetic Floor"))
        db.add(Room(
            id="food-room", block_id="food-block", floor_id="food-floor",
            code="SYN-101", display_name="Synthetic Food Hall", aliases=[],
            resource_type="CAFETERIA", status="ACTIVE",
        ))
        db.commit()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    def headers(user_id: str, role: str) -> dict[str, str]:
        token = create_access_token({"sub": user_id, "role": role})
        return {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        yield client, {
            "management": headers("food-manager", "MANAGEMENT"),
            "student_a": headers("food-student-a", "STUDENT"),
            "student_b": headers("food-student-b", "STUDENT"),
            "faculty_a": headers("food-faculty-a", "FACULTY"),
            "faculty_b": headers("food-faculty-b", "FACULTY"),
        }, session_factory

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _create_stall(client, management_headers):
    response = client.post("/api/food/stalls", headers=management_headers, json={
        "room_id": "food-room",
        "name": "Synthetic Test Canteen",
        "location_text": "Synthetic Block near Room SYN-101",
        "description": "Synthetic food stall used only by isolated tests.",
    })
    assert response.status_code == 201, response.text
    return response.json()


def _create_menu(client, management_headers, location_id, menu_date=None):
    response = client.post("/api/food/menus", headers=management_headers, json={
        "location_id": location_id,
        "menu_date": (menu_date or date.today()).isoformat(),
        "title": "Synthetic Lunch",
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_stalls_and_menu_workflow_are_management_only(food_client):
    client, tokens, _ = food_client
    stall = _create_stall(client, tokens["management"])
    for role in ("student_a", "faculty_a"):
        denied_create = client.post("/api/food/stalls", headers=tokens[role], json={
            "room_id": "food-room", "name": "Unauthorized Stall",
        })
        assert denied_create.status_code == 403
        denied_list = client.get("/api/food/stalls", headers=tokens[role])
        assert denied_list.status_code == 403

    menu = _create_menu(client, tokens["management"], stall["id"])
    assert menu["status"] == "DRAFT"
    for role in ("student_a", "faculty_a"):
        assert client.get("/api/food/menus", headers=tokens[role]).json() == []
        assert client.get(
            f"/api/food/menus/{menu['id']}", headers=tokens[role]
        ).status_code == 404
        denied_edit = client.patch(
            f"/api/food/menus/{menu['id']}", headers=tokens[role],
            json={"title": "Unauthorized edit"},
        )
        assert denied_edit.status_code == 403

    bad_price = client.post(
        f"/api/food/menus/{menu['id']}/items",
        headers=tokens["management"],
        json={"item": "Invalid item", "price": -1},
    )
    assert bad_price.status_code == 422
    for label, price, available in (
        ("Synthetic Veg Meal", 60, True),
        ("Synthetic Paneer Roll", 40, False),
    ):
        added = client.post(
            f"/api/food/menus/{menu['id']}/items",
            headers=tokens["management"],
            json={
                "item": label,
                "category": "LUNCH" if "Meal" in label else "SNACK",
                "description": "Synthetic test menu item.",
                "price": price,
                "dietary": "VEGETARIAN",
                "dietary_note": "Synthetic test data.",
                "available": available,
            },
        )
        assert added.status_code == 201, added.text

    assert client.get("/api/food/menus", headers=tokens["student_a"]).json() == []
    assert client.get("/api/food/menus", headers=tokens["faculty_a"]).json() == []
    published = client.post(
        f"/api/food/menus/{menu['id']}/publish", headers=tokens["management"]
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "PUBLISHED"
    assert {item["item"] for item in published.json()["items"]} == {
        "Synthetic Veg Meal", "Synthetic Paneer Roll",
    }
    assert next(
        item for item in published.json()["items"]
        if item["item"] == "Synthetic Paneer Roll"
    )["available"] is False

    for role in ("student_a", "student_b", "faculty_a", "faculty_b"):
        visible = client.get(
            "/api/food/menus", headers=tokens[role],
            params={"date": date.today().isoformat()},
        )
        assert visible.status_code == 200, visible.text
        assert [entry["id"] for entry in visible.json()] == [menu["id"]]

    for role in ("student_a", "faculty_a"):
        assert client.get(
            f"/api/food/menus/{menu['id']}", headers=tokens[role]
        ).json()["status"] == "PUBLISHED"
        assert client.patch(
            f"/api/food/menu-items/{published.json()['items'][0]['id']}",
            headers=tokens[role], json={"price": 1},
        ).status_code == 403
        assert client.post(
            f"/api/food/menus/{menu['id']}/unpublish", headers=tokens[role]
        ).status_code == 403

    notices_a = client.get("/api/notifications", headers=tokens["student_a"])
    notices_b = client.get("/api/notifications", headers=tokens["faculty_b"])
    assert any(entry["type"] == "FOOD_MENU" for entry in notices_a.json())
    assert any(entry["type"] == "FOOD_MENU" for entry in notices_b.json())

    unpublished = client.post(
        f"/api/food/menus/{menu['id']}/unpublish", headers=tokens["management"]
    )
    assert unpublished.status_code == 200
    assert unpublished.json()["status"] == "UNPUBLISHED"
    assert client.get("/api/food/menus", headers=tokens["student_a"]).json() == []
    assert client.get("/api/food/menus", headers=tokens["faculty_a"]).json() == []


def test_menu_date_filter_and_stall_activation(food_client):
    client, tokens, _ = food_client
    stall = _create_stall(client, tokens["management"])
    yesterday = date.today() - timedelta(days=1)
    today_menu = _create_menu(client, tokens["management"], stall["id"], date.today())
    yesterday_menu = _create_menu(client, tokens["management"], stall["id"], yesterday)
    for menu in (today_menu, yesterday_menu):
        assert client.post(
            f"/api/food/menus/{menu['id']}/items",
            headers=tokens["management"],
            json={"item": "Synthetic Item", "price": 0},
        ).status_code == 201
        assert client.post(
            f"/api/food/menus/{menu['id']}/publish",
            headers=tokens["management"],
        ).status_code == 200

    today = client.get(
        "/api/food/menus", headers=tokens["student_a"],
        params={"date": date.today().isoformat()},
    )
    assert {menu["id"] for menu in today.json()} == {today_menu["id"]}
    previous = client.get(
        "/api/food/menus", headers=tokens["faculty_a"],
        params={"date": yesterday.isoformat()},
    )
    assert {menu["id"] for menu in previous.json()} == {yesterday_menu["id"]}

    deactivated = client.patch(
        f"/api/food/stalls/{stall['id']}", headers=tokens["management"],
        json={"active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False
    assert client.get(
        "/api/food/menus", headers=tokens["student_a"],
        params={"date": date.today().isoformat()},
    ).json() == []


def test_management_can_edit_draft_stall_menu_and_items(food_client):
    client, tokens, _ = food_client
    stall = _create_stall(client, tokens["management"])
    updated_stall = client.patch(
        f"/api/food/stalls/{stall['id']}", headers=tokens["management"],
        json={"name": "Synthetic Updated Stall", "location_text": None, "description": None},
    )
    assert updated_stall.status_code == 200, updated_stall.text
    assert updated_stall.json()["name"] == "Synthetic Updated Stall"
    assert updated_stall.json()["location_text"] is None

    menu = _create_menu(client, tokens["management"], stall["id"])
    updated_menu = client.patch(
        f"/api/food/menus/{menu['id']}", headers=tokens["management"],
        json={"title": "Synthetic Updated Lunch", "menu_date": date.today().isoformat()},
    )
    assert updated_menu.status_code == 200, updated_menu.text
    assert updated_menu.json()["title"] == "Synthetic Updated Lunch"

    item = client.post(
        f"/api/food/menus/{menu['id']}/items",
        headers=tokens["management"],
        json={"item": "Synthetic Editable Item", "price": 20},
    )
    assert item.status_code == 201, item.text
    updated_item = client.patch(
        f"/api/food/menu-items/{item.json()['id']}",
        headers=tokens["management"],
        json={"price": 25, "available": False, "description": "Updated synthetic item."},
    )
    assert updated_item.status_code == 200, updated_item.text
    item_data = updated_item.json()["items"][0]
    assert item_data["price"] == 25
    assert item_data["available"] is False
    assert item_data["description"] == "Updated synthetic item."

    removed = client.delete(
        f"/api/food/menu-items/{item.json()['id']}", headers=tokens["management"]
    )
    assert removed.status_code == 204
    assert client.get(
        f"/api/food/menus/{menu['id']}", headers=tokens["management"]
    ).json()["items"] == []


def test_food_notifications_are_role_scoped_and_publish_requires_items(food_client):
    client, tokens, session_factory = food_client
    stall = _create_stall(client, tokens["management"])
    menu = _create_menu(client, tokens["management"], stall["id"])
    assert client.post(
        f"/api/food/menus/{menu['id']}/publish",
        headers=tokens["management"],
    ).status_code == 409
    assert client.get(
        "/api/food/menus", headers=tokens["management"],
    ).json()[0]["status"] == "DRAFT"

    client.post(
        f"/api/food/menus/{menu['id']}/items",
        headers=tokens["management"],
        json={"item": "Synthetic Beverage", "price": 10, "category": "BEVERAGE"},
    )
    client.post(
        f"/api/food/menus/{menu['id']}/publish", headers=tokens["management"]
    )

    with session_factory() as db:
        role_audiences = {
            (entry.audience_type, entry.audience_id)
            for entry in db.query(Notification).filter_by(type="FOOD_MENU").all()
        }
        assert role_audiences == {("ROLE", "STUDENT"), ("ROLE", "FACULTY")}


def test_food_schema_migrates_legacy_items_without_losing_them():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            """
            CREATE TABLE food_locations (
                id VARCHAR PRIMARY KEY, room_id VARCHAR NOT NULL, name VARCHAR NOT NULL,
                opening_hours VARCHAR, provenance VARCHAR NOT NULL, active BOOLEAN NOT NULL,
                created_by VARCHAR NOT NULL, created_at DATETIME NOT NULL
            )
            """
        ))
        connection.execute(text(
            """
            CREATE TABLE food_menu_items (
                id VARCHAR PRIMARY KEY, location_id VARCHAR NOT NULL,
                menu_date DATE NOT NULL, item VARCHAR NOT NULL, price NUMERIC,
                dietary VARCHAR, available BOOLEAN, created_by VARCHAR NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        ))
        connection.execute(text(
            """
            CREATE TABLE food_menus (
                id VARCHAR PRIMARY KEY, location_id VARCHAR NOT NULL,
                menu_date DATE NOT NULL, title VARCHAR NOT NULL, status VARCHAR NOT NULL,
                published_at DATETIME, created_by VARCHAR NOT NULL,
                created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO food_locations
                (id, room_id, name, provenance, active, created_by, created_at)
            VALUES ('legacy-stall', 'legacy-room', 'Legacy Synthetic Stall',
                    'MANAGEMENT_CURATED', 1, 'manager', '2026-01-02 08:00:00')
            """
        ))
        connection.execute(text(
            """
            INSERT INTO food_menu_items
                (id, location_id, menu_date, item, price, created_by, created_at)
            VALUES ('legacy-item', 'legacy-stall', '2026-01-02', 'Legacy item',
                    25, 'manager', '2026-01-02 08:00:00')
            """
        ))

    migrate_food_schema(engine)
    migrate_food_schema(engine)
    columns = {
        table: {column["name"] for column in inspect(engine).get_columns(table)}
        for table in ("food_locations", "food_menu_items")
    }
    assert {"location_text", "description", "updated_at"} <= columns["food_locations"]
    assert {"menu_id", "category", "description", "dietary_note"} <= columns["food_menu_items"]
    with engine.connect() as connection:
        legacy_item = connection.execute(text(
            "SELECT menu_id, category, item FROM food_menu_items WHERE id='legacy-item'"
        )).one()
        assert legacy_item.menu_id is not None, (
            legacy_item,
            connection.execute(text("SELECT id, status FROM food_menus")).all(),
        )
        legacy_menu = connection.execute(text(
            "SELECT status, title FROM food_menus WHERE id=:id"
        ), {"id": legacy_item.menu_id}).one()
    assert legacy_item.item == "Legacy item"
    assert legacy_item.category == "OTHER"
    assert legacy_menu.status == "PUBLISHED"
    assert legacy_menu.title == "Previously published menu"
    engine.dispose()
