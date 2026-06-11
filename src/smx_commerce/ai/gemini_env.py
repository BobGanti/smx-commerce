from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from smx_commerce.ai.contracts import CommerceAIClientError


class GeminiHTTPTransport:
    def generate_content(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        model_path = quote(model, safe="")
        url = f"{base_url.rstrip('/')}/models/{model_path}:generateContent"

        user_prompt = (
            f"{task_prompt}\n\n"
            "Return only one valid JSON object matching this schema.\n"
            f"Expected schema:\n{json.dumps(expected_schema, ensure_ascii=False, indent=2)}\n\n"
            f"Context:\n{json.dumps(context, ensure_ascii=False, indent=2, default=str)}"
        )

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
            },
        }

        body = json.dumps(payload).encode("utf-8")

        req = request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
        )

        try:
            with request.urlopen(req, timeout=60) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise CommerceAIClientError(f"Gemini request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise CommerceAIClientError("Gemini request failed before receiving a response") from exc
        except json.JSONDecodeError as exc:
            raise CommerceAIClientError("Gemini returned invalid JSON response envelope") from exc

        return _extract_gemini_text(response_payload)


@dataclass
class GeminiEnvCommerceAIClient:
    api_key: str
    model: str
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    transport: Any | None = None

    def __post_init__(self) -> None:
        self.api_key = (self.api_key or "").strip()
        self.model = (self.model or "").strip()
        self.base_url = (self.base_url or "").strip()

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiEnvCommerceAIClient")

        if not self.model:
            raise ValueError("GEMINI_MODEL is required for GeminiEnvCommerceAIClient")

        if self.transport is None:
            self.transport = GeminiHTTPTransport()

    def run_agent_task(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        agent_name = _required_text(agent_name, "agent_name")
        system_prompt = _required_text(system_prompt, "system_prompt")
        task_prompt = _required_text(task_prompt, "task_prompt")

        if not isinstance(expected_schema, dict) or not expected_schema:
            raise ValueError("expected_schema must be a non-empty dict")

        if not isinstance(context, dict):
            raise ValueError("context must be a dict")

        response_text = self.transport.generate_content(
            api_key=self.api_key,
            model=self.model,
            base_url=self.base_url,
            system_prompt=f"{system_prompt}\n\nAgent name: {agent_name}",
            task_prompt=task_prompt,
            expected_schema=expected_schema,
            context=context,
        )

        return _parse_json_object(response_text)


def load_gemini_env_client(
    *,
    env_file: str | Path | None = ".env",
    environ: dict[str, str] | None = None,
    transport: Any | None = None,
) -> GeminiEnvCommerceAIClient | None:
    values: dict[str, str] = {}

    if env_file is not None:
        values.update(_read_env_file(Path(env_file)))

    if environ is None:
        values.update(os.environ)
    else:
        values.update(environ)

    api_key = values.get("GEMINI_API_KEY", "").strip()
    model = values.get("GEMINI_MODEL", "").strip()
    base_url = values.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip()

    if not api_key or not model:
        return None

    return GeminiEnvCommerceAIClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        transport=transport,
    )


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    values: dict[str, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            values[key] = value

    return values


def _extract_gemini_text(response_payload: dict[str, Any]) -> str:
    try:
        candidates = response_payload["candidates"]
        first_candidate = candidates[0]
        parts = first_candidate["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise CommerceAIClientError("Gemini response envelope did not contain text content") from exc

    text_parts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ]

    text = "\n".join(text_parts).strip()

    if not text:
        raise CommerceAIClientError("Gemini response text was empty")

    return text


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()

    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise CommerceAIClientError("AI client returned text that was not valid JSON") from exc

    if not isinstance(value, dict):
        raise CommerceAIClientError("AI client must return one JSON object")

    return value


def _required_text(value: str, field_name: str) -> str:
    cleaned = (value or "").strip()

    if not cleaned:
        raise ValueError(f"{field_name} is required")

    return cleaned
