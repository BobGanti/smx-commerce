from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


REQUIRED_TABLES = [
    "smx_categories",
    "smx_products",
    "smx_product_categories",
    "smx_product_media",
    "smx_product_prices",
    "smx_orders",
    "smx_customer_entitlements",
    "smx_customer_sessions",
    "smx_customer_auth_tokens",
    "smx_customers",
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



def ensure_schema_upgrades(engine: Engine) -> list[str]:
    """Apply safe, idempotent schema upgrades for existing client databases.

    SQLAlchemy create_all() creates missing tables but does not add columns to
    tables that already exist. This helper handles additive upgrades that are
    safe for existing deployments.
    """

    applied: list[str] = []
    inspector = inspect(engine)

    if inspector.has_table("smx_orders"):
        existing_columns = {
            column["name"]
            for column in inspector.get_columns("smx_orders")
        }

        if "customer_id" not in existing_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE smx_orders ADD COLUMN customer_id INTEGER")
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS "
                        "ix_smx_orders_customer_id "
                        "ON smx_orders (customer_id)"
                    )
                )

            applied.append("smx_orders.customer_id")

    return applied


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