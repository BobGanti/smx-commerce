from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from smx_commerce.checkout import Order
from smx_commerce.notifications.receipt_pdf import generate_order_receipt_pdf


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


@dataclass(frozen=True)
class EmailMessage:
    to_email: str
    subject: str
    body_text: str
    from_email: str | None = None
    attachments: tuple[EmailAttachment, ...] = ()


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
        receipts_dir: str | None = None,
        logo_path: str | None = None,
    ):
        self.sender = sender
        self.from_email = from_email
        self.brand_name = brand_name
        self.receipts_dir = receipts_dir
        self.logo_path = logo_path


    def send_order_paid_confirmation(self, order: Order) -> NotificationResult:
        message = self.build_order_paid_message(order)

        try:
            self.sender.send(message)
            return NotificationResult(sent=True)

        except Exception as exc:
            return NotificationResult(sent=False, error_message=str(exc))

    def _order_lines_text(self, order: Order) -> str:
        cart_items = (order.metadata or {}).get("cart_items")

        if isinstance(cart_items, list) and cart_items:
            lines = ["Items purchased:"]

            for item in cart_items:
                if not isinstance(item, dict):
                    continue

                product_name = str(item.get("product_name", "")).strip() or "Product"
                price_label = str(item.get("price_label", "")).strip() or "Price option"
                currency = str(item.get("currency", order.amount.currency)).upper()
                amount_cents = int(item.get("amount_cents", 0))
                quantity = int(item.get("quantity", 1))
                line_total = amount_cents * quantity / 100

                lines.append(
                    f"- {product_name} x {quantity} · {price_label} · {currency} {line_total:.2f}"
                )

            return "\n".join(lines)

        return (
            f"Product: {order.product_slug}\n"
            f"Price option: {order.price_code}"
        )
    

    def build_order_paid_message(self, order: Order) -> EmailMessage:
        subject = f"Your {self.brand_name} order is confirmed"

        attachments: tuple[EmailAttachment, ...] = ()

        if self.receipts_dir:
            receipt = generate_order_receipt_pdf(
                order,
                receipts_dir=self.receipts_dir,
                brand_name=self.brand_name,
                logo_path=self.logo_path,
            )

            attachments = (
                EmailAttachment(
                    filename=receipt.filename,
                    content=receipt.content,
                    mime_type="application/pdf",
                ),
            )

        receipt_note = (
            "Your PDF receipt is attached to this email.\n\n"
            if attachments
            else ""
        )

        order_lines = self._order_lines_text(order)

        body_text = (
            f"Hello {order.buyer.full_name},\n\n"
            "Your payment has been confirmed.\n\n"
            f"Order ID: {order.public_id}\n"
            f"{order_lines}\n"
            f"Amount paid: {order.amount.currency.upper()} {order.amount.major():.2f}\n\n"
            f"{receipt_note}"
            "Thank you."
        )

        return EmailMessage(
            to_email=order.buyer.email,
            from_email=self.from_email,
            subject=subject,
            body_text=body_text,
            attachments=attachments,
        )
