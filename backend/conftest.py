"""Prevent pytest imports from creating or migrating the default campus database."""
import os
from pathlib import Path
from urllib.parse import unquote

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def _targets_campus_database(database_url: str) -> bool:
    try:
        url = make_url(database_url)
    except ArgumentError as error:
        pytest.exit(f"Invalid DATABASE_URL for tests: {error}", returncode=2)

    if url.get_backend_name() != "sqlite" or not url.database:
        return False

    database = unquote(url.database)
    if database == ":memory:":
        return False
    if database.startswith("file:"):
        database = database[len("file:"):]
    if len(database) > 2 and database[0] == "/" and database[2] == ":":
        database = database[1:]

    backend_dir = Path(__file__).parent
    target = (backend_dir / "campus.db").resolve()
    database_path = Path(database)
    candidates = [database_path.resolve()]
    if not database_path.is_absolute():
        candidates.append((backend_dir / database_path).resolve())
    return target in candidates


def pytest_configure(config: pytest.Config) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if database_url is None:
        database_url = "sqlite://"
        os.environ["DATABASE_URL"] = database_url
    elif not database_url.strip():
        pytest.exit(
            "Unsafe pytest database configuration: DATABASE_URL is empty. "
            "Set it to an isolated database such as sqlite://.",
            returncode=2,
        )

    if _targets_campus_database(database_url):
        pytest.exit(
            "Unsafe pytest database configuration: DATABASE_URL resolves to "
            f"{Path(__file__).parent / 'campus.db'}. "
            "Set it to an isolated database such as sqlite://.",
            returncode=2,
        )
