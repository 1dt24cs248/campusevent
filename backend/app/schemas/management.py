"""Management-only schemas for academic master data."""
from pydantic import BaseModel, Field, field_validator


def _required(value: str) -> str:
    result = value.strip()
    if not result:
        raise ValueError("This field cannot be empty.")
    return result


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _required(value)


class DepartmentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _required(value)


class SectionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    department_id: str
    year: int = Field(ge=1, le=8)
    strength: int = Field(ge=1, le=1000)

    @field_validator("code", "name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _required(value)


class SectionUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    department_id: str | None = None
    year: int | None = Field(default=None, ge=1, le=8)
    strength: int | None = Field(default=None, ge=1, le=1000)

    @field_validator("code", "name")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _required(value) if value is not None else None


class SubjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    department_id: str | None = None
    credits: int | None = Field(default=None, ge=0, le=100)
    description: str | None = Field(default=None, max_length=5000)
    kind: str | None = Field(default=None, max_length=40)

    @field_validator("code", "name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _required(value)

    @field_validator("description", "kind")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _required(value)


class SubjectUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    department_id: str | None = None
    credits: int | None = Field(default=None, ge=0, le=100)
    description: str | None = Field(default=None, max_length=5000)
    kind: str | None = Field(default=None, max_length=40)

    @field_validator("code", "name")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _required(value) if value is not None else None

    @field_validator("description", "kind")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _required(value)
