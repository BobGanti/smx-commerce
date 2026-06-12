import pytest

from smx_commerce.ai import (
    CommerceAIClientError,
    GoogleCommerceAIClient,
    build_commerce_ai_client_from_profile,
)


class FakeGoogleResponse:
    text = '{"issue_type": "payment_problem", "confidence": 0.91}'


class FakeGoogleModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return FakeGoogleResponse()


class FakeGoogleClient:
    def __init__(self):
        self.models = FakeGoogleModels()


def test_build_commerce_ai_client_from_google_profile_returns_package_adapter():
    provider_client = FakeGoogleClient()

    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": "google",
            "model": "gemini-test",
            "api_key": "redacted",
            "client": provider_client,
        }
    )

    assert isinstance(ai_client, GoogleCommerceAIClient)

    result = ai_client.run_agent_task(
        agent_name="commerce_support_issue_classifier",
        system_prompt="Classify the support issue.",
        task_prompt="Return the issue type.",
        expected_schema={
            "type": "object",
            "properties": {
                "issue_type": {"type": "string"},
                "confidence": {"type": "number"},
            },
        },
        context={
            "customer_email": "aoife@example.com",
            "customer_message": "I paid but cannot access the course.",
        },
    )

    assert result == {
        "issue_type": "payment_problem",
        "confidence": 0.91,
    }

    call = provider_client.models.calls[0]

    assert call["model"] == "gemini-test"
    assert "commerce_support_issue_classifier" in call["contents"]
    assert "aoife@example.com" in call["contents"]
    assert call["config"]["response_mime_type"] == "application/json"


def test_build_commerce_ai_client_from_profile_returns_none_when_profile_missing():
    assert build_commerce_ai_client_from_profile(None) is None


def test_google_profile_requires_model():
    with pytest.raises(CommerceAIClientError, match="requires a model"):
        build_commerce_ai_client_from_profile(
            {
                "provider": "google",
                "model": "",
                "client": FakeGoogleClient(),
            }
        )


def test_google_profile_requires_client():
    with pytest.raises(CommerceAIClientError, match="requires a client"):
        build_commerce_ai_client_from_profile(
            {
                "provider": "google",
                "model": "gemini-test",
            }
        )


def test_unsupported_provider_is_rejected():
    with pytest.raises(CommerceAIClientError, match="Unsupported commerce AI provider"):
        build_commerce_ai_client_from_profile(
            {
                "provider": "not-real-provider",
                "model": "fake-test",
            }
        )


class FakeGoogleUsageMetadata:
    prompt_token_count = 12
    candidates_token_count = 8
    total_token_count = 20


class FakeGoogleUsageResponse:
    text = "{\"issue_type\": \"general_question\", \"confidence\": 0.9}"
    usage_metadata = FakeGoogleUsageMetadata()


class FakeGoogleUsageModels:
    def generate_content(self, **kwargs):
        return FakeGoogleUsageResponse()


class FakeGoogleUsageClient:
    models = FakeGoogleUsageModels()


def test_google_adapter_returns_usage_metadata():
    ai_client = build_commerce_ai_client_from_profile(
        {
            "provider": "google",
            "model": "gemini-test",
            "client": FakeGoogleUsageClient(),
        }
    )

    result = ai_client.run_agent_task(
        agent_name="commerce_support_issue_classifier",
        system_prompt="Classify.",
        task_prompt="Return JSON.",
        expected_schema={"type": "object"},
        context={},
    )

    assert result.get("issue_type") == "general_question"
    assert result.usage.provider == "google"
    assert result.usage.model == "gemini-test"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 8
    assert result.usage.total_tokens == 20

