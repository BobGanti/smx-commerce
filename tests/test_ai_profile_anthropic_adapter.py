import pytest

from smx_commerce.ai import (
    AnthropicCommerceAIClient,
    CommerceAIClientError,
    build_commerce_ai_client_from_profile,
)


class FakeAnthropicTextBlock:
    text = '{"summary": "Customer cannot access purchased course.", "needs_human_review": true}'


class FakeAnthropicResponse:
    content = [FakeAnthropicTextBlock()]


class FakeAnthropicMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeAnthropicResponse()


class FakeAnthropicClient:
    def __init__(self):
        self.messages = FakeAnthropicMessages()


def test_build_commerce_ai_client_from_anthropic_profile_returns_adapter():
    provider_client = FakeAnthropicClient()

    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": "anthropic",
            "model": "claude-test",
            "api_key": "redacted",
            "client": provider_client,
            "max_tokens": 512,
        }
    )

    assert isinstance(ai_client, AnthropicCommerceAIClient)

    result = ai_client.run_agent_task(
        agent_name="commerce_support_summary",
        system_prompt="Summarize the support issue.",
        task_prompt="Return the summary.",
        expected_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "needs_human_review": {"type": "boolean"},
            },
        },
        context={
            "customer_email": "aoife@example.com",
            "customer_message": "I paid but cannot access the course.",
        },
    )

    assert result == {
        "summary": "Customer cannot access purchased course.",
        "needs_human_review": True,
    }

    call = provider_client.messages.calls[0]

    assert call["model"] == "claude-test"
    assert call["max_tokens"] == 512
    assert call["messages"][0]["role"] == "user"
    assert "commerce_support_summary" in call["messages"][0]["content"]
    assert "aoife@example.com" in call["messages"][0]["content"]


def test_anthropic_adapter_accepts_dict_content_blocks():
    class DictBlockResponse:
        content = [
            {
                "type": "text",
                "text": '{"summary": "Dict block parsed.", "needs_human_review": false}',
            }
        ]

    class DictBlockMessages:
        def create(self, **kwargs):
            return DictBlockResponse()

    class DictBlockClient:
        messages = DictBlockMessages()

    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": "anthropic",
            "model": "claude-test",
            "client": DictBlockClient(),
        }
    )

    result = ai_client.run_agent_task(
        agent_name="commerce_support_summary",
        system_prompt="Summarize.",
        task_prompt="Return JSON.",
        expected_schema={"type": "object"},
        context={},
    )

    assert result == {
        "summary": "Dict block parsed.",
        "needs_human_review": False,
    }


def test_anthropic_profile_requires_model():
    with pytest.raises(CommerceAIClientError, match="requires a model"):
        build_commerce_ai_client_from_profile(
            {
                "provider": "anthropic",
                "model": "",
                "client": FakeAnthropicClient(),
            }
        )


def test_anthropic_profile_requires_client():
    with pytest.raises(CommerceAIClientError, match="requires a client"):
        build_commerce_ai_client_from_profile(
            {
                "provider": "anthropic",
                "model": "claude-test",
            }
        )


def test_anthropic_adapter_rejects_invalid_json():
    class BadTextBlock:
        text = "not-json"

    class BadResponse:
        content = [BadTextBlock()]

    class BadMessages:
        def create(self, **kwargs):
            return BadResponse()

    class BadClient:
        messages = BadMessages()

    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": "anthropic",
            "model": "claude-test",
            "client": BadClient(),
        }
    )

    with pytest.raises(CommerceAIClientError, match="returned invalid JSON"):
        ai_client.run_agent_task(
            agent_name="commerce_support_summary",
            system_prompt="Summarize.",
            task_prompt="Return JSON.",
            expected_schema={"type": "object"},
            context={},
        )
