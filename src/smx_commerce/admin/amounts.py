from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_admin_amount_to_cents(value: str, *, field_name: str = "amount") -> int:
    raw_value = str(value or "").strip()

    if not raw_value:
        raise ValueError(f"{field_name} is required")

    try:
        amount = Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a valid currency amount") from exc

    if amount < 0:
        raise ValueError(f"{field_name} cannot be negative")

    cents = (amount * Decimal("100")).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )

    return int(cents)


def parse_admin_price_amount_from_payload(payload: dict, *, is_form: bool) -> int:
    """
    Browser forms should send amount_major, for example:
      1     -> 100
      1.50  -> 150
      299   -> 29900

    JSON/API callers keep using amount_cents.

    For temporary backwards compatibility, form submissions that still send
    amount_cents are also accepted.
    """
    if is_form:
        amount_major = payload.get("amount_major")

        if amount_major not in {None, ""}:
            return parse_admin_amount_to_cents(amount_major, field_name="amount")

        if payload.get("amount_cents") not in {None, ""}:
            return int(payload.get("amount_cents", 0) or 0)

        return parse_admin_amount_to_cents("", field_name="amount")

    return int(payload.get("amount_cents", 0) or 0)
