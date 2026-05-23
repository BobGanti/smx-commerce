from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from smx_commerce.checkout import Order


@dataclass(frozen=True)
class EmailMessage:
    to_email: str
    subject: str
    body_text: str
    from_email: str | None = None


@dataclass(frozen=True)
class NotificationResult:
    sent: bool
    error_message: str = ""


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None:
        ...


class OrderConfirmationEmailService:
    def __init__(
        self,
        sender: EmailSender,
        *,
        from_email: str | None = None,
        brand_name: str = "smx-commerce",
    ):
        self.sender = sender
        self.from_email = from_email
        self.brand_name = brand_name

    def send_order_paid_confirmation(self, order: Order) -> NotificationResult:
        message = self.build_order_paid_message(order)

        try:
            self.sender.send(message)
            return NotificationResult(sent=True)

        except Exception as exc:
            return NotificationResult(sent=False, error_message=str(exc))

    def build_order_paid_message(self, order: Order) -> EmailMessage:
        subject = f"Your {self.brand_name} order is confirmed"

        body_text = (
            f"Hello {order.buyer.full_name},\n\n"
            "Your payment has been confirmed.\n\n"
            f"Order ID: {order.public_id}\n"
            f"Product: {order.product_slug}\n"
            f"Price option: {order.price_code}\n"
            f"Amount paid: {order.amount.currency} {order.amount.major()}\n\n"
            "Thank you."
        )

        return EmailMessage(
            to_email=order.buyer.email,
            from_email=self.from_email,
            subject=subject,
            body_text=body_text,
        )
