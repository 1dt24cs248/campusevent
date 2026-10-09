"""Additive, idempotent migrations for academic portal metadata."""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


ACADEMIC_COLUMNS = {
    "subjects": {
        "description": "TEXT",
        "credits": "INTEGER",
    },
    "assessments": {
        "description": "TEXT",
        "maximum_marks": "NUMERIC(8, 2)",
        "created_by": "VARCHAR",
        "status": "VARCHAR NOT NULL DEFAULT 'PUBLISHED'",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
        "is_synthetic": "BOOLEAN NOT NULL DEFAULT 0",
        "provenance": "VARCHAR",
    },
    "announcements": {
        "section_id": "VARCHAR",
    },
}


def migrate_academic_schema(engine: Engine) -> None:
    """Add nullable metadata without rewriting existing academic records."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    table_columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in ACADEMIC_COLUMNS
        if table in tables
    }
    with engine.begin() as connection:
        for table, columns in ACADEMIC_COLUMNS.items():
            if table not in tables:
                continue
            for name, sql_type in columns.items():
                if name not in table_columns[table]:
                    connection.execute(
                        text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}')
                    )
