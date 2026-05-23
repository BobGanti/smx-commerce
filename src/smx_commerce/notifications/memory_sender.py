from __future__ import annotations

from smx_commerce.notifications.emailer import EmailMessage


class MemoryEmailSender:
    def __init__(self):
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.messages.append(message)
