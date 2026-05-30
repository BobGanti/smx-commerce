from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


REQUIRED_TABLES = [
    "smx_categories",
    "smx_products",
    "smx_product_categories",
    "smx_product_media",
    "smx_product_prices",
    "smx_orders",
    "smx_payment_events",
    "smx_commerce_settings",
]


REQUIRED_COLUMNS = {
    "smx_products": [
        "product_public_id",
    ],
}


class SchemaNotReadyError(RuntimeError):
    pass


def get_missing_tables(engine: Engine) -> list[str]:
    inspector = inspect(engine)

    return [
        table_name
        for table_name in REQUIRED_TABLES
        if not inspector.has_table(table_name)
    ]


def get_missing_columns(engine: Engine) -> list[str]:
    inspector = inspect(engine)
    missing: list[str] = []

    for table_name, required_columns in REQUIRED_COLUMNS.items():
        if not inspector.has_table(table_name):
            continue

        existing_columns = {
            column["name"]
            for column in inspector.get_columns(table_name)
        }

        for column_name in required_columns:
            if column_name not in existing_columns:
                missing.append(f"{table_name}.{column_name}")

    return missing


def assert_schema_ready(engine: Engine) -> None:
    missing_tables = get_missing_tables(engine)
    missing_columns = get_missing_columns(engine)

    problems = []

    if missing_tables:
        problems.append("Missing table(s): " + ", ".join(missing_tables))

    if missing_columns:
        problems.append("Missing column(s): " + ", ".join(missing_columns))

    if problems:
        raise SchemaNotReadyError(
            "smx-commerce database schema is not ready. " + " ".join(problems)
        )