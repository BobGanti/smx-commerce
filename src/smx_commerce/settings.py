from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SENSITIVE_SETTING_KEYS = {
    "stripe_secret_key",
    "stripe_webhook_secret",
    "smtp_password",
    "admin_token",
    "database_url",
}


@dataclass
class CommerceSettings:
    values: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned = {}

        for key, value in dict(self.values or {}).items():
            normalized_key = normalize_setting_key(key)
            reject_sensitive_setting_key(normalized_key)
            cleaned[normalized_key] = value

        self.values = cleaned

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(normalize_setting_key(key), default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.values)


def normalize_setting_key(key: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise ValueError("setting key is required")

    normalized = key.strip().lower()

    if not normalized.replace("_", "").replace("-", "").isalnum():
        raise ValueError("setting key may only contain letters, numbers, underscores, and hyphens")

    return normalized.replace("-", "_")


def reject_sensitive_setting_key(key: str) -> None:
    if key in SENSITIVE_SETTING_KEYS:
        raise ValueError(f"setting is sensitive and must not be stored here: {key}")
