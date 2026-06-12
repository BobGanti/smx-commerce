from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from smx_commerce.ai import CommerceAIClient, CommerceAIUsage


ALLOWED_SUPPORT_PRIORITIES = {
    "low",
    "normal",
    "high",
    "urgent",
}


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
class IssueClassificationResult:
    issue_type: str
    confidence: float
    usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


@dataclass(frozen=True)
class SupportSummaryResult:
    summary: str
    usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


@dataclass(frozen=True)
class MissingInformationResult:
    missing_information: list[str]
    usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


@dataclass(frozen=True)
class EscalationAssessmentResult:
    should_escalate: bool
    usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


@dataclass(frozen=True)
class PriorityAssessmentResult:
    recommended_priority: str
    usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


@dataclass(frozen=True)
class SupportTriageResult:
    issue_type: str
    confidence: float
    summary: str
    should_escalate: bool
    recommended_priority: str
    missing_information: list[str]
    usage_by_agent: dict[str, CommerceAIUsage] = field(default_factory=dict)
    total_usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


class SupportIssueClassifierAgent:
    def __init__(self, ai_client: CommerceAIClient):
        self.ai_client = ai_client

    def classify(self, context: dict[str, Any]) -> IssueClassificationResult:
        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_issue_classifier",
            system_prompt=(
                "You classify smx-commerce support requests. "
                "Return only the best allowed issue_type and confidence. "
                "Do not summarize, prioritize, escalate, or draft replies."
            ),
            task_prompt="Classify the customer support issue.",
            expected_schema={
                "type": "object",
                "required": ["issue_type", "confidence"],
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
                },
            },
            context=context,
        )

        usage = _usage_from_agent_result(result)
        issue_type = str(result.get("issue_type", "")).strip()
        if issue_type not in ALLOWED_SUPPORT_ISSUE_TYPES:
            issue_type = "general_question"

        return IssueClassificationResult(
            issue_type=issue_type,
            confidence=_coerce_confidence(result.get("confidence")),
            usage=usage,
        )


class SupportSummaryAgent:
    def __init__(self, ai_client: CommerceAIClient):
        self.ai_client = ai_client

    def summarize(self, context: dict[str, Any]) -> SupportSummaryResult:
        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_summary",
            system_prompt=(
                "You summarize customer support requests for an admin. "
                "Return only a concise factual summary. "
                "Do not classify, prioritize, escalate, or draft replies."
            ),
            task_prompt="Summarize the customer support request.",
            expected_schema={
                "type": "object",
                "required": ["summary"],
                "properties": {
                    "summary": {"type": "string"},
                },
            },
            context=context,
        )

        usage = _usage_from_agent_result(result)
        summary = str(result.get("summary", "")).strip()
        if not summary:
            summary = "Customer submitted a support request."

        return SupportSummaryResult(summary=summary, usage=usage)


class SupportMissingInformationAgent:
    def __init__(self, ai_client: CommerceAIClient):
        self.ai_client = ai_client

    def identify_missing_information(self, context: dict[str, Any]) -> MissingInformationResult:
        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_missing_information",
            system_prompt=(
                "You identify missing information needed to resolve a support request. "
                "Return only missing_information. "
                "Do not classify, prioritize, escalate, summarize, or draft replies."
            ),
            task_prompt="Identify missing information needed for support resolution.",
            expected_schema={
                "type": "object",
                "required": ["missing_information"],
                "properties": {
                    "missing_information": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            context=context,
        )

        usage = _usage_from_agent_result(result)
        return MissingInformationResult(
            missing_information=_clean_string_list(result.get("missing_information", [])),
            usage=usage,
        )


class SupportEscalationAssessorAgent:
    def __init__(self, ai_client: CommerceAIClient):
        self.ai_client = ai_client

    def assess(self, context: dict[str, Any]) -> EscalationAssessmentResult:
        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_escalation_assessor",
            system_prompt=(
                "You decide whether a support request needs human escalation. "
                "Return only should_escalate. "
                "Do not classify, summarize, prioritize, identify missing info, or draft replies."
            ),
            task_prompt="Decide whether this support request should be escalated to a human admin.",
            expected_schema={
                "type": "object",
                "required": ["should_escalate"],
                "properties": {
                    "should_escalate": {"type": "boolean"},
                },
            },
            context=context,
        )

        usage = _usage_from_agent_result(result)
        return EscalationAssessmentResult(
            should_escalate=bool(result.get("should_escalate", False)),
            usage=usage,
        )


class SupportPriorityAssessorAgent:
    def __init__(self, ai_client: CommerceAIClient):
        self.ai_client = ai_client

    def assess(self, context: dict[str, Any]) -> PriorityAssessmentResult:
        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_priority_assessor",
            system_prompt=(
                "You recommend support priority only. "
                "Return only recommended_priority using low, normal, high, or urgent. "
                "Do not classify, summarize, escalate, identify missing info, or draft replies."
            ),
            task_prompt="Recommend the support priority.",
            expected_schema={
                "type": "object",
                "required": ["recommended_priority"],
                "properties": {
                    "recommended_priority": {
                        "type": "string",
                        "enum": sorted(ALLOWED_SUPPORT_PRIORITIES),
                    },
                },
            },
            context=context,
        )

        usage = _usage_from_agent_result(result)
        priority = str(result.get("recommended_priority", "")).strip()
        return PriorityAssessmentResult(recommended_priority=priority, usage=usage)


class SupportTriageService:
    def __init__(self, ai_client: CommerceAIClient):
        if ai_client is None:
            raise ValueError("ai_client is required for support triage")

        self.ai_client = ai_client
        self.issue_classifier = SupportIssueClassifierAgent(ai_client)
        self.summary_agent = SupportSummaryAgent(ai_client)
        self.missing_information_agent = SupportMissingInformationAgent(ai_client)
        self.escalation_assessor = SupportEscalationAssessorAgent(ai_client)
        self.priority_assessor = SupportPriorityAssessorAgent(ai_client)

    def triage(
        self,
        *,
        customer_message: str,
        customer_email: str = "",
        order_public_id: str = "",
        subject: str = "",
        order_context: dict[str, Any] | None = None,
    ) -> SupportTriageResult:
        message = (customer_message or "").strip()
        if not message:
            raise ValueError("customer_message is required")

        context = {
            "customer_email": customer_email,
            "order_public_id": order_public_id,
            "order_context": order_context or {},
            "subject": subject,
            "customer_message": message,
            "allowed_issue_types": sorted(ALLOWED_SUPPORT_ISSUE_TYPES),
            "allowed_priorities": sorted(ALLOWED_SUPPORT_PRIORITIES),
        }

        with ThreadPoolExecutor(max_workers=5) as executor:
            classification_future = executor.submit(self.issue_classifier.classify, context)
            summary_future = executor.submit(self.summary_agent.summarize, context)
            missing_information_future = executor.submit(
                self.missing_information_agent.identify_missing_information,
                context,
            )
            escalation_future = executor.submit(self.escalation_assessor.assess, context)
            priority_future = executor.submit(self.priority_assessor.assess, context)

            classification = classification_future.result()
            summary = summary_future.result()
            missing_information = missing_information_future.result()
            escalation = escalation_future.result()
            priority = priority_future.result()

        recommended_priority = priority.recommended_priority
        if recommended_priority not in ALLOWED_SUPPORT_PRIORITIES:
            recommended_priority = "high" if escalation.should_escalate else "normal"

        usage_by_agent = {
            "commerce_support_issue_classifier": classification.usage,
            "commerce_support_summary": summary.usage,
            "commerce_support_missing_information": missing_information.usage,
            "commerce_support_escalation_assessor": escalation.usage,
            "commerce_support_priority_assessor": priority.usage,
        }
        total_usage = _sum_usage_by_agent(usage_by_agent)

        return SupportTriageResult(
            issue_type=classification.issue_type,
            confidence=classification.confidence,
            summary=summary.summary,
            should_escalate=escalation.should_escalate,
            recommended_priority=recommended_priority,
            missing_information=missing_information.missing_information,
            usage_by_agent=usage_by_agent,
            total_usage=total_usage,
        )




def _usage_from_agent_result(result: Any) -> CommerceAIUsage:
    usage = getattr(result, "usage", None)
    if isinstance(usage, CommerceAIUsage):
        return usage
    return CommerceAIUsage()


def _sum_usage_by_agent(usage_by_agent: dict[str, CommerceAIUsage]) -> CommerceAIUsage:
    total = CommerceAIUsage()
    for usage in usage_by_agent.values():
        total = total.plus(usage)
    return total

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


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]
