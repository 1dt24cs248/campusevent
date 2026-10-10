"""Serialize operations that read or modify the published timetable state."""
from sqlalchemy import text
from sqlalchemy.orm import Session


_POSTGRES_TIMETABLE_LOCK_ID = 74_428_205_305_171


def acquire_timetable_state_lock(db: Session) -> None:
    """Acquire a transaction-scoped lock shared by timetable readers and writers."""
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": _POSTGRES_TIMETABLE_LOCK_ID},
        )
        return

    if dialect == "sqlite":
        connection = db.connection()
        sqlite_connection = connection.connection.driver_connection
        if sqlite_connection.in_transaction:
            connection.exec_driver_sql(
                "UPDATE timetable_entries SET id = id WHERE 0"
            )
        else:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        return

    raise RuntimeError(
        f"Timetable locking is not configured for database dialect {dialect!r}."
    )
