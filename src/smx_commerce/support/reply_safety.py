from __future__ import annotations

from smx_commerce.catalog.objects import validate_required_text


UNSAFE_COMPLETED_ACTION_CLAIMS = (
    "refund has been issued",
    "refund was issued",
    "we have refunded",
    "we refunded",
    "your payment has been refunded",
    "access has been restored",
    "we restored your access",
    "your account has been updated",
    "your order has been cancelled",
    "your subscription has been cancelled",
    "we cancelled your order",
)


def validate_admin_reply_body(value: str) -> str:
    body = validate_required_text(value, "body")
    normalized = " ".join(body.lower().split())

    for phrase in UNSAFE_COMPLETED_ACTION_CLAIMS:
        if phrase in normalized:
            raise ValueError(
                "reply contains an unsafe completed-action claim; save a draft that says the issue is being reviewed instead"
            )

    return body
