from __future__ import annotations

import hashlib
from datetime import timezone, datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from smx_commerce.catalog.objects import validate_required_text
from smx_commerce.checkout.objects import BuyerDetails, validate_email
from smx_commerce.core.ids import generate_public_id
from smx_commerce.customers.models import (
    CustomerAuthTokenRow,
    CustomerEntitlementRow,
    CustomerRow,
    CustomerSessionRow,
    utc_now,
)
from smx_commerce.customers.objects import (
    Customer,
    CustomerAuthToken,
    CustomerAuthTokenPurpose,
    CustomerEntitlement,
    CustomerEntitlementStatus,
    CustomerEntitlementType,
    CustomerSession,
    CustomerStatus,
    IssuedCustomerAuthToken,
    IssuedCustomerSession,
)


class CustomerRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_public_id(self, public_id: str) -> Customer | None:
        row = self.session.execute(
            select(CustomerRow).where(CustomerRow.public_id == public_id)
        ).scalar_one_or_none()

        return self._to_customer(row) if row is not None else None

    def get_by_email(self, email: str) -> Customer | None:
        normalized_email = validate_email(email)

        row = self.session.execute(
            select(CustomerRow).where(CustomerRow.email == normalized_email)
        ).scalar_one_or_none()

        return self._to_customer(row) if row is not None else None

    def list(
        self,
        *,
        status: CustomerStatus | str | None = None,
        limit: int | None = 100,
    ) -> list[Customer]:
        statement = select(CustomerRow).order_by(CustomerRow.id.desc())

        if status is not None:
            status_value = status.value if isinstance(status, CustomerStatus) else CustomerStatus(status).value
            statement = statement.where(CustomerRow.status == status_value)

        if limit is not None:
            statement = statement.limit(limit)

        rows = self.session.execute(statement).scalars().all()

        return [self._to_customer(row) for row in rows]

    def list_sessions(
        self,
        customer_public_id: str,
        *,
        limit: int | None = 20,
    ) -> list[CustomerSession]:
        customer_row = self._get_customer_row_or_raise(customer_public_id)

        statement = (
            select(CustomerSessionRow)
            .where(CustomerSessionRow.customer_id == customer_row.id)
            .order_by(CustomerSessionRow.id.desc())
        )

        if limit is not None:
            statement = statement.limit(limit)

        rows = self.session.execute(statement).scalars().all()

        return [self._to_session(row, customer_row.public_id) for row in rows]

    def get_or_create_from_identity(
        self,
        *,
        email: str,
        full_name: str = "",
        phone: str = "",
        company: str = "",
        metadata: dict | None = None,
    ) -> Customer:
        normalized_email = validate_email(email)
        normalized_full_name = (full_name or "").strip()
        normalized_phone = (phone or "").strip()
        normalized_company = (company or "").strip()

        existing = self.session.execute(
            select(CustomerRow).where(CustomerRow.email == normalized_email)
        ).scalar_one_or_none()

        if existing is not None:
            changed = False

            if normalized_full_name and not existing.full_name:
                existing.full_name = normalized_full_name
                changed = True

            if normalized_phone and not existing.phone:
                existing.phone = normalized_phone
                changed = True

            if normalized_company and not existing.company:
                existing.company = normalized_company
                changed = True

            if metadata:
                existing.metadata_json = {
                    **dict(existing.metadata_json or {}),
                    **dict(metadata or {}),
                }
                changed = True

            if changed:
                self.session.flush()

            return self._to_customer(existing)

        row = CustomerRow(
            public_id=self._new_public_id("cus", CustomerRow),
            email=normalized_email,
            full_name=normalized_full_name,
            phone=normalized_phone,
            company=normalized_company,
            metadata_json=dict(metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_customer(row)

    def get_or_create_from_buyer(self, buyer: BuyerDetails) -> Customer:
        existing = self.session.execute(
            select(CustomerRow).where(CustomerRow.email == buyer.email)
        ).scalar_one_or_none()

        if existing is not None:
            changed = False

            if buyer.full_name and not existing.full_name:
                existing.full_name = buyer.full_name
                changed = True

            if buyer.phone and not existing.phone:
                existing.phone = buyer.phone
                changed = True

            if buyer.company and not existing.company:
                existing.company = buyer.company
                changed = True

            if changed:
                self.session.flush()

            return self._to_customer(existing)

        row = CustomerRow(
            public_id=self._new_public_id("cus", CustomerRow),
            email=buyer.email,
            full_name=buyer.full_name,
            phone=buyer.phone,
            company=buyer.company,
            status=CustomerStatus.ACTIVE.value,
            metadata_json=dict(buyer.metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_customer(row)

    def get_by_internal_id(self, internal_id: int) -> Customer | None:
        row = self.session.execute(
            select(CustomerRow).where(CustomerRow.id == int(internal_id))
        ).scalar_one_or_none()

        return self._to_customer(row) if row is not None else None

    def list_entitlements_for_order(self, order_public_id: str) -> list[CustomerEntitlement]:
        normalized_order_public_id = validate_required_text(order_public_id, "order_public_id")

        rows = self.session.execute(
            select(CustomerEntitlementRow)
            .where(CustomerEntitlementRow.order_public_id == normalized_order_public_id)
            .order_by(CustomerEntitlementRow.id.desc())
        ).scalars().all()

        entitlements: list[CustomerEntitlement] = []

        for row in rows:
            customer_public_id = self.session.execute(
                select(CustomerRow.public_id).where(CustomerRow.id == row.customer_id)
            ).scalar_one_or_none()

            if customer_public_id:
                entitlements.append(self._to_entitlement(row, customer_public_id))

        return entitlements

    def create_auth_token(
        self,
        *,
        customer_public_id: str,
        purpose: CustomerAuthTokenPurpose | str = CustomerAuthTokenPurpose.LOGIN,
        expires_in_minutes: int = 15,
    ) -> IssuedCustomerAuthToken:
        customer_row = self._get_customer_row_or_raise(customer_public_id)
        token = token_urlsafe(32)
        purpose_value = purpose.value if isinstance(purpose, CustomerAuthTokenPurpose) else CustomerAuthTokenPurpose(purpose).value

        row = CustomerAuthTokenRow(
            public_id=self._new_public_id("cat", CustomerAuthTokenRow),
            customer_id=customer_row.id,
            token_hash=_hash_token(token),
            purpose=purpose_value,
            expires_at=utc_now() + timedelta(minutes=expires_in_minutes),
        )

        self.session.add(row)
        self.session.flush()

        return IssuedCustomerAuthToken(
            token=token,
            record=self._to_auth_token(row, customer_row.public_id),
        )

    def verify_auth_token(
        self,
        *,
        token: str,
        purpose: CustomerAuthTokenPurpose | str = CustomerAuthTokenPurpose.LOGIN,
    ) -> Customer | None:
        purpose_value = purpose.value if isinstance(purpose, CustomerAuthTokenPurpose) else CustomerAuthTokenPurpose(purpose).value

        row = self.session.execute(
            select(CustomerAuthTokenRow).where(
                CustomerAuthTokenRow.token_hash == _hash_token(token),
                CustomerAuthTokenRow.purpose == purpose_value,
            )
        ).scalar_one_or_none()

        if row is None:
            return None

        now = _normalize_now_for_datetime(row.expires_at)

        if row.used_at is not None or row.expires_at <= now:
            return None

        customer_row = self.session.execute(
            select(CustomerRow).where(CustomerRow.id == row.customer_id)
        ).scalar_one()

        if customer_row.status != CustomerStatus.ACTIVE.value:
            row.used_at = now
            self.session.flush()
            return None

        row.used_at = now
        customer_row.last_login_at = now
        self.session.flush()

        return self._to_customer(customer_row)

    def create_session(
        self,
        *,
        customer_public_id: str,
        expires_in_days: int = 30,
    ) -> IssuedCustomerSession:
        customer_row = self._get_customer_row_or_raise(customer_public_id)

        if customer_row.status != CustomerStatus.ACTIVE.value:
            raise ValueError("customer is blocked")

        session_token = token_urlsafe(32)

        row = CustomerSessionRow(
            public_id=self._new_public_id("css", CustomerSessionRow),
            customer_id=customer_row.id,
            session_token_hash=_hash_token(session_token),
            expires_at=utc_now() + timedelta(days=expires_in_days),
            last_seen_at=utc_now(),
        )

        self.session.add(row)
        self.session.flush()

        return IssuedCustomerSession(
            session_token=session_token,
            record=self._to_session(row, customer_row.public_id),
        )

    def get_customer_by_session_token(self, session_token: str) -> Customer | None:
        row = self.session.execute(
            select(CustomerSessionRow).where(CustomerSessionRow.session_token_hash == _hash_token(session_token))
        ).scalar_one_or_none()

        if row is None:
            return None

        now = _normalize_now_for_datetime(row.expires_at)

        if row.revoked_at is not None or row.expires_at <= now:
            return None

        row.last_seen_at = now

        customer_row = self.session.execute(
            select(CustomerRow).where(CustomerRow.id == row.customer_id)
        ).scalar_one()

        if customer_row.status != CustomerStatus.ACTIVE.value:
            row.revoked_at = row.revoked_at or now
            self.session.flush()
            return None

        self.session.flush()

        return self._to_customer(customer_row)

    def revoke_session(self, session_token: str) -> bool:
        row = self.session.execute(
            select(CustomerSessionRow).where(CustomerSessionRow.session_token_hash == _hash_token(session_token))
        ).scalar_one_or_none()

        if row is None:
            return False

        row.revoked_at = utc_now()
        self.session.flush()

        return True

    def set_status(
        self,
        customer_public_id: str,
        status: CustomerStatus | str,
    ) -> Customer:
        customer_row = self._get_customer_row_or_raise(customer_public_id)
        status_value = status.value if isinstance(status, CustomerStatus) else CustomerStatus(status).value

        customer_row.status = status_value

        if status_value == CustomerStatus.BLOCKED.value:
            self._revoke_customer_sessions(customer_row.id)

        self.session.flush()

        return self._to_customer(customer_row)

    def _revoke_customer_sessions(self, customer_id: int) -> None:
        now = utc_now()
        rows = self.session.execute(
            select(CustomerSessionRow).where(
                CustomerSessionRow.customer_id == int(customer_id),
                CustomerSessionRow.revoked_at.is_(None),
            )
        ).scalars().all()

        for row in rows:
            row.revoked_at = now

    def create_entitlement(
        self,
        *,
        customer_public_id: str,
        order_public_id: str = "",
        product_slug: str = "",
        price_code: str = "",
        entitlement_type: CustomerEntitlementType | str = CustomerEntitlementType.ONE_TIME,
        status: CustomerEntitlementStatus | str = CustomerEntitlementStatus.PENDING,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerEntitlement:
        customer_row = self._get_customer_row_or_raise(customer_public_id)

        entitlement_type_value = (
            entitlement_type.value
            if isinstance(entitlement_type, CustomerEntitlementType)
            else CustomerEntitlementType(entitlement_type).value
        )
        status_value = (
            status.value
            if isinstance(status, CustomerEntitlementStatus)
            else CustomerEntitlementStatus(status).value
        )

        row = CustomerEntitlementRow(
            public_id=self._new_public_id("ent", CustomerEntitlementRow),
            customer_id=customer_row.id,
            order_public_id=(order_public_id or "").strip(),
            product_slug=(product_slug or "").strip(),
            price_code=(price_code or "").strip(),
            entitlement_type=entitlement_type_value,
            status=status_value,
            starts_at=starts_at,
            ends_at=ends_at,
            metadata_json=dict(metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_entitlement(row, customer_row.public_id)

    def list_entitlements(self, customer_public_id: str) -> list[CustomerEntitlement]:
        customer_row = self._get_customer_row_or_raise(customer_public_id)

        rows = self.session.execute(
            select(CustomerEntitlementRow)
            .where(CustomerEntitlementRow.customer_id == customer_row.id)
            .order_by(CustomerEntitlementRow.id.desc())
        ).scalars().all()

        return [self._to_entitlement(row, customer_row.public_id) for row in rows]

    def _get_customer_row_or_raise(self, customer_public_id: str) -> CustomerRow:
        row = self.session.execute(
            select(CustomerRow).where(CustomerRow.public_id == customer_public_id)
        ).scalar_one_or_none()

        if row is None:
            raise ValueError(f"customer not found: {customer_public_id}")

        return row

    def _new_public_id(self, prefix: str, row_type: type) -> str:
        for _ in range(20):
            public_id = generate_public_id(prefix)

            exists = self.session.execute(
                select(row_type.public_id).where(row_type.public_id == public_id)
            ).scalar_one_or_none()

            if exists is None:
                return public_id

        raise RuntimeError(f"could not generate unique {prefix} public id")

    @staticmethod
    def _to_customer(row: CustomerRow) -> Customer:
        return Customer(
            public_id=row.public_id,
            email=row.email,
            full_name=row.full_name or "",
            phone=row.phone or "",
            company=row.company or "",
            status=CustomerStatus(row.status),
            metadata=dict(row.metadata_json or {}),
            last_login_at=row.last_login_at,
        )

    @staticmethod
    def _to_auth_token(row: CustomerAuthTokenRow, customer_public_id: str) -> CustomerAuthToken:
        return CustomerAuthToken(
            public_id=row.public_id,
            customer_public_id=customer_public_id,
            purpose=CustomerAuthTokenPurpose(row.purpose),
            expires_at=row.expires_at,
            used_at=row.used_at,
        )

    @staticmethod
    def _to_session(row: CustomerSessionRow, customer_public_id: str) -> CustomerSession:
        return CustomerSession(
            public_id=row.public_id,
            customer_public_id=customer_public_id,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            last_seen_at=row.last_seen_at,
        )

    @staticmethod
    def _to_entitlement(row: CustomerEntitlementRow, customer_public_id: str) -> CustomerEntitlement:
        return CustomerEntitlement(
            public_id=row.public_id,
            customer_public_id=customer_public_id,
            order_public_id=row.order_public_id or "",
            product_slug=row.product_slug or "",
            price_code=row.price_code or "",
            entitlement_type=CustomerEntitlementType(row.entitlement_type),
            status=CustomerEntitlementStatus(row.status),
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            metadata=dict(row.metadata_json or {}),
        )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()



def _is_naive_datetime(value) -> bool:
    return value.tzinfo is None or value.tzinfo.utcoffset(value) is None


def _normalize_now_for_datetime(reference):
    now = utc_now()

    if reference is None:
        return now

    if _is_naive_datetime(reference) and not _is_naive_datetime(now):
        return now.replace(tzinfo=None)

    if not _is_naive_datetime(reference) and _is_naive_datetime(now):
        return now.replace(tzinfo=timezone.utc)

    return now
