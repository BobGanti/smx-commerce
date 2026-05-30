from __future__ import annotations

import secrets


def generate_public_id(prefix: str, *, token_bytes: int = 8) -> str:
    normalized_prefix = (prefix or "").strip().lower().replace("_", "-")

    if not normalized_prefix:
        raise ValueError("public id prefix is required")

    token = secrets.token_urlsafe(token_bytes).rstrip("=")
    token = token.replace("-", "").replace("_", "").lower()

    return f"{normalized_prefix}_{token}"