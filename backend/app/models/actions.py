from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String

from app.db import Base


class ReportHistory(Base):
    __tablename__ = "report_histories"

    id = Column(String, primary_key=True)
    report_type = Column(String, nullable=False)
    report_id = Column(String, nullable=False, index=True)
    event = Column(String, nullable=False)
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    changed_by = Column(String, ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime, nullable=False)
    note = Column(String, nullable=True)
    internal = Column(Boolean, nullable=False, default=False)


class FoodLocation(Base):
    __tablename__ = "food_locations"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    name = Column(String, nullable=False)
    location_text = Column(String, nullable=True)
    description = Column(String, nullable=True)
    opening_hours = Column(String, nullable=True)
    provenance = Column(String, nullable=False, default="MANAGEMENT_CURATED")
    active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)


class FoodMenu(Base):
    __tablename__ = "food_menus"

    id = Column(String, primary_key=True)
    location_id = Column(String, ForeignKey("food_locations.id"), nullable=False, index=True)
    menu_date = Column(Date, nullable=False, index=True)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False, default="DRAFT", index=True)
    published_at = Column(DateTime, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class FoodMenuItem(Base):
    __tablename__ = "food_menu_items"

    id = Column(String, primary_key=True)
    location_id = Column(String, ForeignKey("food_locations.id"), nullable=False)
    menu_id = Column(String, ForeignKey("food_menus.id"), nullable=True, index=True)
    menu_date = Column(Date, nullable=False, index=True)
    item = Column(String, nullable=False)
    category = Column(String, nullable=False, default="OTHER")
    description = Column(String, nullable=True)
    price = Column(Numeric(8, 2), nullable=True)
    dietary = Column(String, nullable=True)
    dietary_note = Column(String, nullable=True)
    available = Column(Boolean, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
