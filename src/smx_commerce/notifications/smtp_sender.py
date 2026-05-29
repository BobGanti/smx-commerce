from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage as StdlibEmailMessage
import smtplib

from smx_commerce.catalog.objects import validate_required_text
from smx_commerce.notifications.emailer import EmailMessage


@dataclass(frozen=True)
class SMTPEmailSender:
    host: str
    port: int = 587
    default_from_email: str | None = None
    username: str | None = None
    password: str | None = None
    use_tls: bool = True
    use_ssl: bool = False
    timeout: float = 10.0

    def __post_init__(self) -> None:
        validate_required_text(self.host, "host")

        if int(self.port) <= 0:
            raise ValueError("port must be positive")

        if self.use_tls and self.use_ssl:
            raise ValueError("use_tls and use_ssl cannot both be true")

    def send(self, message: EmailMessage) -> None:
        from_email = message.from_email or self.default_from_email

        if not from_email:
            raise ValueError("from_email is required")

        validate_required_text(message.to_email, "to_email")
        validate_required_text(message.subject, "subject")

        ###
        email = StdlibEmailMessage()
        email["From"] = from_email
        email["To"] = message.to_email
        email["Subject"] = message.subject
        email.set_content(message.body_text or "")

        for attachment in message.attachments:
            maintype, _, subtype = attachment.mime_type.partition("/")

            if not maintype or not subtype:
                maintype = "application"
                subtype = "octet-stream"

            email.add_attachment(
                attachment.content,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
            )

        smtp_class = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP

        with smtp_class(self.host, int(self.port), timeout=self.timeout) as smtp:
            if self.use_tls:
                smtp.starttls()

            if self.username:
                smtp.login(self.username, self.password or "")

            smtp.send_message(email)
