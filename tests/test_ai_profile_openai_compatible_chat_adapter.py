import pytest

from smx_commerce.ai import (
    CommerceAIClientError,
    OpenAICompatibleChatCommerceAIClient,
    build_commerce_ai_client_from_profile,
)


OPENAI_COMPATIBLE_PROVIDERS = [
    "xai",
    "alibaba",
    "deepseek",
    "moonshotai",
]


class FakeChatUsage:
    prompt_tokens = 40
    completion_tokens = 15
    total_tokens = 55


class FakeChatMessage:
    content = '{"summary": "Customer needs help with paid course access.", "needs_human_review": true}'


class FakeChatChoice:
    message = FakeChatMessage()


class FakeChatResponse:
    choices = [FakeChatChoice()]
    usage = FakeChatUsage()


class FakeChatCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeChatResponse()


class FakeChat:
    def __init__(self):
        self.completions = FakeChatCompletions()


class FakeOpenAICompatibleClient:
    def __init__(self):
        self.chat = FakeChat()


@pytest.mark.parametrize("provider", OPENAI_COMPATIBLE_PROVIDERS)
def test_build_commerce_ai_client_from_openai_compatible_profile(provider):
    provider_client = FakeOpenAICompatibleClient()

    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": provider,
            "model": "compatible-test-model",
            "api_key": "redacted",
            "client": provider_client,
            "max_tokens": 777,
        }
    )

    assert isinstance(ai_client, OpenAICompatibleChatCommerceAIClient)

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
        "summary": "Customer needs help with paid course access.",
        "needs_human_review": True,
    }

    assert result.usage.provider == provider
    assert result.usage.model == "compatible-test-model"
    assert result.usage.input_tokens == 40
    assert result.usage.output_tokens == 15
    assert result.usage.total_tokens == 55

    call = provider_client.chat.completions.calls[0]

    assert call["model"] == "compatible-test-model"
    assert call["max_tokens"] == 777
    assert call["messages"][0]["role"] == "user"
    assert "commerce_support_summary" in call["messages"][0]["content"]
    assert "aoife@example.com" in call["messages"][0]["content"]


def test_openai_compatible_profile_can_request_json_response_format():
    provider_client = FakeOpenAICompatibleClient()

    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": "deepseek",
            "model": "deepseek-test",
            "client": provider_client,
            "json_response_format": True,
        }
    )

    ai_client.run_agent_task(
        agent_name="commerce_support_summary",
        system_prompt="Summarize.",
        task_prompt="Return JSON.",
        expected_schema={"type": "object"},
        context={},
    )

    call = provider_client.chat.completions.calls[0]

    assert call["response_format"] == {"type": "json_object"}


def test_openai_compatible_profile_requires_model():
    with pytest.raises(CommerceAIClientError, match="requires a model"):
        build_commerce_ai_client_from_profile(
            {
                "provider": "alibaba",
                "model": "",
                "client": FakeOpenAICompatibleClient(),
            }
        )


def test_openai_compatible_profile_requires_client():
    with pytest.raises(CommerceAIClientError, match="requires a client"):
        build_commerce_ai_client_from_profile(
            {
                "provider": "xai",
                "model": "grok-test",
            }
        )


def test_model_family_names_are_not_provider_names():
    for provider in ["grok", "qwen", "kimi"]:
        with pytest.raises(CommerceAIClientError, match="Unsupported commerce AI provider"):
            build_commerce_ai_client_from_profile(
                {
                    "provider": provider,
                    "model": "model-family-test",
                    "client": FakeOpenAICompatibleClient(),
                }
            )


def test_openai_compatible_chat_adapter_rejects_invalid_json():
    class BadMessage:
        content = "not-json"

    class BadChoice:
        message = BadMessage()

    class BadResponse:
        choices = [BadChoice()]

    class BadCompletions:
        def create(self, **kwargs):
            return BadResponse()

    class BadChat:
        completions = BadCompletions()

    class BadClient:
        chat = BadChat()

    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": "moonshotai",
            "model": "kimi-test",
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
