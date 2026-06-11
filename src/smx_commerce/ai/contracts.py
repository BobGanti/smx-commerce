from __future__ import annotations

from typing import Any, Protocol


class CommerceAIClientError(RuntimeError):
    pass


class CommerceAIClient(Protocol):
    def run_agent_task(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        ...
