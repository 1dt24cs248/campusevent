"""Campus food locations and management-controlled menus."""
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.clock import get_now
from app.deps import get_current_user, get_db, require_roles
from app.models.actions import FoodLocation, FoodMenu, FoodMenuItem
from app.models.campus import Room
from app.models.identity import User
from app.models.workflow import Notification
from app.schemas.actions import (
    FoodLocationCreate,
    FoodLocationUpdate,
    FoodMenuCreate,
    FoodMenuItemCreate,
    FoodMenuUpdate,
    ManagedFoodMenuItemCreate,
    ManagedFoodMenuItemUpdate,
)

router = APIRouter()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _location_response(db: Session, location: FoodLocation) -> dict[str, Any]:
    room = db.query(Room).filter(Room.id == location.room_id).first()
    return {
        "id": location.id,
        "name": location.name,
        "room_id": location.room_id,
        "room_code": room.code if room else None,
        "display_name": room.display_name if room else None,
        "location_text": location.location_text,
        "location": location.location_text or (room.display_name if room else "Location not recorded"),
        "description": location.description,
        "opening_hours": location.opening_hours,
        "provenance": location.provenance,
        "active": location.active,
        "created_at": location.created_at,
        "updated_at": location.updated_at,
    }


def _menu_response(db: Session, menu: FoodMenu) -> dict[str, Any]:
    location = db.query(FoodLocation).filter(FoodLocation.id == menu.location_id).first()
    if location is None:
        raise HTTPException(status_code=409, detail="The menu's food stall no longer exists.")
    items = db.query(FoodMenuItem).filter(FoodMenuItem.menu_id == menu.id).order_by(
        FoodMenuItem.category, FoodMenuItem.item
    ).all()
    return {
        "id": menu.id,
        "location_id": location.id,
        "stall": _location_response(db, location),
        "title": menu.title,
        "menu_date": menu.menu_date,
        "status": menu.status,
        "published_at": menu.published_at,
        "created_by": menu.created_by,
        "created_at": menu.created_at,
        "updated_at": menu.updated_at,
        "item_count": len(items),
        "items": [{
            "id": item.id,
            "menu_id": menu.id,
            "item": item.item,
            "category": item.category or "OTHER",
            "description": item.description,
            "price": item.price,
            "dietary": item.dietary,
            "dietary_note": item.dietary_note,
            "available": item.available if item.available is not None else True,
        } for item in items],
    }


def _create_stall(
    db: Session,
    user: User,
    body: FoodLocationCreate,
) -> FoodLocation:
    room = db.query(Room).filter(Room.id == body.room_id, Room.status == "ACTIVE").first()
    if not room:
        raise HTTPException(status_code=422, detail="Select an active campus room for this food stall.")
    now = get_now()
    location = FoodLocation(
        id=_id("food"),
        room_id=room.id,
        name=body.name,
        location_text=body.location_text,
        description=body.description,
        opening_hours=body.opening_hours,
        provenance="MANAGEMENT_CURATED",
        active=True,
        created_by=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(location)
    log_audit(
        db, user.id, "CREATE_FOOD_LOCATION", "FoodLocation", location.id,
        {"name": location.name, "room_id": room.id}, role=user.role,
    )
    return location


def _require_editable_menu(db: Session, menu_id: str) -> FoodMenu:
    menu = db.query(FoodMenu).filter(FoodMenu.id == menu_id).first()
    if menu is None:
        raise HTTPException(status_code=404, detail="Food menu not found.")
    if menu.status == "PUBLISHED":
        raise HTTPException(status_code=409, detail="Unpublish this menu before editing it.")
    return menu


@router.get("/food/locations")
def food_locations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    locations = db.query(FoodLocation).filter(
        FoodLocation.active.is_(True)
    ).order_by(FoodLocation.name).all()
    return [_location_response(db, location) for location in locations]


@router.get("/food/stalls")
def management_food_stalls(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    locations = db.query(FoodLocation).order_by(FoodLocation.name).all()
    return [_location_response(db, location) for location in locations]


@router.post("/food/stalls", status_code=status.HTTP_201_CREATED)
@router.post("/food/locations", status_code=status.HTTP_201_CREATED)
def create_food_stall(
    body: FoodLocationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    location = _create_stall(db, user, body)
    db.commit()
    db.refresh(location)
    return _location_response(db, location)


@router.patch("/food/stalls/{location_id}")
def update_food_stall(
    location_id: str,
    body: FoodLocationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    location = db.query(FoodLocation).filter(FoodLocation.id == location_id).first()
    if location is None:
        raise HTTPException(status_code=404, detail="Food stall not found.")
    changes = body.model_dump(exclude_unset=True)
    if any(changes.get(field) is None for field in ("room_id", "name", "active") if field in changes):
        raise HTTPException(status_code=422, detail="Room, name, and active status cannot be cleared.")
    if "room_id" in changes:
        room_id = changes.pop("room_id")
        room = db.query(Room).filter(Room.id == room_id, Room.status == "ACTIVE").first()
        if room is None:
            raise HTTPException(status_code=422, detail="Select an active campus room for this food stall.")
        location.room_id = room.id
    for field, value in changes.items():
        setattr(location, field, value)
    location.updated_at = get_now()
    log_audit(
        db, user.id, "UPDATE_FOOD_LOCATION", "FoodLocation", location.id,
        {"updated_fields": sorted(body.model_fields_set)}, role=user.role,
    )
    db.commit()
    db.refresh(location)
    return _location_response(db, location)


@router.get("/food/menus")
def list_food_menus(
    menu_date: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(FoodMenu).join(
        FoodLocation, FoodLocation.id == FoodMenu.location_id
    )
    if user.role != "MANAGEMENT":
        query = query.filter(
            FoodMenu.status == "PUBLISHED",
            FoodLocation.active.is_(True),
        )
        menu_date = menu_date or get_now().date()
    if menu_date is not None:
        query = query.filter(FoodMenu.menu_date == menu_date)
    menus = query.order_by(FoodMenu.menu_date.desc(), FoodLocation.name, FoodMenu.title).all()
    return [_menu_response(db, menu) for menu in menus]


@router.post("/food/menus", status_code=status.HTTP_201_CREATED)
def create_food_menu(
    body: FoodMenuCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    location = db.query(FoodLocation).filter(
        FoodLocation.id == body.location_id,
        FoodLocation.active.is_(True),
    ).first()
    if location is None:
        raise HTTPException(status_code=404, detail="Active food stall not found.")
    now = get_now()
    menu = FoodMenu(
        id=_id("fmenu"),
        location_id=location.id,
        menu_date=body.menu_date,
        title=body.title,
        status="DRAFT",
        created_by=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(menu)
    log_audit(
        db, user.id, "CREATE_FOOD_MENU", "FoodMenu", menu.id,
        {"location_id": location.id, "menu_date": body.menu_date.isoformat()},
        role=user.role,
    )
    db.commit()
    db.refresh(menu)
    return _menu_response(db, menu)


@router.patch("/food/menus/{menu_id}")
def update_food_menu(
    menu_id: str,
    body: FoodMenuUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    menu = _require_editable_menu(db, menu_id)
    changes = body.model_dump(exclude_unset=True)
    if any(changes.get(field) is None for field in ("item", "category", "price") if field in changes):
        raise HTTPException(status_code=422, detail="Item name, category, and price cannot be cleared.")
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Menu fields cannot be cleared.")
    if "location_id" in changes:
        location = db.query(FoodLocation).filter(
            FoodLocation.id == changes["location_id"],
            FoodLocation.active.is_(True),
        ).first()
        if location is None:
            raise HTTPException(status_code=404, detail="Active food stall not found.")
    for field, value in changes.items():
        setattr(menu, field, value)
    menu.updated_at = get_now()
    log_audit(
        db, user.id, "UPDATE_FOOD_MENU", "FoodMenu", menu.id,
        {"updated_fields": sorted(body.model_fields_set)}, role=user.role,
    )
    db.commit()
    db.refresh(menu)
    return _menu_response(db, menu)


@router.get("/food/menus/{menu_id}")
def get_food_menu(
    menu_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(FoodMenu).join(
        FoodLocation, FoodLocation.id == FoodMenu.location_id
    ).filter(FoodMenu.id == menu_id)
    if user.role != "MANAGEMENT":
        query = query.filter(
            FoodMenu.status == "PUBLISHED",
            FoodLocation.active.is_(True),
        )
    menu = query.first()
    if menu is None:
        raise HTTPException(status_code=404, detail="Food menu not found.")
    return _menu_response(db, menu)


@router.post("/food/menus/{menu_id}/items", status_code=status.HTTP_201_CREATED)
def create_food_menu_item(
    menu_id: str,
    body: ManagedFoodMenuItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    menu = _require_editable_menu(db, menu_id)
    item = FoodMenuItem(
        id=_id("fitem"),
        location_id=menu.location_id,
        menu_id=menu.id,
        menu_date=menu.menu_date,
        item=body.item,
        category=body.category,
        description=body.description,
        price=body.price,
        dietary=body.dietary,
        dietary_note=body.dietary_note,
        available=body.available,
        created_by=user.id,
        created_at=get_now(),
    )
    menu.updated_at = get_now()
    db.add(item)
    log_audit(
        db, user.id, "CREATE_FOOD_MENU_ITEM", "FoodMenuItem", item.id,
        {"menu_id": menu.id}, role=user.role,
    )
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "menu_id": menu.id,
        "item": item.item,
        "category": item.category,
        "price": item.price,
        "available": item.available,
    }


@router.patch("/food/menu-items/{item_id}")
def update_food_menu_item(
    item_id: str,
    body: ManagedFoodMenuItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    item = db.query(FoodMenuItem).filter(FoodMenuItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Food menu item not found.")
    menu = _require_editable_menu(db, item.menu_id) if item.menu_id else None
    if menu is None:
        raise HTTPException(status_code=409, detail="Legacy menu items cannot be edited through this endpoint.")
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(item, field, value)
    menu.updated_at = get_now()
    log_audit(
        db, user.id, "UPDATE_FOOD_MENU_ITEM", "FoodMenuItem", item.id,
        {"updated_fields": sorted(body.model_fields_set)}, role=user.role,
    )
    db.commit()
    db.refresh(item)
    return _menu_response(db, menu)


@router.delete("/food/menu-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food_menu_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    item = db.query(FoodMenuItem).filter(FoodMenuItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Food menu item not found.")
    menu = _require_editable_menu(db, item.menu_id) if item.menu_id else None
    if menu is None:
        raise HTTPException(status_code=409, detail="Legacy menu items cannot be removed through this endpoint.")
    db.delete(item)
    menu.updated_at = get_now()
    db.commit()


@router.post("/food/menus/{menu_id}/publish")
def publish_food_menu(
    menu_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    menu = db.query(FoodMenu).filter(FoodMenu.id == menu_id).first()
    if menu is None:
        raise HTTPException(status_code=404, detail="Food menu not found.")
    location = db.query(FoodLocation).filter(
        FoodLocation.id == menu.location_id,
        FoodLocation.active.is_(True),
    ).first()
    if location is None:
        raise HTTPException(status_code=409, detail="Activate the food stall before publishing its menu.")
    item_count = db.query(FoodMenuItem).filter(FoodMenuItem.menu_id == menu.id).count()
    if item_count == 0:
        raise HTTPException(status_code=409, detail="Add at least one menu item before publishing.")
    if menu.status != "PUBLISHED":
        now = get_now()
        menu.status = "PUBLISHED"
        menu.published_at = now
        menu.updated_at = now
        for role in ("STUDENT", "FACULTY"):
            db.add(Notification(
                id=_id("notif"),
                audience_type="ROLE",
                audience_id=role,
                type="FOOD_MENU",
                title="Campus Food Menu Published",
                body=f"'{menu.title}' at {location.name} is published for {menu.menu_date.isoformat()}.",
                payload={"menu_id": menu.id, "location_id": location.id},
                created_at=now,
            ))
        log_audit(
            db, user.id, "PUBLISH_FOOD_MENU", "FoodMenu", menu.id,
            {"location_id": location.id}, role=user.role,
        )
        db.commit()
        db.refresh(menu)
    return _menu_response(db, menu)


@router.post("/food/menus/{menu_id}/unpublish")
def unpublish_food_menu(
    menu_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    menu = db.query(FoodMenu).filter(FoodMenu.id == menu_id).first()
    if menu is None:
        raise HTTPException(status_code=404, detail="Food menu not found.")
    if menu.status == "PUBLISHED":
        menu.status = "UNPUBLISHED"
        menu.updated_at = get_now()
        log_audit(
            db, user.id, "UNPUBLISH_FOOD_MENU", "FoodMenu", menu.id,
            {"location_id": menu.location_id}, role=user.role,
        )
        db.commit()
        db.refresh(menu)
    return _menu_response(db, menu)


@router.get("/food")
@router.get("/food/menu")
def legacy_food_menu(
    menu_date: date | None = Query(default=None, alias="date"),
    location_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    menu_date = menu_date or get_now().date()
    query = db.query(FoodMenu).join(
        FoodLocation, FoodLocation.id == FoodMenu.location_id
    ).filter(
        FoodMenu.menu_date == menu_date,
        FoodMenu.status == "PUBLISHED",
        FoodLocation.active.is_(True),
    )
    if location_id:
        query = query.filter(FoodLocation.id == location_id)
    entries = []
    for menu in query.order_by(FoodLocation.name, FoodMenu.title).all():
        response = _menu_response(db, menu)
        for item in response["items"]:
            entries.append({
                "id": item["id"],
                "location_id": menu.location_id,
                "location_name": response["stall"]["name"],
                "room_code": response["stall"]["room_code"],
                "display_name": response["stall"]["display_name"],
                "location_text": response["stall"]["location_text"],
                "opening_hours": response["stall"]["opening_hours"],
                "menu_date": menu.menu_date,
                "menu_title": menu.title,
                "item": item["item"],
                "category": item["category"],
                "description": item["description"],
                "price": item["price"],
                "dietary": item["dietary"],
                "dietary_note": item["dietary_note"],
                "available": item["available"],
                "provenance": response["stall"]["provenance"],
            })
    return entries


@router.post("/food/locations/{location_id}/menu", status_code=status.HTTP_201_CREATED)
def create_legacy_food_menu_item(
    location_id: str,
    body: FoodMenuItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    location = db.query(FoodLocation).filter(
        FoodLocation.id == location_id,
        FoodLocation.active.is_(True),
    ).first()
    if location is None:
        raise HTTPException(status_code=404, detail="Food location not found.")
    now = get_now()
    menu = db.query(FoodMenu).filter(
        FoodMenu.location_id == location.id,
        FoodMenu.menu_date == body.menu_date,
        FoodMenu.status == "PUBLISHED",
        FoodMenu.title == "Management-published items",
    ).first()
    if menu is None:
        menu = FoodMenu(
            id=_id("fmenu"),
            location_id=location.id,
            menu_date=body.menu_date,
            title="Management-published items",
            status="PUBLISHED",
            published_at=now,
            created_by=user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(menu)
        db.flush()
    item = FoodMenuItem(
        id=_id("fitem"),
        location_id=location.id,
        menu_id=menu.id,
        menu_date=body.menu_date,
        item=body.item,
        category="OTHER",
        price=body.price,
        dietary=body.dietary,
        available=body.available if body.available is not None else True,
        created_by=user.id,
        created_at=now,
    )
    menu.updated_at = now
    db.add(item)
    log_audit(
        db, user.id, "PUBLISH_FOOD_MENU_ITEM", "FoodMenuItem", item.id,
        {"location_id": location.id, "date": body.menu_date.isoformat()},
        role=user.role,
    )
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "location_id": location.id,
        "menu_id": menu.id,
        "menu_date": item.menu_date,
        "item": item.item,
        "provenance": location.provenance,
    }
