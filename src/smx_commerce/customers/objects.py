from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from smx_commerce.catalog.objects import validate_required_text
from smx_commerce.checkout.objects import validate_email


class CustomerStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class CustomerAuthTokenPurpose(str, Enum):
    LOGIN = "login"
    ORDER_SUPPORT = "order_support"
    EMAIL_VERIFY = "email_verify"


class CustomerEntitlementType(str, Enum):
    ONE_TIME = "one_time"
    SUBSCRIPTION = "subscription"
    SERVICE_ACCESS = "service_access"


class CustomerEntitlementStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class Customer:
    public_id: str
    email: str
    full_name: str = ""
    phone: str = ""
    company: str = ""
    status: CustomerStatus = CustomerStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)
    last_login_at: datetime | None = None

    def __post_init__(self) -> None:
        self.public_id = validate_required_text(self.public_id, "public_id")
        self.email = validate_email(self.email)
        self.full_name = (self.full_name or "").strip()
        self.phone = (self.phone or "").strip()
        self.company = (self.company or "").strip()

        if not isinstance(self.status, CustomerStatus):
            self.status = CustomerStatus(self.status)

        self.metadata = dict(self.metadata or {})


@dataclass
class CustomerAuthToken:
    public_id: str
    customer_public_id: str
    purpose: CustomerAuthTokenPurpose
    expires_at: datetime
    used_at: datetime | None = None

    def __post_init__(self) -> None:
        self.public_id = validate_required_text(self.public_id, "public_id")
        self.customer_public_id = validate_required_text(self.customer_public_id, "customer_public_id")

        if not isinstance(self.purpose, CustomerAuthTokenPurpose):
            self.purpose = CustomerAuthTokenPurpose(self.purpose)


@dataclass
class IssuedCustomerAuthToken:
    token: str
    record: CustomerAuthToken


@dataclass
class CustomerSession:
    public_id: str
    customer_public_id: str
    expires_at: datetime
    revoked_at: datetime | None = None
    last_seen_at: datetime | None = None

    def __post_init__(self) -> None:
        self.public_id = validate_required_text(self.public_id, "public_id")
        self.customer_public_id = validate_required_text(self.customer_public_id, "customer_public_id")


@dataclass
class IssuedCustomerSession:
    session_token: str
    record: CustomerSession


@dataclass
class CustomerEntitlement:
    public_id: str
    customer_public_id: str
    order_public_id: str = ""
    product_slug: str = ""
    price_code: str = ""
    entitlement_type: CustomerEntitlementType = CustomerEntitlementType.ONE_TIME
    status: CustomerEntitlementStatus = CustomerEntitlementStatus.PENDING
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.public_id = validate_required_text(self.public_id, "public_id")
        self.customer_public_id = validate_required_text(self.customer_public_id, "customer_public_id")
        self.order_public_id = (self.order_public_id or "").strip()
        self.product_slug = (self.product_slug or "").strip()
        self.price_code = (self.price_code or "").strip()

        if not isinstance(self.entitlement_type, CustomerEntitlementType):
            self.entitlement_type = CustomerEntitlementType(self.entitlement_type)

        if not isinstance(self.status, CustomerEntitlementStatus):
            self.status = CustomerEntitlementStatus(self.status)

        self.metadata = dict(self.metadata or {})
