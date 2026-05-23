from .emailer import (
    EmailMessage,
    EmailSender,
    NotificationResult,
    OrderConfirmationEmailService,
)
from .memory_sender import MemoryEmailSender
from .smtp_sender import SMTPEmailSender

__all__ = [
    "EmailMessage",
    "EmailSender",
    "MemoryEmailSender",
    "NotificationResult",
    "OrderConfirmationEmailService",
    "SMTPEmailSender",
]
