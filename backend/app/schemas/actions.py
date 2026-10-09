from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ReportType = Literal["MAINTENANCE", "GENERAL", "SAFETY"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class ReportCreate(BaseModel):
    report_type: ReportType
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=3, max_length=8000)
    room_id: str | None = None
    location_text: str | None = Field(default=None, max_length=300)
    anonymous: bool = False

    @field_validator("category", "description")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator("location_text")
    @classmethod
    def trim_location(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class EmergencyCreate(BaseModel):
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=3, max_length=4000)
    room_id: str | None = None
    location_text: str | None = Field(default=None, max_length=300)

    @field_validator("category", "description")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class EmergencyContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relationship: str = Field(min_length=1, max_length=80)
    phone_number: str = Field(min_length=5, max_length=30, pattern=r"^[+]?[\d() .-]+$")

    @field_validator("name", "relationship", "phone_number")
    @classmethod
    def trim_contact_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class EmergencyContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    relationship: str | None = Field(default=None, min_length=1, max_length=80)
    phone_number: str | None = Field(default=None, min_length=5, max_length=30, pattern=r"^[+]?[\d() .-]+$")

    @field_validator("name", "relationship", "phone_number")
    @classmethod
    def trim_updated_contact_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class ReportUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=30)
    priority: Priority | None = None
    severity: Priority | None = None
    assigned_to: str | None = Field(default=None, max_length=120)
    resolution_note: str | None = Field(default=None, max_length=2000)

    @field_validator("assigned_to", "resolution_note")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ReportNote(BaseModel):
    note: str = Field(min_length=1, max_length=2000)

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Note cannot be empty.")
        return value


class FoodLocationCreate(BaseModel):
    room_id: str
    name: str = Field(min_length=2, max_length=120)
    opening_hours: str | None = Field(default=None, max_length=120)
    location_text: str | None = Field(default=None, max_length=240)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Location name cannot be empty.")
        return value

    @field_validator("opening_hours", "location_text", "description")
    @classmethod
    def trim_optional_food_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class FoodLocationUpdate(BaseModel):
    room_id: str | None = None
    name: str | None = Field(default=None, min_length=2, max_length=120)
    opening_hours: str | None = Field(default=None, max_length=120)
    location_text: str | None = Field(default=None, max_length=240)
    description: str | None = Field(default=None, max_length=1000)
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def trim_updated_food_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Location name cannot be empty.")
        return value

    @field_validator("opening_hours", "location_text", "description")
    @classmethod
    def trim_updated_food_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class FoodMenuCreate(BaseModel):
    location_id: str
    menu_date: date
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def trim_menu_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Menu title cannot be empty.")
        return value


class FoodMenuUpdate(BaseModel):
    location_id: str | None = None
    menu_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def trim_updated_menu_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Menu title cannot be empty.")
        return value


FoodCategory = Literal["BREAKFAST", "LUNCH", "SNACK", "BEVERAGE", "OTHER"]
FoodDietary = Literal["VEGETARIAN", "NON_VEGETARIAN", "VEGAN", "OTHER"]


class ManagedFoodMenuItemCreate(BaseModel):
    item: str = Field(min_length=1, max_length=120)
    category: FoodCategory = "OTHER"
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal = Field(ge=0, le=99999)
    dietary: FoodDietary = "OTHER"
    dietary_note: str | None = Field(default=None, max_length=500)
    available: bool = True

    @field_validator("item")
    @classmethod
    def trim_managed_food_item(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Menu item cannot be empty.")
        return value

    @field_validator("description", "dietary_note")
    @classmethod
    def trim_managed_food_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ManagedFoodMenuItemUpdate(BaseModel):
    item: str | None = Field(default=None, min_length=1, max_length=120)
    category: FoodCategory | None = None
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal | None = Field(default=None, ge=0, le=99999)
    dietary: FoodDietary | None = None
    dietary_note: str | None = Field(default=None, max_length=500)
    available: bool | None = None

    @field_validator("item")
    @classmethod
    def trim_updated_managed_food_item(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Menu item cannot be empty.")
        return value

    @field_validator("description", "dietary_note")
    @classmethod
    def trim_updated_managed_food_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class FoodMenuItemCreate(BaseModel):
    item: str = Field(min_length=1, max_length=120)
    menu_date: date
    price: Decimal | None = Field(default=None, ge=0, le=99999)
    dietary: Literal["VEGETARIAN", "NON_VEGETARIAN", "VEGAN", "OTHER"] | None = None
    available: bool | None = None

    @field_validator("item")
    @classmethod
    def trim_item(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Menu item cannot be empty.")
        return value


class FoodMenuItemResponse(BaseModel):
    id: str
    location_id: str
    location_name: str
    room_code: str
    display_name: str
    opening_hours: str | None
    menu_date: date
    item: str
    price: Decimal | None
    dietary: str | None
    available: bool | None
    provenance: str


class ReportHistoryResponse(BaseModel):
    event: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: str
    note: str | None
