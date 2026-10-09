"""Safe additive migrations for legacy action tables."""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


ACTION_COLUMNS = {
    "maintenance_tickets": {
        "report_type": "VARCHAR",
        "location_text": "VARCHAR",
        "updated_at": "DATETIME",
        "resolved_at": "DATETIME",
        "resolution_note": "VARCHAR",
    },
    "incidents": {
        "anonymous": "BOOLEAN",
        "location_room_id": "VARCHAR",
        "severity": "VARCHAR",
        "priority": "VARCHAR",
        "assigned_to": "VARCHAR",
        "updated_at": "DATETIME",
        "resolved_at": "DATETIME",
        "resolution_note": "VARCHAR",
    },
    "emergency_events": {
        "code": "VARCHAR",
        "category": "VARCHAR",
        "description_enc": "VARCHAR",
        "room_id": "VARCHAR",
        "severity": "VARCHAR",
        "priority": "VARCHAR",
        "assigned_to": "VARCHAR",
        "updated_at": "DATETIME",
        "resolved_at": "DATETIME",
        "resolution_note": "VARCHAR",
    },
}


def migrate_action_columns(engine: Engine) -> None:
    """Add only missing nullable columns; existing rows and tables are preserved."""
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in ACTION_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}'))
