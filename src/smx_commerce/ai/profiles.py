from __future__ import annotations

import json
import re
from typing import Any

from smx_commerce.ai.contracts import CommerceAIClientError


class GoogleCommerceAIClient:
    def __init__(
        self,
        *,
        model: str,
        client: Any,
    ):
        if not model:
            raise CommerceAIClientError("Google AI profile requires a model.")
        if client is None:
            raise CommerceAIClientError("Google AI profile requires a client.")

        self.model = model
        self.client = client

    def run_agent_task(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = _build_agent_prompt(
            agent_name=agent_name,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            expected_schema=expected_schema,
            context=context,
        )

        response_text = self._generate_text(prompt)
        return _parse_json_object(response_text, agent_name=agent_name)

    def _generate_text(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                },
            )
        except TypeError:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
        except Exception as exc:
            raise CommerceAIClientError(f"Google AI request failed: {exc}") from exc

        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) if content is not None else None
            for part in parts or []:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str) and part_text.strip():
                    return part_text

        raise CommerceAIClientError("Google AI response did not contain text.")


class OpenAIResponsesCommerceAIClient:
    def __init__(
        self,
        *,
        model: str,
        client: Any,
    ):
        if not model:
            raise CommerceAIClientError("OpenAI AI profile requires a model.")
        if client is None:
            raise CommerceAIClientError("OpenAI AI profile requires a client.")

        self.model = model
        self.client = client

    def run_agent_task(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = _build_agent_prompt(
            agent_name=agent_name,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            expected_schema=expected_schema,
            context=context,
        )

        response_text = self._generate_text(prompt)
        return _parse_json_object(response_text, agent_name=agent_name)

    def _generate_text(self, prompt: str) -> str:
        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                text={
                    "format": {
                        "type": "json_object",
                    },
                },
            )
        except TypeError:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
            )
        except Exception as exc:
            raise CommerceAIClientError(f"OpenAI Responses API request failed: {exc}") from exc

        text = getattr(response, "output_text", None)
        if isinstance(text, str) and text.strip():
            return text

        output = getattr(response, "output", None) or []
        for item in output:
            content = getattr(item, "content", None) or []
            for content_item in content:
                content_text = getattr(content_item, "text", None)
                if isinstance(content_text, str) and content_text.strip():
                    return content_text

        raise CommerceAIClientError("OpenAI Responses API response did not contain output text.")


class AnthropicCommerceAIClient:
    def __init__(
        self,
        *,
        model: str,
        client: Any,
        max_tokens: int = 2048,
    ):
        if not model:
            raise CommerceAIClientError("Anthropic AI profile requires a model.")
        if client is None:
            raise CommerceAIClientError("Anthropic AI profile requires a client.")

        self.model = model
        self.client = client
        self.max_tokens = max_tokens

    def run_agent_task(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = _build_agent_prompt(
            agent_name=agent_name,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            expected_schema=expected_schema,
            context=context,
        )

        response_text = self._generate_text(prompt)
        return _parse_json_object(response_text, agent_name=agent_name)

    def _generate_text(self, prompt: str) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise CommerceAIClientError(f"Anthropic AI request failed: {exc}") from exc

        content = getattr(response, "content", None) or []
        for block in content:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str) and block_text.strip():
                return block_text

            if isinstance(block, dict):
                block_text = block.get("text")
                if isinstance(block_text, str) and block_text.strip():
                    return block_text

        raise CommerceAIClientError("Anthropic AI response did not contain text.")

def build_commerce_ai_client_from_profile(profile: dict[str, Any] | None):
    if not profile:
        return None

    provider = str(profile.get("provider", "")).strip().lower()

    if provider == "google":
        return GoogleCommerceAIClient(
            model=str(profile.get("model", "")).strip(),
            client=profile.get("client"),
        )

    if provider == "openai":
        return OpenAIResponsesCommerceAIClient(
            model=str(profile.get("model", "")).strip(),
            client=profile.get("client"),
        )

    if provider == "anthropic":
        return AnthropicCommerceAIClient(
            model=str(profile.get("model", "")).strip(),
            client=profile.get("client"),
            max_tokens=int(profile.get("max_tokens", 2048)),
        )

    raise CommerceAIClientError(f"Unsupported commerce AI provider: {provider or '<missing>'}")


def _build_agent_prompt(
    *,
    agent_name: str,
    system_prompt: str,
    task_prompt: str,
    expected_schema: dict[str, Any],
    context: dict[str, Any],
) -> str:
    return "\n\n".join(
        [
            "You are running an internal smx-commerce AI agent task.",
            f"Agent name: {agent_name}",
            "System instructions:",
            system_prompt.strip(),
            "Task:",
            task_prompt.strip(),
            "Expected JSON schema:",
            json.dumps(expected_schema, ensure_ascii=False, sort_keys=True),
            "Context:",
            json.dumps(context, ensure_ascii=False, sort_keys=True, default=str),
            "Return only one valid JSON object. Do not wrap it in Markdown. Do not include commentary.",
        ]
    )


def _parse_json_object(text: str, *, agent_name: str) -> dict[str, Any]:
    cleaned = _strip_markdown_json_fence(text.strip())

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise CommerceAIClientError(
            f"Agent {agent_name} returned invalid JSON."
        ) from exc

    if not isinstance(parsed, dict):
        raise CommerceAIClientError(
            f"Agent {agent_name} returned JSON that was not an object."
        )

    return parsed


def _strip_markdown_json_fence(text: str) -> str:
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if match:
        return match.group(1).strip()

    return text
