from __future__ import annotations

import json
import re
from typing import Any

from smx_commerce.ai.contracts import CommerceAIClientError, CommerceAIResult, CommerceAIUsage


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

        response_text, usage = self._generate_text(prompt)
        return CommerceAIResult(
            data=_parse_json_object(response_text, agent_name=agent_name),
            usage=usage,
        )

    def _generate_text(self, prompt: str) -> tuple[str, CommerceAIUsage]:
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
            return text, _extract_google_usage(response, provider="google", model=self.model)

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) if content is not None else None
            for part in parts or []:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str) and part_text.strip():
                    return part_text, _extract_google_usage(response, provider="google", model=self.model)

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

        response_text, usage = self._generate_text(prompt)
        return CommerceAIResult(
            data=_parse_json_object(response_text, agent_name=agent_name),
            usage=usage,
        )

    def _generate_text(self, prompt: str) -> tuple[str, CommerceAIUsage]:
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
            return text, _extract_openai_usage(response, provider="openai", model=self.model)

        output = getattr(response, "output", None) or []
        for item in output:
            content = getattr(item, "content", None) or []
            for content_item in content:
                content_text = getattr(content_item, "text", None)
                if isinstance(content_text, str) and content_text.strip():
                    return content_text, _extract_openai_usage(response, provider="openai", model=self.model)

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

        response_text, usage = self._generate_text(prompt)
        return CommerceAIResult(
            data=_parse_json_object(response_text, agent_name=agent_name),
            usage=usage,
        )

    def _generate_text(self, prompt: str) -> tuple[str, CommerceAIUsage]:
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
                return block_text, _extract_anthropic_usage(response, provider="anthropic", model=self.model)

            if isinstance(block, dict):
                block_text = block.get("text")
                if isinstance(block_text, str) and block_text.strip():
                    return block_text, _extract_anthropic_usage(response, provider="anthropic", model=self.model)

        raise CommerceAIClientError("Anthropic AI response did not contain text.")






SUPPORT_ASSISTANT_AGENT_NAMES = frozenset(
    {
        "commerce_support_issue_classifier",
        "commerce_support_summary",
        "commerce_support_missing_information",
        "commerce_support_escalation_assessor",
        "commerce_support_priority_assessor",
    }
)


class CommerceAIRoutingClient:
    def __init__(
        self,
        *,
        main_client: Any,
        assistant_client: Any | None = None,
    ):
        if main_client is None:
            raise CommerceAIClientError("Commerce AI routing requires a main client.")

        self.main_client = main_client
        self.assistant_client = assistant_client

    def run_agent_task(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict[str, Any],
        context: dict[str, Any],
    ) -> CommerceAIResult:
        client = self._client_for_agent(agent_name)

        return client.run_agent_task(
            agent_name=agent_name,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            expected_schema=expected_schema,
            context=context,
        )

    def _client_for_agent(self, agent_name: str):
        if self.assistant_client is not None and agent_name in SUPPORT_ASSISTANT_AGENT_NAMES:
            return self.assistant_client

        return self.main_client


OPENAI_COMPATIBLE_CHAT_PROVIDERS = {
    "xai",
    "alibaba",
    "deepseek",
    "moonshotai",
}


class OpenAICompatibleChatCommerceAIClient:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        client: Any,
        max_tokens: int = 2048,
        json_response_format: bool = False,
    ):
        if not provider:
            raise CommerceAIClientError("OpenAI-compatible AI profile requires a provider.")
        if not model:
            raise CommerceAIClientError("OpenAI-compatible AI profile requires a model.")
        if client is None:
            raise CommerceAIClientError("OpenAI-compatible AI profile requires a client.")

        self.provider = provider
        self.model = model
        self.client = client
        self.max_tokens = max_tokens
        self.json_response_format = json_response_format

    def run_agent_task(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        expected_schema: dict[str, Any],
        context: dict[str, Any],
    ) -> CommerceAIResult:
        prompt = _build_agent_prompt(
            agent_name=agent_name,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            expected_schema=expected_schema,
            context=context,
        )

        response_text, usage = self._generate_text(prompt)
        return CommerceAIResult(
            data=_parse_json_object(response_text, agent_name=agent_name),
            usage=usage,
        )

    def _generate_text(self, prompt: str) -> tuple[str, CommerceAIUsage]:
        request_kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
        }

        if self.json_response_format:
            request_kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**request_kwargs)
        except TypeError:
            request_kwargs.pop("response_format", None)
            try:
                response = self.client.chat.completions.create(**request_kwargs)
            except TypeError:
                request_kwargs.pop("max_tokens", None)
                response = self.client.chat.completions.create(**request_kwargs)
        except Exception as exc:
            raise CommerceAIClientError(
                f"OpenAI-compatible Chat Completions request failed for provider {self.provider}: {exc}"
            ) from exc

        choices = getattr(response, "choices", None) or []
        for choice in choices:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None) if message is not None else None

            if isinstance(content, str) and content.strip():
                return content, _extract_openai_compatible_chat_usage(
                    response,
                    provider=self.provider,
                    model=self.model,
                )

            if isinstance(choice, dict):
                message = choice.get("message") or {}
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content, _extract_openai_compatible_chat_usage(
                        response,
                        provider=self.provider,
                        model=self.model,
                    )

        raise CommerceAIClientError(
            f"OpenAI-compatible Chat Completions response did not contain message content for provider {self.provider}."
        )


def _extract_google_usage(response: Any, *, provider: str, model: str) -> CommerceAIUsage:
    usage = getattr(response, "usage_metadata", None)
    input_tokens = _coerce_int(getattr(usage, "prompt_token_count", 0))
    output_tokens = _coerce_int(getattr(usage, "candidates_token_count", 0))
    total_tokens = _coerce_int(getattr(usage, "total_token_count", 0))
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens

    return CommerceAIUsage(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        raw={
            "prompt_token_count": input_tokens,
            "candidates_token_count": output_tokens,
            "total_token_count": total_tokens,
        },
    )


def _extract_openai_compatible_chat_usage(response: Any, *, provider: str, model: str) -> CommerceAIUsage:
    usage = getattr(response, "usage", None)

    input_tokens = _coerce_int(_get_usage_value(usage, "prompt_tokens"))
    if input_tokens <= 0:
        input_tokens = _coerce_int(_get_usage_value(usage, "input_tokens"))

    output_tokens = _coerce_int(_get_usage_value(usage, "completion_tokens"))
    if output_tokens <= 0:
        output_tokens = _coerce_int(_get_usage_value(usage, "output_tokens"))

    total_tokens = _coerce_int(_get_usage_value(usage, "total_tokens"))
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens

    return CommerceAIUsage(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        raw={
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
    )


def _extract_anthropic_usage(response: Any, *, provider: str, model: str) -> CommerceAIUsage:
    usage = getattr(response, "usage", None)
    input_tokens = _coerce_int(_get_usage_value(usage, "input_tokens"))
    output_tokens = _coerce_int(_get_usage_value(usage, "output_tokens"))
    total_tokens = input_tokens + output_tokens

    return CommerceAIUsage(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        raw={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
    )

def _extract_openai_usage(response: Any, *, provider: str, model: str) -> CommerceAIUsage:
    usage = getattr(response, "usage", None)
    input_tokens = _coerce_int(_get_usage_value(usage, "input_tokens"))
    output_tokens = _coerce_int(_get_usage_value(usage, "output_tokens"))
    total_tokens = _coerce_int(_get_usage_value(usage, "total_tokens"))
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens

    return CommerceAIUsage(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        raw={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
    )


def _get_usage_value(usage: Any, key: str) -> Any:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return usage.get(key, 0)
    return getattr(usage, key, 0)


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0




def _is_labeled_ai_profile(profile: dict[str, Any]) -> bool:
    return "main" in profile or "assistant" in profile


def build_commerce_ai_client_from_profile(profile: dict[str, Any] | None):
    if not profile:
        return None

    if _is_labeled_ai_profile(profile):
        main_profile = profile.get("main")
        if not main_profile:
            raise CommerceAIClientError("Labeled commerce AI profile requires a main profile.")

        main_client = build_commerce_ai_client_from_profile(main_profile)
        if main_client is None:
            raise CommerceAIClientError("Labeled commerce AI profile main profile did not create a client.")

        assistant_profile = profile.get("assistant")
        assistant_client = (
            build_commerce_ai_client_from_profile(assistant_profile)
            if assistant_profile
            else None
        )

        return CommerceAIRoutingClient(
            main_client=main_client,
            assistant_client=assistant_client,
        )

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

    if provider in OPENAI_COMPATIBLE_CHAT_PROVIDERS:
        return OpenAICompatibleChatCommerceAIClient(
            provider=provider,
            model=str(profile.get("model", "")).strip(),
            client=profile.get("client"),
            max_tokens=_coerce_int(profile.get("max_tokens", 2048)) or 2048,
            json_response_format=bool(profile.get("json_response_format", False)),
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
