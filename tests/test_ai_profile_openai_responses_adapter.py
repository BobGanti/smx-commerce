import pytest

from smx_commerce.ai import (
    CommerceAIClientError,
    OpenAIResponsesCommerceAIClient,
    build_commerce_ai_client_from_profile,
)


class FakeOpenAIUsage:
    input_tokens = 30
    output_tokens = 12
    total_tokens = 42


class FakeOpenAIResponse:
    output_text = "{\"summary\": \"Customer cannot access purchased course.\", \"needs_human_review\": true}"
    usage = FakeOpenAIUsage()


class FakeOpenAIResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeOpenAIResponse()


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeOpenAIResponses()


def test_build_commerce_ai_client_from_openai_profile_returns_responses_adapter():
    provider_client = FakeOpenAIClient()

    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": "openai",
            "model": "gpt-test",
            "api_key": "redacted",
            "client": provider_client,
        }
    )

    assert isinstance(ai_client, OpenAIResponsesCommerceAIClient)

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

    assert result.usage.provider == "openai"
    assert result.usage.model == "gpt-test"
    assert result.usage.input_tokens == 30
    assert result.usage.output_tokens == 12
    assert result.usage.total_tokens == 42

    call = provider_client.responses.calls[0]

    assert call["model"] == "gpt-test"
    assert "commerce_support_summary" in call["input"]
    assert "aoife@example.com" in call["input"]
    assert call["text"]["format"]["type"] == "json_object"


def test_openai_profile_requires_model():
    with pytest.raises(CommerceAIClientError, match="requires a model"):
        build_commerce_ai_client_from_profile(
            {
                "provider": "openai",
                "model": "",
                "client": FakeOpenAIClient(),
            }
        )


def test_openai_profile_requires_client():
    with pytest.raises(CommerceAIClientError, match="requires a client"):
        build_commerce_ai_client_from_profile(
            {
                "provider": "openai",
                "model": "gpt-test",
            }
        )


def test_openai_responses_adapter_rejects_invalid_json():
    class BadResponse:
        output_text = "not-json"

    class BadResponses:
        def create(self, **kwargs):
            return BadResponse()

    class BadClient:
        responses = BadResponses()

    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": "openai",
            "model": "gpt-test",
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
