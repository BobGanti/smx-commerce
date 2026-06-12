from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from smx_commerce.ai import CommerceAIClient, CommerceAIUsage


@dataclass(frozen=True)
class SupportReplyPlan:
    reply_strategy: str
    facts_to_include: list[str]
    questions_to_ask: list[str]
    forbidden_claims: list[str]
    needs_human_review: bool
    usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


@dataclass(frozen=True)
class SupportReplyComposition:
    body: str
    tone: str
    next_actions: list[str]
    usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


@dataclass(frozen=True)
class SupportReplyVerification:
    is_safe: bool
    needs_revision: bool
    concerns: list[str]
    usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


@dataclass(frozen=True)
class SupportReplyDraft:
    body: str
    tone: str
    needs_human_review: bool
    next_actions: list[str]
    usage_by_agent: dict[str, CommerceAIUsage] = field(default_factory=dict)
    total_usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)


class SupportReplyPlannerAgent:
    def __init__(self, ai_client: CommerceAIClient):
        self.ai_client = ai_client

    def plan(self, context: dict[str, Any]) -> SupportReplyPlan:
        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_reply_planner",
            system_prompt=(
                "You plan a support reply for smx-commerce. "
                "Return only reply strategy, facts to include, questions to ask, forbidden claims, and human review flag. "
                "Do not write customer-facing prose."
            ),
            task_prompt="Plan the support reply.",
            expected_schema={
                "type": "object",
                "required": [
                    "reply_strategy",
                    "facts_to_include",
                    "questions_to_ask",
                    "forbidden_claims",
                    "needs_human_review",
                ],
                "properties": {
                    "reply_strategy": {"type": "string"},
                    "facts_to_include": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "questions_to_ask": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "forbidden_claims": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "needs_human_review": {"type": "boolean"},
                },
            },
            context=context,
        )

        usage = _usage_from_agent_result(result)
        reply_strategy = str(result.get("reply_strategy", "")).strip()
        if not reply_strategy:
            reply_strategy = "Acknowledge the request, avoid inventing facts, and ask for missing information if needed."

        return SupportReplyPlan(
            reply_strategy=reply_strategy,
            facts_to_include=_clean_string_list(result.get("facts_to_include", [])),
            questions_to_ask=_clean_string_list(result.get("questions_to_ask", [])),
            forbidden_claims=_clean_string_list(result.get("forbidden_claims", [])),
            needs_human_review=bool(result.get("needs_human_review", True)),
            usage=usage,
        )


class SupportReplyComposerAgent:
    def __init__(self, ai_client: CommerceAIClient):
        self.ai_client = ai_client

    def compose(self, context: dict[str, Any]) -> SupportReplyComposition:
        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_reply_composer",
            system_prompt=(
                "You write a customer-facing support reply from an approved reply plan. "
                "Do not invent facts. Do not claim that refunds, cancellations, account changes, or emails have already been performed."
            ),
            task_prompt="Write the admin-reviewable support reply draft.",
            expected_schema={
                "type": "object",
                "required": [
                    "body",
                    "tone",
                    "next_actions",
                ],
                "properties": {
                    "body": {"type": "string"},
                    "tone": {"type": "string"},
                    "next_actions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            context=context,
        )

        usage = _usage_from_agent_result(result)
        body = str(result.get("body", "")).strip()
        if not body:
            body = "Thank you for contacting us. We are reviewing your request and will get back to you shortly."

        tone = str(result.get("tone", "")).strip() or "professional"

        return SupportReplyComposition(
            body=body,
            tone=tone,
            next_actions=_clean_string_list(result.get("next_actions", [])),
            usage=usage,
        )


class SupportReplyVerifierAgent:
    def __init__(self, ai_client: CommerceAIClient):
        self.ai_client = ai_client

    def verify(self, context: dict[str, Any]) -> SupportReplyVerification:
        result = self.ai_client.run_agent_task(
            agent_name="commerce_support_reply_verifier",
            system_prompt=(
                "You verify a drafted smx-commerce support reply. "
                "Check for hallucinated facts, unsafe completed-action claims, unsupported refund/cancellation/access promises, and missing required caveats. "
                "Return only safety verdict fields. Do not rewrite the reply."
            ),
            task_prompt="Verify the support reply draft.",
            expected_schema={
                "type": "object",
                "required": [
                    "is_safe",
                    "needs_revision",
                    "concerns",
                ],
                "properties": {
                    "is_safe": {"type": "boolean"},
                    "needs_revision": {"type": "boolean"},
                    "concerns": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            context=context,
        )

        usage = _usage_from_agent_result(result)
        return SupportReplyVerification(
            is_safe=bool(result.get("is_safe", True)),
            needs_revision=bool(result.get("needs_revision", False)),
            concerns=_clean_string_list(result.get("concerns", [])),
            usage=usage,
        )


class SupportReplyComposerService:
    def __init__(self, ai_client: CommerceAIClient):
        if ai_client is None:
            raise ValueError("ai_client is required for support reply composition")

        self.ai_client = ai_client
        self.planner = SupportReplyPlannerAgent(ai_client)
        self.composer = SupportReplyComposerAgent(ai_client)
        self.verifier = SupportReplyVerifierAgent(ai_client)

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

        base_context = {
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
        }

        plan = self.planner.plan(base_context)

        composition_context = {
            **base_context,
            "reply_plan": {
                "reply_strategy": plan.reply_strategy,
                "facts_to_include": plan.facts_to_include,
                "questions_to_ask": plan.questions_to_ask,
                "forbidden_claims": plan.forbidden_claims,
                "needs_human_review": plan.needs_human_review,
            },
        }

        composition = self.composer.compose(composition_context)

        verification_context = {
            **composition_context,
            "draft_reply": {
                "body": composition.body,
                "tone": composition.tone,
                "next_actions": composition.next_actions,
            },
        }

        verification = self.verifier.verify(verification_context)

        next_actions = list(composition.next_actions)
        if verification.concerns:
            next_actions.extend([f"Verifier concern: {concern}" for concern in verification.concerns])

        usage_by_agent = {
            "commerce_support_reply_planner": plan.usage,
            "commerce_support_reply_composer": composition.usage,
            "commerce_support_reply_verifier": verification.usage,
        }
        total_usage = _sum_usage_by_agent(usage_by_agent)

        return SupportReplyDraft(
            body=composition.body,
            tone=composition.tone,
            needs_human_review=bool(plan.needs_human_review or verification.needs_revision or not verification.is_safe),
            next_actions=next_actions,
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

def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]
