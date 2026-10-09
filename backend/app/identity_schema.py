"""Additive schema upgrades for institutional student and faculty identities."""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


IDENTITY_COLUMNS = {
    "students": {
        "usn": "VARCHAR",
        "phone": "VARCHAR",
        "program": "VARCHAR",
        "semester": "INTEGER",
        "admission_year": "INTEGER",
        "academic_status": "VARCHAR",
        "profile": "JSON",
    },
    "faculties": {
        "employee_id": "VARCHAR",
        "designation": "VARCHAR",
    },
}

UNIQUE_IDENTIFIERS = (
    ("students", "usn", "uq_students_usn"),
    ("students", "user_id", "uq_students_user_id"),
    ("faculties", "employee_id", "uq_faculties_employee_id"),
    ("faculties", "user_id", "uq_faculties_user_id"),
)


def migrate_identity_columns(engine: Engine) -> None:
    """Add nullable identity fields and uniqueness indexes without rewriting rows."""
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in IDENTITY_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.execute(
                        text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}')
                    )

        for table, column, index_name in UNIQUE_IDENTIFIERS:
            if not inspector.has_table(table):
                continue
            duplicates = connection.execute(text(
                f'SELECT "{column}", COUNT(*) FROM "{table}" '
                f'WHERE "{column}" IS NOT NULL GROUP BY "{column}" HAVING COUNT(*) > 1 LIMIT 1'
            )).first()
            if duplicates:
                raise RuntimeError(
                    f"Cannot add {index_name}: duplicate {column} value "
                    f"{duplicates[0]!r} exists in {table}."
                )
            connection.execute(text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS "{index_name}" '
                f'ON "{table}" ("{column}")'
            ))
