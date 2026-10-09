"""Additive, idempotent migrations for the campus food workflow."""
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


FOOD_COLUMNS = {
    "food_locations": {
        "location_text": "VARCHAR",
        "description": "VARCHAR",
        "updated_at": "DATETIME",
    },
    "food_menu_items": {
        "menu_id": "VARCHAR",
        "category": "VARCHAR",
        "description": "VARCHAR",
        "dietary_note": "VARCHAR",
    },
}


def migrate_food_schema(engine: Engine) -> None:
    """Add food metadata and retain legacy visible items as published menus."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    table_columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in FOOD_COLUMNS
        if table in tables
    }
    with engine.begin() as connection:
        for table, columns in FOOD_COLUMNS.items():
            if table not in tables:
                continue
            for name, sql_type in columns.items():
                if name not in table_columns[table]:
                    connection.execute(
                        text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}')
                    )

        if not {"food_menu_items", "food_menus"} <= tables:
            return
        legacy_rows = connection.execute(text(
            """
            SELECT id, location_id, menu_date, created_by, created_at
            FROM food_menu_items
            WHERE menu_id IS NULL
            """
        )).mappings().all()
        groups = {}
        for row in legacy_rows:
            groups.setdefault((row["location_id"], row["menu_date"]), []).append(row)
        for (location_id, menu_date), items in groups.items():
            menu_id = f"legacy_{uuid4().hex}"
            created_at = min(item["created_at"] for item in items)
            connection.execute(text(
                """
                INSERT INTO food_menus
                    (id, location_id, menu_date, title, status, published_at,
                     created_by, created_at, updated_at)
                VALUES
                    (:id, :location_id, :menu_date, :title, 'PUBLISHED', :published_at,
                     :created_by, :created_at, :updated_at)
                """
            ), {
                "id": menu_id,
                "location_id": location_id,
                "menu_date": str(menu_date),
                "title": "Previously published menu",
                "published_at": created_at,
                "created_by": items[0]["created_by"],
                "created_at": created_at,
                "updated_at": created_at,
            })
            for item in items:
                connection.execute(text(
                    """
                    UPDATE food_menu_items
                    SET menu_id = :menu_id,
                        category = COALESCE(category, 'OTHER')
                    WHERE id = :item_id AND menu_id IS NULL
                    """
                ), {"menu_id": menu_id, "item_id": item["id"]})

        if "food_locations" in tables:
            connection.execute(text(
                "UPDATE food_locations SET updated_at = created_at WHERE updated_at IS NULL"
            ))
