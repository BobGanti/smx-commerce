from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class CommerceAIClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommerceAIUsage:
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "raw": dict(self.raw),
        }

    def plus(self, other: "CommerceAIUsage") -> "CommerceAIUsage":
        return CommerceAIUsage(
            provider=self.provider or other.provider,
            model=self.model or other.model,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            raw={},
        )


@dataclass(frozen=True)
class CommerceAIResult:
    data: dict[str, Any]
    usage: CommerceAIUsage = field(default_factory=CommerceAIUsage)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, dict):
            return self.data == other
        return super().__eq__(other)


class CommerceAIClient(Protocol):
    def run_agent_task(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict[str, Any],
        context: dict[str, Any],
    ) -> CommerceAIResult:
        ...
