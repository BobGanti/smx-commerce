from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from smx_commerce.core.settings_models import CommerceSettingRow
from smx_commerce.settings import (
    CommerceSettings,
    normalize_setting_key,
    reject_sensitive_setting_key,
)


class CommerceSettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(self) -> CommerceSettings:
        rows = self.session.execute(
            select(CommerceSettingRow).order_by(CommerceSettingRow.key.asc())
        ).scalars().all()

        return CommerceSettings({row.key: row.value_json for row in rows})

    def get(self, key: str, default: Any = None) -> Any:
        normalized_key = normalize_setting_key(key)

        row = self.session.execute(
            select(CommerceSettingRow).where(CommerceSettingRow.key == normalized_key)
        ).scalar_one_or_none()

        return default if row is None else row.value_json

    def set_many(self, values: dict[str, Any]) -> CommerceSettings:
        for key, value in dict(values or {}).items():
            self.set(key, value)

        self.session.flush()
        return self.get_all()

    def set(self, key: str, value: Any) -> None:
        normalized_key = normalize_setting_key(key)
        reject_sensitive_setting_key(normalized_key)

        row = self.session.execute(
            select(CommerceSettingRow).where(CommerceSettingRow.key == normalized_key)
        ).scalar_one_or_none()

        if row is None:
            self.session.add(
                CommerceSettingRow(
                    key=normalized_key,
                    value_json=value,
                )
            )
        else:
            row.value_json = value

    def delete(self, key: str) -> CommerceSettings:
        normalized_key = normalize_setting_key(key)

        self.session.execute(
            delete(CommerceSettingRow).where(CommerceSettingRow.key == normalized_key)
        )
        self.session.flush()

        return self.get_all()
