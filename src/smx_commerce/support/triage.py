from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from smx_commerce.ai import CommerceAIClient


ALLOWED_SUPPORT_ISSUE_TYPES = {
    "order_status",
    "payment_problem",
    "refund_request",
    "cancellation_request",
    "product_question",
    "delivery_issue",
    "account_access_issue",
    "subscription_issue",
    "complaint",
    "fraud_or_spam",
    "human_escalation",
    "general_question",
}


@dataclass(frozen=True)
class SupportTriageResult:
    issue_type: str
    confidence: float
    summary: str
    should_escalate: bool
    missing_information: list[str]


class SupportTriageService:
    def __init__(self, ai_client: CommerceAIClient):
        if ai_client is None:
            raise ValueError("ai_client is required for support triage")

        self.ai_client = ai_client

    def triage(
        self,
        *,
        customer_message: str,
        customer_email: str = "",
        order_public_id: str = "",
        subject: str = "",
    ) -> SupportTriageResult:
        message = (customer_message or "").strip()
        if not message:
            raise ValueError("customer_message is required")

        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_triage",
            system_prompt=(
                "You are the smx-commerce support triage agent. "
                "Classify customer support requests using only the allowed issue types. "
                "Do not invent issue types. If uncertain, use general_question or human_escalation."
            ),
            task_prompt="Classify this customer support request.",
            expected_schema={
                "type": "object",
                "required": [
                    "issue_type",
                    "confidence",
                    "summary",
                    "should_escalate",
                    "missing_information",
                ],
                "properties": {
                    "issue_type": {
                        "type": "string",
                        "enum": sorted(ALLOWED_SUPPORT_ISSUE_TYPES),
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "summary": {"type": "string"},
                    "should_escalate": {"type": "boolean"},
                    "missing_information": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            context={
                "customer_email": customer_email,
                "order_public_id": order_public_id,
                "subject": subject,
                "customer_message": message,
                "allowed_issue_types": sorted(ALLOWED_SUPPORT_ISSUE_TYPES),
            },
        )

        issue_type = str(result.get("issue_type", "")).strip()

        if issue_type not in ALLOWED_SUPPORT_ISSUE_TYPES:
            issue_type = "general_question"

        confidence = _coerce_confidence(result.get("confidence"))

        summary = str(result.get("summary", "")).strip()
        if not summary:
            summary = "Customer submitted a support request."

        should_escalate = bool(result.get("should_escalate", False))

        missing_information = result.get("missing_information", [])
        if not isinstance(missing_information, list):
            missing_information = []

        return SupportTriageResult(
            issue_type=issue_type,
            confidence=confidence,
            summary=summary,
            should_escalate=should_escalate,
            missing_information=[str(item).strip() for item in missing_information if str(item).strip()],
        )


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    if confidence < 0:
        return 0.0

    if confidence > 1:
        return 1.0

    return confidence
