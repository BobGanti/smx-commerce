from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from smx_commerce.core.ids import generate_public_id


@dataclass(frozen=True)
class ProductPublicIdMigrationResult:
    column_added: bool
    index_created: bool
    products_backfilled: int

@dataclass(frozen=True)
class ProductMediaTableMigrationResult:
    table_created_or_verified: bool

def migrate_product_public_ids(engine: Engine) -> ProductPublicIdMigrationResult:
    """
    Add and backfill smx_products.product_public_id.

    This is intentionally explicit because create_all() does not migrate
    existing production tables.
    """
    column_added = False
    index_created = False
    products_backfilled = 0

    if not _table_exists(engine, "smx_products"):
        raise RuntimeError("smx_products table does not exist. Run schema initialization first.")

    with engine.begin() as connection:
        if not _column_exists(engine, "smx_products", "product_public_id"):
            connection.execute(
                text("ALTER TABLE smx_products ADD COLUMN product_public_id VARCHAR(80)")
            )
            column_added = True

        existing_public_ids = {
            row["product_public_id"]
            for row in connection.execute(
                text(
                    """
                    SELECT product_public_id
                    FROM smx_products
                    WHERE product_public_id IS NOT NULL
                      AND product_public_id != ''
                    """
                )
            ).mappings()
        }

        rows_to_backfill = connection.execute(
            text(
                """
                SELECT id
                FROM smx_products
                WHERE product_public_id IS NULL
                   OR product_public_id = ''
                ORDER BY id ASC
                """
            )
        ).mappings().all()

        for row in rows_to_backfill:
            product_public_id = _generate_unique_product_public_id(existing_public_ids)

            connection.execute(
                text(
                    """
                    UPDATE smx_products
                    SET product_public_id = :product_public_id
                    WHERE id = :id
                    """
                ),
                {
                    "product_public_id": product_public_id,
                    "id": row["id"],
                },
            )

            existing_public_ids.add(product_public_id)
            products_backfilled += 1

        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ix_smx_products_product_public_id
                ON smx_products (product_public_id)
                """
            )
        )
        index_created = True

    return ProductPublicIdMigrationResult(
        column_added=column_added,
        index_created=index_created,
        products_backfilled=products_backfilled,
    )


def migrate_product_media_table(engine: Engine) -> ProductMediaTableMigrationResult:
    """
    Create smx_product_media if missing.

    This is intentionally explicit because product media is a new child table
    required by the ecommerce media feature.
    """
    if not _table_exists(engine, "smx_products"):
        raise RuntimeError("smx_products table does not exist. Run schema initialization first.")

    if not _column_exists(engine, "smx_products", "product_public_id"):
        raise RuntimeError(
            "smx_products.product_public_id is missing. "
            "Run migrate-product-public-ids before migrate-product-media-table."
        )

    from smx_commerce.catalog.models import ProductMediaRow

    ProductMediaRow.__table__.create(engine, checkfirst=True)

    return ProductMediaTableMigrationResult(table_created_or_verified=True)

def _table_exists(engine: Engine, table_name: str) -> bool:
    return inspect(engine).has_table(table_name)


def _column_exists(engine: Engine, table_name: str, column_name: str) -> bool:
    inspector = inspect(engine)

    return any(
        column["name"] == column_name
        for column in inspector.get_columns(table_name)
    )


def _generate_unique_product_public_id(existing_public_ids: set[str]) -> str:
    for _ in range(20):
        value = generate_public_id("prod")

        if value not in existing_public_ids:
            return value

    raise RuntimeError("could not generate unique product_public_id")