"""Additive event workflow columns for existing campus databases."""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


EVENT_COLUMNS = {
    "location": "VARCHAR",
    "organizer": "VARCHAR",
    "created_by": "VARCHAR",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
    "decision_reason": "VARCHAR",
    "decided_by": "VARCHAR",
    "decided_at": "DATETIME",
    "notes": "VARCHAR",
}


def migrate_event_columns(engine: Engine) -> None:
    """Add nullable metadata columns without changing existing event rows."""
    inspector = inspect(engine)
    if not inspector.has_table("events"):
        return
    existing = {column["name"] for column in inspector.get_columns("events")}
    with engine.begin() as connection:
        for name, sql_type in EVENT_COLUMNS.items():
            if name not in existing:
                connection.execute(
                    text(f'ALTER TABLE "events" ADD COLUMN "{name}" {sql_type}')
                )
