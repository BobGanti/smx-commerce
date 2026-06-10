from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from smx_commerce.catalog.objects import validate_required_text
from smx_commerce.checkout.objects import validate_email
from smx_commerce.core.ids import generate_public_id
from smx_commerce.support.models import SupportMessageRow, SupportThreadRow
from smx_commerce.support.objects import (
    SupportMessage,
    SupportMessageSenderType,
    SupportThread,
    SupportThreadDetail,
    SupportThreadPriority,
    SupportThreadStatus,
)


class SupportRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_thread(
        self,
        *,
        customer_email: str,
        subject: str,
        customer_name: str = "",
        order_public_id: str = "",
        status: SupportThreadStatus | str = SupportThreadStatus.OPEN,
        priority: SupportThreadPriority | str = SupportThreadPriority.NORMAL,
        issue_type: str = "general_question",
        source: str = "public_support",
        metadata: dict[str, Any] | None = None,
    ) -> SupportThread:
        row = SupportThreadRow(
            public_id=self._generate_unique_public_id("sup"),
            customer_email=validate_email(customer_email),
            customer_name=(customer_name or "").strip(),
            subject=validate_required_text(subject, "subject"),
            order_public_id=(order_public_id or "").strip(),
            status=self._thread_status_value(status),
            priority=self._thread_priority_value(priority),
            issue_type=validate_required_text(issue_type, "issue_type"),
            source=validate_required_text(source, "source"),
            metadata_json=dict(metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        return self._to_thread(row)

    def add_customer_message(
        self,
        thread_public_id: str,
        *,
        body: str,
        sender_name: str = "",
        sender_email: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SupportMessage:
        thread_row = self._get_thread_row_or_raise(thread_public_id)

        row = SupportMessageRow(
            public_id=self._generate_unique_public_id("supmsg"),
            thread_public_id=thread_row.public_id,
            sender_type=SupportMessageSenderType.CUSTOMER.value,
            sender_name=(sender_name or thread_row.customer_name or "").strip(),
            sender_email=(sender_email or thread_row.customer_email or "").strip().lower(),
            body=validate_required_text(body, "body"),
            metadata_json=dict(metadata or {}),
        )

        self.session.add(row)
        self.session.flush()

        thread_row.updated_at = row.created_at
        self.session.flush()

        return self._to_message(row)

    def get_by_public_id(self, public_id: str) -> SupportThread | None:
        value = validate_required_text(public_id, "public_id")

        row = self.session.execute(
            select(SupportThreadRow).where(SupportThreadRow.public_id == value)
        ).scalar_one_or_none()

        return self._to_thread(row) if row is not None else None

    def get_thread_with_messages(self, public_id: str) -> SupportThreadDetail | None:
        value = validate_required_text(public_id, "public_id")

        thread_row = self.session.execute(
            select(SupportThreadRow).where(SupportThreadRow.public_id == value)
        ).scalar_one_or_none()

        if thread_row is None:
            return None

        message_rows = self.session.execute(
            select(SupportMessageRow)
            .where(SupportMessageRow.thread_public_id == value)
            .order_by(SupportMessageRow.created_at.asc(), SupportMessageRow.id.asc())
        ).scalars().all()

        return SupportThreadDetail(
            thread=self._to_thread(thread_row),
            messages=[self._to_message(row) for row in message_rows],
        )

    def list_threads(
        self,
        *,
        status: SupportThreadStatus | str | None = None,
        limit: int | None = 100,
    ) -> list[SupportThread]:
        statement = select(SupportThreadRow)

        if status is not None:
            statement = statement.where(SupportThreadRow.status == self._thread_status_value(status))

        statement = statement.order_by(
            SupportThreadRow.updated_at.desc(),
            SupportThreadRow.id.desc(),
        )

        if limit is not None:
            statement = statement.limit(limit)

        rows = self.session.execute(statement).scalars().all()

        return [self._to_thread(row) for row in rows]

    def _get_thread_row_or_raise(self, public_id: str) -> SupportThreadRow:
        value = validate_required_text(public_id, "public_id")

        row = self.session.execute(
            select(SupportThreadRow).where(SupportThreadRow.public_id == value)
        ).scalar_one_or_none()

        if row is None:
            raise ValueError(f"support thread not found: {value}")

        return row

    def _generate_unique_public_id(self, prefix: str) -> str:
        for _ in range(20):
            public_id = generate_public_id(prefix)
            thread_exists = self.session.execute(
                select(SupportThreadRow.id).where(SupportThreadRow.public_id == public_id)
            ).scalar_one_or_none()
            message_exists = self.session.execute(
                select(SupportMessageRow.id).where(SupportMessageRow.public_id == public_id)
            ).scalar_one_or_none()

            if thread_exists is None and message_exists is None:
                return public_id

        raise RuntimeError(f"could not generate unique {prefix} public id")

    @staticmethod
    def _thread_status_value(status: SupportThreadStatus | str) -> str:
        return status.value if isinstance(status, SupportThreadStatus) else SupportThreadStatus(status).value

    @staticmethod
    def _thread_priority_value(priority: SupportThreadPriority | str) -> str:
        return priority.value if isinstance(priority, SupportThreadPriority) else SupportThreadPriority(priority).value

    @staticmethod
    def _to_thread(row: SupportThreadRow) -> SupportThread:
        return SupportThread(
            public_id=row.public_id,
            customer_email=row.customer_email,
            customer_name=row.customer_name or "",
            subject=row.subject,
            order_public_id=row.order_public_id or "",
            status=SupportThreadStatus(row.status),
            priority=SupportThreadPriority(row.priority),
            issue_type=row.issue_type,
            source=row.source,
            metadata=dict(row.metadata_json or {}),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_message(row: SupportMessageRow) -> SupportMessage:
        return SupportMessage(
            public_id=row.public_id,
            thread_public_id=row.thread_public_id,
            sender_type=SupportMessageSenderType(row.sender_type),
            sender_name=row.sender_name or "",
            sender_email=row.sender_email or "",
            body=row.body,
            metadata=dict(row.metadata_json or {}),
            created_at=row.created_at,
        )
