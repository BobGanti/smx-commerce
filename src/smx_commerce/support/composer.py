from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from smx_commerce.ai import CommerceAIClient


@dataclass(frozen=True)
class SupportReplyDraft:
    body: str
    tone: str
    needs_human_review: bool
    next_actions: list[str]


class SupportReplyComposerService:
    def __init__(self, ai_client: CommerceAIClient):
        if ai_client is None:
            raise ValueError("ai_client is required for support reply composition")

        self.ai_client = ai_client

    def compose_reply(
        self,
        *,
        customer_message: str,
        customer_email: str = "",
        customer_name: str = "",
        subject: str = "",
        issue_type: str = "",
        triage_summary: str = "",
        missing_information: list[str] | None = None,
        order_context: dict[str, Any] | None = None,
    ) -> SupportReplyDraft:
        message = (customer_message or "").strip()
        if not message:
            raise ValueError("customer_message is required")

        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_composer",
            system_prompt=(
                "You are the smx-commerce support reply composer. "
                "Draft a helpful, professional reply for an admin to review. "
                "Do not claim that refunds, cancellations, account changes, or emails have already been performed. "
                "Do not invent order facts. Ask for missing information when needed."
            ),
            task_prompt="Draft an admin-reviewable customer support reply.",
            expected_schema={
                "type": "object",
                "required": [
                    "body",
                    "tone",
                    "needs_human_review",
                    "next_actions",
                ],
                "properties": {
                    "body": {"type": "string"},
                    "tone": {"type": "string"},
                    "needs_human_review": {"type": "boolean"},
                    "next_actions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            context={
                "customer_email": customer_email,
                "customer_name": customer_name,
                "subject": subject,
                "issue_type": issue_type,
                "triage_summary": triage_summary,
                "missing_information": missing_information or [],
                "order_context": order_context or {},
                "customer_message": message,
                "safety_rules": [
                    "Draft only. Do not send.",
                    "Do not promise a refund was issued.",
                    "Do not promise account access was changed.",
                    "Ask for missing order information if needed.",
                ],
            },
        )

        body = str(result.get("body", "")).strip()
        if not body:
            body = "Thank you for contacting us. We are reviewing your request and will get back to you shortly."

        tone = str(result.get("tone", "")).strip() or "professional"

        next_actions = result.get("next_actions", [])
        if not isinstance(next_actions, list):
            next_actions = []

        return SupportReplyDraft(
            body=body,
            tone=tone,
            needs_human_review=bool(result.get("needs_human_review", True)),
            next_actions=[
                str(action).strip()
                for action in next_actions
                if str(action).strip()
            ],
        )
