from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


REQUIRED_TABLES = [
    "smx_categories",
    "smx_products",
    "smx_product_categories",
    "smx_product_prices",
    "smx_orders",
    "smx_payment_events",
    "smx_commerce_settings",
]


class SchemaNotReadyError(RuntimeError):
    pass


def get_missing_tables(engine: Engine) -> list[str]:
    inspector = inspect(engine)

    return [
        table_name
        for table_name in REQUIRED_TABLES
        if not inspector.has_table(table_name)
    ]


def assert_schema_ready(engine: Engine) -> None:
    missing_tables = get_missing_tables(engine)

    if missing_tables:
        joined = ", ".join(missing_tables)
        raise SchemaNotReadyError(
            f"smx-commerce database schema is not ready. Missing table(s): {joined}"
        )
