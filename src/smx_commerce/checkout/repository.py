from __future__ import annotations

from secrets import token_urlsafe
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from smx_commerce.catalog.models import ProductPriceRow, ProductRow
from smx_commerce.catalog.objects import Money, PriceStatus, ProductStatus, validate_required_text
from smx_commerce.checkout.models import OrderRow, utc_now
from smx_commerce.checkout.objects import BuyerDetails, Order, OrderStatus
from smx_commerce.customers.models import CustomerRow
from smx_commerce.customers.repository import CustomerRepository


class OrderRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_pending(
        self,
        *,
        product_slug: str,
        price_code: str,
        buyer: BuyerDetails,
        payment_provider: str = "stripe",
        payment_reference: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Order:
        product = self._get_active_product_or_raise(product_slug)
        price = self._get_active_price_or_raise(product.slug, price_code)
        customer_id = self._get_or_create_customer_id(buyer)

        row = OrderRow(
            customer_id=customer_id,
            public_id=self._new_public_id(),
            product_slug=product.slug,
            price_code=price.code,
            amount_cents=price.amount_cents,
            currency=price.currency,
            status=OrderStatus.PENDING.value,
            buyer_full_name=buyer.full_name,
            buyer_email=buyer.email,
            buyer_phone=buyer.phone,
            buyer_company=buyer.company,
            buyer_metadata_json=dict(buyer.metadata or {}),
            payment_provider=validate_required_text(payment_provider, "payment_provider"),
            payment_reference=payment_reference,
            metadata_json=dict(metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_domain(row)
    
    
    def create_pending_cart(
        self,
        *,
        amount: Money,
        buyer: BuyerDetails,
        payment_provider: str = "stripe",
        payment_reference: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Order:
        if not isinstance(amount, Money):
            raise TypeError("amount must be a Money instance")

        customer_id = self._get_or_create_customer_id(buyer)

        row = OrderRow(
            customer_id=customer_id,
            public_id=self._new_public_id(),
            product_slug="cart",
            price_code="cart",
            amount_cents=amount.amount_cents,
            currency=amount.currency,
            status=OrderStatus.PENDING.value,
            buyer_full_name=buyer.full_name,
            buyer_email=buyer.email,
            buyer_phone=buyer.phone,
            buyer_company=buyer.company,
            buyer_metadata_json=dict(buyer.metadata or {}),
            payment_provider=validate_required_text(payment_provider, "payment_provider"),
            payment_reference=payment_reference,
            metadata_json=dict(metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_domain(row)
    

    def _get_or_create_customer_id(self, buyer: BuyerDetails) -> int:
        customer = CustomerRepository(self.session).get_or_create_from_buyer(buyer)

        return self.session.execute(
            select(CustomerRow.id).where(CustomerRow.public_id == customer.public_id)
        ).scalar_one()

    def backfill_customer_links(self, *, limit: int | None = None) -> dict[str, int]:
        query = select(OrderRow).where(OrderRow.customer_id.is_(None)).order_by(OrderRow.id.asc())

        if limit is not None:
            query = query.limit(limit)

        rows = self.session.execute(query).scalars().all()

        checked = 0
        linked = 0
        skipped = 0

        for row in rows:
            checked += 1

            try:
                buyer = BuyerDetails(
                    full_name=row.buyer_full_name,
                    email=row.buyer_email,
                    phone=row.buyer_phone,
                    company=row.buyer_company,
                    metadata=dict(row.buyer_metadata_json or {}),
                )
            except ValueError:
                skipped += 1
                continue

            row.customer_id = self._get_or_create_customer_id(buyer)
            linked += 1

        self.session.flush()

        return {
            "checked": checked,
            "linked": linked,
            "skipped": skipped,
        }

    def get_by_public_id(self, public_id: str) -> Order | None:
        normalized_public_id = validate_required_text(public_id, "public_id")

        row = self.session.execute(
            select(OrderRow).where(OrderRow.public_id == normalized_public_id)
        ).scalar_one_or_none()

        return self._to_domain(row) if row is not None else None

    def get_by_payment_reference(self, payment_reference: str) -> Order | None:
        normalized_reference = validate_required_text(payment_reference, "payment_reference")

        row = self.session.execute(
            select(OrderRow).where(OrderRow.payment_reference == normalized_reference)
        ).scalar_one_or_none()

        return self._to_domain(row) if row is not None else None

    def list(
        self,
        *,
        status: OrderStatus | str | None = None,
        product_slug: str | None = None,
    ) -> list[Order]:
        statement = select(OrderRow)

        if status is not None:
            order_status = status if isinstance(status, OrderStatus) else OrderStatus(status)
            statement = statement.where(OrderRow.status == order_status.value)

        if product_slug is not None:
            statement = statement.where(OrderRow.product_slug == product_slug)

        statement = statement.order_by(OrderRow.id.desc())

        rows = self.session.execute(statement).scalars().all()

        return [self._to_domain(row) for row in rows]

    def update(self, public_id: str, **changes: Any) -> Order:
        row = self._get_row_or_raise(public_id)

        allowed_fields = {
            "status",
            "payment_reference",
            "metadata",
            "notes",
        }

        unknown_fields = set(changes) - allowed_fields

        if unknown_fields:
            raise ValueError(f"unsupported order update field(s): {sorted(unknown_fields)}")

        if "status" in changes:
            status = changes["status"]
            row.status = status.value if isinstance(status, OrderStatus) else OrderStatus(status).value

            if row.status == OrderStatus.PAID.value and row.paid_at is None:
                row.paid_at = utc_now()

        if "payment_reference" in changes:
            row.payment_reference = changes["payment_reference"]

        if "metadata" in changes:
            row.metadata_json = dict(changes["metadata"] or {})

        if "notes" in changes:
            row.notes = changes["notes"] or ""

        self.session.flush()

        return self._to_domain(row)

    def mark_paid(self, public_id: str, *, payment_reference: str | None = None) -> Order:
        changes: dict[str, Any] = {"status": OrderStatus.PAID}

        if payment_reference:
            changes["payment_reference"] = payment_reference

        return self.update(public_id, **changes)

    def cancel(self, public_id: str) -> Order:
        return self.update(public_id, status=OrderStatus.CANCELLED)

    def fail(self, public_id: str) -> Order:
        return self.update(public_id, status=OrderStatus.FAILED)

    def _get_active_product_or_raise(self, product_slug: str) -> ProductRow:
        row = self.session.execute(
            select(ProductRow).where(ProductRow.slug == product_slug)
        ).scalar_one_or_none()

        if row is None:
            raise ValueError(f"product not found: {product_slug}")

        if row.status != ProductStatus.ACTIVE.value:
            raise ValueError(f"product is not active: {product_slug}")

        return row

    def _get_active_price_or_raise(self, product_slug: str, price_code: str) -> ProductPriceRow:
        row = self.session.execute(
            select(ProductPriceRow).where(
                ProductPriceRow.product_slug == product_slug,
                ProductPriceRow.code == price_code,
            )
        ).scalar_one_or_none()

        if row is None:
            raise ValueError(f"price not found for product {product_slug}: {price_code}")

        if row.status != PriceStatus.ACTIVE.value:
            raise ValueError(f"price is not active for product {product_slug}: {price_code}")

        return row

    def _get_row_or_raise(self, public_id: str) -> OrderRow:
        normalized_public_id = validate_required_text(public_id, "public_id")

        row = self.session.execute(
            select(OrderRow).where(OrderRow.public_id == normalized_public_id)
        ).scalar_one_or_none()

        if row is None:
            raise ValueError(f"order not found: {normalized_public_id}")

        return row

    def _new_public_id(self) -> str:
        while True:
            public_id = f"ord_{token_urlsafe(16)}"
            exists = self.session.execute(
                select(OrderRow.public_id).where(OrderRow.public_id == public_id)
            ).scalar_one_or_none()

            if exists is None:
                return public_id

    @staticmethod
    def _to_domain(row: OrderRow) -> Order:
        return Order(
            public_id=row.public_id,
            product_slug=row.product_slug,
            price_code=row.price_code,
            buyer=BuyerDetails(
                full_name=row.buyer_full_name,
                email=row.buyer_email,
                phone=row.buyer_phone,
                company=row.buyer_company,
                metadata=dict(row.buyer_metadata_json or {}),
            ),
            amount=Money(amount_cents=row.amount_cents, currency=row.currency),
            status=OrderStatus(row.status),
            payment_provider=row.payment_provider,
            payment_reference=row.payment_reference,
            metadata=dict(row.metadata_json or {}),
            notes=row.notes or "",
        )
