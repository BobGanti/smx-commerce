from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from smx_commerce.catalog.models import (
    CategoryRow,
    ProductCategoryRow,
    ProductMediaRow,
    ProductPriceRow,
    ProductRow,
)
from smx_commerce.core.ids import generate_public_id
from smx_commerce.catalog.objects import (
    BillingMode,
    Category,
    CategoryStatus,
    Money,
    PriceStatus,
    Product,
    ProductKind,
    ProductMedia,
    ProductMediaRole,
    ProductPrice,
    ProductStatus,
    validate_required_text,
    validate_slug,
)


class CategoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, category: Category) -> Category:
        if self.get_by_slug(category.slug) is not None:
            raise ValueError(f"category already exists: {category.slug}")

        row = CategoryRow(
            slug=category.slug,
            name=category.name,
            description=category.description or "",
            status=category.status.value,
            parent_slug=category.parent_slug,
            sort_order=category.sort_order,
            metadata_json=dict(category.metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_domain(row)

    def get_by_slug(self, slug: str) -> Category | None:
        normalized_slug = validate_slug(slug)

        row = self.session.execute(
            select(CategoryRow).where(CategoryRow.slug == normalized_slug)
        ).scalar_one_or_none()

        return self._to_domain(row) if row is not None else None

    def list(
        self,
        *,
        status: CategoryStatus | str | None = None,
        include_archived: bool = False,
    ) -> list[Category]:
        statement = select(CategoryRow)

        if status is not None:
            category_status = status if isinstance(status, CategoryStatus) else CategoryStatus(status)
            statement = statement.where(CategoryRow.status == category_status.value)
        elif not include_archived:
            statement = statement.where(CategoryRow.status != CategoryStatus.ARCHIVED.value)

        statement = statement.order_by(CategoryRow.sort_order.asc(), CategoryRow.name.asc())

        rows = self.session.execute(statement).scalars().all()

        return [self._to_domain(row) for row in rows]

    def update(self, slug: str, **changes: Any) -> Category:
        row = self._get_row_or_raise(slug)

        allowed_fields = {
            "name",
            "description",
            "status",
            "parent_slug",
            "sort_order",
            "metadata",
        }

        unknown_fields = set(changes) - allowed_fields

        if unknown_fields:
            raise ValueError(f"unsupported category update field(s): {sorted(unknown_fields)}")

        if "name" in changes:
            row.name = validate_required_text(changes["name"], "name")

        if "description" in changes:
            row.description = changes["description"] or ""

        if "status" in changes:
            status = changes["status"]
            row.status = status.value if isinstance(status, CategoryStatus) else CategoryStatus(status).value

        if "parent_slug" in changes:
            parent_slug = changes["parent_slug"]
            row.parent_slug = validate_slug(parent_slug, "parent_slug") if parent_slug else None

        if "sort_order" in changes:
            row.sort_order = int(changes["sort_order"])

        if "metadata" in changes:
            row.metadata_json = dict(changes["metadata"] or {})

        self.session.flush()

        return self._to_domain(row)

    def archive(self, slug: str) -> Category:
        return self.update(slug, status=CategoryStatus.ARCHIVED)

    def _get_row_or_raise(self, slug: str) -> CategoryRow:
        normalized_slug = validate_slug(slug)

        row = self.session.execute(
            select(CategoryRow).where(CategoryRow.slug == normalized_slug)
        ).scalar_one_or_none()

        if row is None:
            raise ValueError(f"category not found: {normalized_slug}")

        return row

    @staticmethod
    def _to_domain(row: CategoryRow) -> Category:
        return Category(
            slug=row.slug,
            name=row.name,
            description=row.description or "",
            status=CategoryStatus(row.status),
            parent_slug=row.parent_slug,
            sort_order=row.sort_order,
            metadata=dict(row.metadata_json or {}),
        )


class ProductRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, product: Product) -> Product:
        if self.get_by_slug(product.slug) is not None:
            raise ValueError(f"product already exists: {product.slug}")

        self._validate_category_slugs(product.category_slugs)

        row = ProductRow(
            product_public_id=product.product_public_id or self._generate_unique_product_public_id(),
            slug=product.slug,
            name=product.name,
            kind=product.kind.value,
            summary=product.summary or "",
            description=product.description or "",
            status=product.status.value,
            sort_order=product.sort_order,
            metadata_json=dict(product.metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        self._replace_category_links(product.slug, product.category_slugs)

        price_repo = ProductPriceRepository(self.session)
        for price in product.prices:
            price_repo.create(product.slug, price)

        self.session.flush()

        created = self.get_by_slug(product.slug)
        assert created is not None
        return created

    def get_by_slug(self, slug: str) -> Product | None:
        normalized_slug = validate_slug(slug)

        row = self.session.execute(
            select(ProductRow).where(ProductRow.slug == normalized_slug)
        ).scalar_one_or_none()

        return self._to_domain(row) if row is not None else None


    def get_by_public_id(self, product_public_id: str) -> Product | None:
        value = validate_required_text(product_public_id, "product_public_id")

        row = self.session.execute(
            select(ProductRow).where(ProductRow.product_public_id == value)
        ).scalar_one_or_none()

        return self._to_domain(row) if row is not None else None


    def list(
        self,
        *,
        status: ProductStatus | str | None = None,
        category_slug: str | None = None,
        include_archived: bool = False,
    ) -> list[Product]:
        statement = select(ProductRow)

        if category_slug is not None:
            normalized_category_slug = validate_slug(category_slug, "category_slug")
            statement = statement.join(
                ProductCategoryRow,
                ProductCategoryRow.product_slug == ProductRow.slug,
            ).where(ProductCategoryRow.category_slug == normalized_category_slug)

        if status is not None:
            product_status = status if isinstance(status, ProductStatus) else ProductStatus(status)
            statement = statement.where(ProductRow.status == product_status.value)
        elif not include_archived:
            statement = statement.where(ProductRow.status != ProductStatus.ARCHIVED.value)

        statement = statement.order_by(ProductRow.sort_order.asc(), ProductRow.name.asc())

        rows = self.session.execute(statement).scalars().all()

        return [self._to_domain(row) for row in rows]

    def update(self, slug: str, **changes: Any) -> Product:
        row = self._get_row_or_raise(slug)

        allowed_fields = {
            "name",
            "kind",
            "summary",
            "description",
            "status",
            "category_slugs",
            "sort_order",
            "metadata",
        }

        unknown_fields = set(changes) - allowed_fields

        if unknown_fields:
            raise ValueError(f"unsupported product update field(s): {sorted(unknown_fields)}")

        if "name" in changes:
            row.name = validate_required_text(changes["name"], "name")

        if "kind" in changes:
            kind = changes["kind"]
            row.kind = kind.value if isinstance(kind, ProductKind) else ProductKind(kind).value

        if "summary" in changes:
            row.summary = changes["summary"] or ""

        if "description" in changes:
            row.description = changes["description"] or ""

        if "status" in changes:
            status = changes["status"]
            row.status = status.value if isinstance(status, ProductStatus) else ProductStatus(status).value

        if "sort_order" in changes:
            row.sort_order = int(changes["sort_order"])

        if "metadata" in changes:
            row.metadata_json = dict(changes["metadata"] or {})

        if "category_slugs" in changes:
            category_slugs = [
                validate_slug(value, "category_slug")
                for value in (changes["category_slugs"] or [])
            ]
            self._validate_category_slugs(category_slugs)
            self._replace_category_links(row.slug, category_slugs)

        self.session.flush()

        return self._to_domain(row)

    def archive(self, slug: str) -> Product:
        return self.update(slug, status=ProductStatus.ARCHIVED)


    def _generate_unique_product_public_id(self) -> str:
        for _ in range(10):
            value = generate_public_id("prod")

            exists = self.session.execute(
                select(ProductRow.id).where(ProductRow.product_public_id == value)
            ).scalar_one_or_none()

            if exists is None:
                return value

        raise RuntimeError("could not generate unique product_public_id")


    def _get_row_or_raise(self, slug: str) -> ProductRow:
        normalized_slug = validate_slug(slug)

        row = self.session.execute(
            select(ProductRow).where(ProductRow.slug == normalized_slug)
        ).scalar_one_or_none()

        if row is None:
            raise ValueError(f"product not found: {normalized_slug}")

        return row

    def _category_slugs_for_product(self, product_slug: str) -> list[str]:
        rows = self.session.execute(
            select(ProductCategoryRow.category_slug)
            .where(ProductCategoryRow.product_slug == product_slug)
            .order_by(ProductCategoryRow.category_slug.asc())
        ).scalars().all()

        return list(rows)

    def _replace_category_links(self, product_slug: str, category_slugs: list[str]) -> None:
        self.session.execute(
            delete(ProductCategoryRow).where(ProductCategoryRow.product_slug == product_slug)
        )

        for category_slug in dict.fromkeys(category_slugs):
            self.session.add(
                ProductCategoryRow(
                    product_slug=product_slug,
                    category_slug=category_slug,
                )
            )

    def _validate_category_slugs(self, category_slugs: list[str]) -> None:
        for category_slug in dict.fromkeys(category_slugs):
            exists = self.session.execute(
                select(CategoryRow.slug).where(CategoryRow.slug == category_slug)
            ).scalar_one_or_none()

            if exists is None:
                raise ValueError(f"category does not exist: {category_slug}")

    def _prices_for_product(self, product_slug: str) -> list[ProductPrice]:
        return ProductPriceRepository(self.session).list(product_slug, include_archived=True)
    
    def _media_for_product(self, product_public_id: str | None) -> list[ProductMedia]:
        if not product_public_id:
            return []

        rows = self.session.execute(
            select(ProductMediaRow)
            .where(ProductMediaRow.product_public_id == product_public_id)
            .order_by(ProductMediaRow.media_role.asc(), ProductMediaRow.sort_order.asc(), ProductMediaRow.id.asc())
        ).scalars().all()

        return [
            ProductMedia(
                url=row.url,
                media_role=ProductMediaRole(row.media_role),
                storage_path=row.storage_path or "",
                filename=row.filename or "",
                content_type=row.content_type or "",
                alt_text=row.alt_text or "",
                sort_order=row.sort_order,
                metadata=dict(row.metadata_json or {}),
            )
            for row in rows
        ]

    def _to_domain(self, row: ProductRow) -> Product:
        return Product(
            slug=row.slug,
            name=row.name,
            product_public_id=row.product_public_id,
            kind=ProductKind(row.kind),
            summary=row.summary or "",
            description=row.description or "",
            status=ProductStatus(row.status),
            category_slugs=self._category_slugs_for_product(row.slug),
            sort_order=row.sort_order,
            prices=self._prices_for_product(row.slug),
            media=self._media_for_product(row.product_public_id),
            metadata=dict(row.metadata_json or {}),
        )


class ProductMediaRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, product_public_id: str, media: ProductMedia) -> ProductMedia:
        normalized_product_public_id = validate_required_text(
            product_public_id,
            "product_public_id",
        )

        self._ensure_product_exists(normalized_product_public_id)

        if media.is_main:
            self.delete_main(normalized_product_public_id)

        row = ProductMediaRow(
            product_public_id=normalized_product_public_id,
            media_role=media.media_role.value,
            url=media.url,
            storage_path=media.storage_path or "",
            filename=media.filename or "",
            content_type=media.content_type or "",
            alt_text=media.alt_text or "",
            sort_order=media.sort_order,
            metadata_json=dict(media.metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_domain(row)

    def list(self, product_public_id: str) -> list[ProductMedia]:
        normalized_product_public_id = validate_required_text(
            product_public_id,
            "product_public_id",
        )

        rows = self.session.execute(
            select(ProductMediaRow)
            .where(ProductMediaRow.product_public_id == normalized_product_public_id)
            .order_by(
                ProductMediaRow.media_role.asc(),
                ProductMediaRow.sort_order.asc(),
                ProductMediaRow.id.asc(),
            )
        ).scalars().all()

        return [self._to_domain(row) for row in rows]

    def delete_main(self, product_public_id: str) -> None:
        normalized_product_public_id = validate_required_text(
            product_public_id,
            "product_public_id",
        )

        self.session.execute(
            delete(ProductMediaRow).where(
                ProductMediaRow.product_public_id == normalized_product_public_id,
                ProductMediaRow.media_role == ProductMediaRole.MAIN.value,
            )
        )

    def delete_by_url(self, product_public_id: str, url: str) -> None:
        normalized_product_public_id = validate_required_text(
            product_public_id,
            "product_public_id",
        )
        normalized_url = validate_required_text(url, "url")

        self.session.execute(
            delete(ProductMediaRow).where(
                ProductMediaRow.product_public_id == normalized_product_public_id,
                ProductMediaRow.url == normalized_url,
            )
        )

    def _ensure_product_exists(self, product_public_id: str) -> None:
        exists = self.session.execute(
            select(ProductRow.id).where(ProductRow.product_public_id == product_public_id)
        ).scalar_one_or_none()

        if exists is None:
            raise ValueError(f"product does not exist: {product_public_id}")

    @staticmethod
    def _to_domain(row: ProductMediaRow) -> ProductMedia:
        return ProductMedia(
            url=row.url,
            media_role=ProductMediaRole(row.media_role),
            storage_path=row.storage_path or "",
            filename=row.filename or "",
            content_type=row.content_type or "",
            alt_text=row.alt_text or "",
            sort_order=row.sort_order,
            metadata=dict(row.metadata_json or {}),
        )
    

class ProductPriceRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, product_slug: str, price: ProductPrice) -> ProductPrice:
        normalized_product_slug = validate_slug(product_slug, "product_slug")
        self._ensure_product_exists(normalized_product_slug)

        if self.get_by_code(normalized_product_slug, price.code) is not None:
            raise ValueError(f"price already exists for product {normalized_product_slug}: {price.code}")

        row = ProductPriceRow(
            product_slug=normalized_product_slug,
            code=price.code,
            label=price.label,
            amount_cents=price.amount.amount_cents,
            currency=price.amount.currency,
            status=price.status.value,
            billing_mode=price.billing_mode.value,
            billing_interval=price.billing_interval,
            sort_order=price.sort_order,
            metadata_json=dict(price.metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_domain(row)

    def get_by_code(self, product_slug: str, code: str) -> ProductPrice | None:
        row = self._get_row(product_slug, code)
        return self._to_domain(row) if row is not None else None

    def list(
        self,
        product_slug: str,
        *,
        status: PriceStatus | str | None = None,
        include_archived: bool = False,
    ) -> list[ProductPrice]:
        normalized_product_slug = validate_slug(product_slug, "product_slug")

        statement = select(ProductPriceRow).where(ProductPriceRow.product_slug == normalized_product_slug)

        if status is not None:
            price_status = status if isinstance(status, PriceStatus) else PriceStatus(status)
            statement = statement.where(ProductPriceRow.status == price_status.value)
        elif not include_archived:
            statement = statement.where(ProductPriceRow.status != PriceStatus.ARCHIVED.value)

        statement = statement.order_by(ProductPriceRow.sort_order.asc(), ProductPriceRow.label.asc())

        rows = self.session.execute(statement).scalars().all()

        return [self._to_domain(row) for row in rows]

    def update(self, product_slug: str, code: str, **changes: Any) -> ProductPrice:
        row = self._get_row_or_raise(product_slug, code)

        allowed_fields = {
            "label",
            "amount",
            "status",
            "billing_mode",
            "billing_interval",
            "sort_order",
            "metadata",
        }

        unknown_fields = set(changes) - allowed_fields

        if unknown_fields:
            raise ValueError(f"unsupported price update field(s): {sorted(unknown_fields)}")

        next_billing_mode = row.billing_mode
        next_billing_interval = row.billing_interval

        if "billing_mode" in changes:
            billing_mode = changes["billing_mode"]
            next_billing_mode = billing_mode.value if isinstance(billing_mode, BillingMode) else BillingMode(billing_mode).value

        if "billing_interval" in changes:
            next_billing_interval = changes["billing_interval"]

        self._validate_billing_fields(next_billing_mode, next_billing_interval)

        if "label" in changes:
            row.label = validate_required_text(changes["label"], "label")

        if "amount" in changes:
            amount = changes["amount"]
            if not isinstance(amount, Money):
                raise TypeError("amount must be a Money instance")
            row.amount_cents = amount.amount_cents
            row.currency = amount.currency

        if "status" in changes:
            status = changes["status"]
            row.status = status.value if isinstance(status, PriceStatus) else PriceStatus(status).value

        if "billing_mode" in changes:
            row.billing_mode = next_billing_mode

        if "billing_interval" in changes:
            row.billing_interval = next_billing_interval

        if "sort_order" in changes:
            row.sort_order = int(changes["sort_order"])

        if "metadata" in changes:
            row.metadata_json = dict(changes["metadata"] or {})

        self.session.flush()

        return self._to_domain(row)

    def deactivate(self, product_slug: str, code: str) -> ProductPrice:
        return self.update(product_slug, code, status=PriceStatus.INACTIVE)

    def archive(self, product_slug: str, code: str) -> ProductPrice:
        return self.update(product_slug, code, status=PriceStatus.ARCHIVED)

    def _ensure_product_exists(self, product_slug: str) -> None:
        exists = self.session.execute(
            select(ProductRow.slug).where(ProductRow.slug == product_slug)
        ).scalar_one_or_none()

        if exists is None:
            raise ValueError(f"product does not exist: {product_slug}")

    def _get_row(self, product_slug: str, code: str) -> ProductPriceRow | None:
        normalized_product_slug = validate_slug(product_slug, "product_slug")
        normalized_code = validate_slug(code, "code")

        return self.session.execute(
            select(ProductPriceRow).where(
                ProductPriceRow.product_slug == normalized_product_slug,
                ProductPriceRow.code == normalized_code,
            )
        ).scalar_one_or_none()

    def _get_row_or_raise(self, product_slug: str, code: str) -> ProductPriceRow:
        row = self._get_row(product_slug, code)

        if row is None:
            raise ValueError(
                f"price not found for product {validate_slug(product_slug, 'product_slug')}: {validate_slug(code, 'code')}"
            )

        return row

    @staticmethod
    def _validate_billing_fields(billing_mode: str, billing_interval: str | None) -> None:
        if billing_mode == BillingMode.RECURRING.value and not billing_interval:
            raise ValueError("billing_interval is required for recurring prices")

        if billing_mode == BillingMode.ONE_TIME.value and billing_interval:
            raise ValueError("billing_interval is only valid for recurring prices")

    @staticmethod
    def _to_domain(row: ProductPriceRow) -> ProductPrice:
        return ProductPrice(
            code=row.code,
            label=row.label,
            amount=Money(amount_cents=row.amount_cents, currency=row.currency),
            status=PriceStatus(row.status),
            billing_mode=BillingMode(row.billing_mode),
            billing_interval=row.billing_interval,
            sort_order=row.sort_order,
            metadata=dict(row.metadata_json or {}),
        )
