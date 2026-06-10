from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from smx_commerce.catalog.objects import validate_required_text
from smx_commerce.checkout.objects import validate_email


class SupportThreadStatus(str, Enum):
    OPEN = "open"
    REVIEWING = "reviewing"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"
    FLAGGED = "flagged"


class SupportThreadPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SupportMessageSenderType(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    AGENT = "agent"
    SYSTEM = "system"


@dataclass
class SupportThread:
    public_id: str
    customer_email: str
    subject: str
    customer_name: str = ""
    order_public_id: str = ""
    status: SupportThreadStatus = SupportThreadStatus.OPEN
    priority: SupportThreadPriority = SupportThreadPriority.NORMAL
    issue_type: str = "general_question"
    source: str = "public_support"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.public_id = validate_required_text(self.public_id, "public_id")
        self.customer_email = validate_email(self.customer_email)
        self.subject = validate_required_text(self.subject, "subject")
        self.customer_name = (self.customer_name or "").strip()
        self.order_public_id = (self.order_public_id or "").strip()

        if not isinstance(self.status, SupportThreadStatus):
            self.status = SupportThreadStatus(self.status)

        if not isinstance(self.priority, SupportThreadPriority):
            self.priority = SupportThreadPriority(self.priority)

        self.issue_type = validate_required_text(self.issue_type, "issue_type")
        self.source = validate_required_text(self.source, "source")
        self.metadata = dict(self.metadata or {})


@dataclass
class SupportMessage:
    public_id: str
    thread_public_id: str
    sender_type: SupportMessageSenderType
    body: str
    sender_name: str = ""
    sender_email: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        self.public_id = validate_required_text(self.public_id, "public_id")
        self.thread_public_id = validate_required_text(self.thread_public_id, "thread_public_id")

        if not isinstance(self.sender_type, SupportMessageSenderType):
            self.sender_type = SupportMessageSenderType(self.sender_type)

        self.body = validate_required_text(self.body, "body")
        self.sender_name = (self.sender_name or "").strip()
        self.sender_email = (self.sender_email or "").strip().lower()
        self.metadata = dict(self.metadata or {})


@dataclass(frozen=True)
class SupportThreadDetail:
    thread: SupportThread
    messages: list[SupportMessage]
