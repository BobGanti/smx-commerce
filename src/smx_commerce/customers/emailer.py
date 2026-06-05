from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from smx_commerce.notifications import EmailMessage, EmailSender, NotificationResult


@dataclass(frozen=True)
class CustomerLoginEmailContext:
    to_email: str
    token: str
    public_base_url: str
    store_title: str = "smxCommerce"
    from_email: str | None = None
    next_url: str | None = None


class CustomerLoginEmailService:
    def __init__(
        self,
        sender: EmailSender,
        *,
        from_email: str | None = None,
        store_title: str = "smxCommerce",
    ):
        self.sender = sender
        self.from_email = from_email
        self.store_title = store_title

    def send_login_link(
        self,
        *,
        to_email: str,
        token: str,
        public_base_url: str,
        next_url: str | None = None,
    ) -> NotificationResult:
        message = self.build_login_link_message(
            CustomerLoginEmailContext(
                to_email=to_email,
                token=token,
                public_base_url=public_base_url,
                store_title=self.store_title,
                from_email=self.from_email,
                next_url=next_url,
            )
        )

        try:
            self.sender.send(message)
            return NotificationResult(sent=True)
        except Exception as exc:
            return NotificationResult(sent=False, error_message=str(exc))

    def build_login_link_message(self, context: CustomerLoginEmailContext) -> EmailMessage:
        verify_url = self.build_verify_url(
            public_base_url=context.public_base_url,
            token=context.token,
            next_url=context.next_url,
        )

        subject = f"Your {context.store_title} sign-in link"

        body_text = (
            f"Hello,\n\n"
            f"Use this secure link to sign in to {context.store_title}:\n\n"
            f"{verify_url}\n\n"
            "This link is single-use and expires soon. "
            "If you did not request it, you can ignore this email.\n"
        )

        return EmailMessage(
            to_email=context.to_email,
            from_email=context.from_email,
            subject=subject,
            body_text=body_text,
        )

    @staticmethod
    def build_verify_url(
        *,
        public_base_url: str,
        token: str,
        next_url: str | None = None,
    ) -> str:
        base_url = (public_base_url or "").rstrip("/")

        query = {"token": token}
        if next_url:
            query["next"] = next_url

        return f"{base_url}/commerce/customer/verify?{urlencode(query)}"
