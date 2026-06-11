from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google import genai


class GeminiCommerceAIClient:
    def __init__(self, *, model: str):
        if not model:
            raise ValueError("GEMINI_MODEL is required.")

        self.model = model
        self.client = genai.Client()

    def run_agent_task(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict,
        context: dict,
    ) -> dict:
        prompt = self._build_prompt(
            agent_name=agent_name,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            expected_schema=expected_schema,
            context=context,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        text = (response.text or "").strip()
        return self._parse_json_response(text)

    def _build_prompt(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict,
        context: dict,
    ) -> str:
        return (
            "You are running a bounded smx-commerce support agent task.\n"
            "Return JSON only. Do not wrap the JSON in markdown fences.\n\n"
            f"Agent name:\n{agent_name}\n\n"
            f"System prompt:\n{system_prompt}\n\n"
            f"Task prompt:\n{task_prompt}\n\n"
            f"Expected JSON schema:\n{json.dumps(expected_schema, indent=2, sort_keys=True)}\n\n"
            f"Context:\n{json.dumps(context, indent=2, sort_keys=True)}\n"
        )

    def _parse_json_response(self, text: str) -> dict:
        if not text:
            raise ValueError("Gemini returned an empty response.")

        cleaned = text.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").strip()

        if cleaned.endswith("```"):
            cleaned = cleaned.removesuffix("```").strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini did not return valid JSON: {cleaned}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Gemini response must be a JSON object.")

        return parsed


def load_project_env(project_root: Path) -> None:
    env_path = project_root / ".env"

    if not env_path.exists():
        raise FileNotFoundError(f"Missing .env file: {env_path}")

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def build_commerce_ai_client(*, project_root: str | Path | None = None) -> GeminiCommerceAIClient:
    resolved_root = Path(project_root or Path.cwd()).resolve()
    load_project_env(resolved_root)

    model = os.getenv("GEMINI_MODEL", "").strip()

    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY is required in the project .env file.")

    return GeminiCommerceAIClient(model=model)
