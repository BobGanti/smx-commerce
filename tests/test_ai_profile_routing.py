import pytest

from smx_commerce.ai import (
    CommerceAIClientError,
    CommerceAIRoutingClient,
    GoogleCommerceAIClient,
    build_commerce_ai_client_from_profile,
)


class FakeGoogleUsage:
    prompt_token_count = 10
    candidates_token_count = 5
    total_token_count = 15


class FakeGoogleResponse:
    usage_metadata = FakeGoogleUsage()

    def __init__(self, route_name):
        self.text = f'{{"route": "{route_name}"}}'


class FakeGoogleModels:
    def __init__(self, route_name):
        self.route_name = route_name
        self.calls = []

    def generate_content(self, *, model, contents, config=None):
        self.calls.append(
            {
                "model": model,
                "contents": contents,
                "config": config,
            }
        )
        return FakeGoogleResponse(self.route_name)


class FakeGoogleClient:
    def __init__(self, route_name):
        self.models = FakeGoogleModels(route_name)


def _google_profile(route_name, model):
    return {
        "provider": "google",
        "model": model,
        "client": FakeGoogleClient(route_name),
    }


def _run_agent(ai_client, *, agent_name):
    return ai_client.run_agent_task(
        agent_name=agent_name,
        system_prompt="Follow the task.",
        task_prompt="Return JSON.",
        expected_schema={"type": "object"},
        context={"thread_public_id": "sup_test"},
    )


def test_labeled_ai_profile_routes_support_analysis_to_assistant_and_reply_to_main():
    ai_client = build_commerce_ai_client_from_profile(
        {
            "main": _google_profile("main", "main-model"),
            "assistant": _google_profile("assistant", "assistant-model"),
        }
    )

    assert isinstance(ai_client, CommerceAIRoutingClient)

    analysis_result = _run_agent(
        ai_client,
        agent_name="commerce_support_summary",
    )
    reply_result = _run_agent(
        ai_client,
        agent_name="commerce_support_reply_composer",
    )

    assert analysis_result == {"route": "assistant"}
    assert analysis_result.usage.model == "assistant-model"

    assert reply_result == {"route": "main"}
    assert reply_result.usage.model == "main-model"


def test_labeled_ai_profile_uses_main_when_assistant_is_missing():
    ai_client = build_commerce_ai_client_from_profile(
        {
            "main": _google_profile("main", "main-model"),
        }
    )

    result = _run_agent(
        ai_client,
        agent_name="commerce_support_summary",
    )

    assert isinstance(ai_client, CommerceAIRoutingClient)
    assert result == {"route": "main"}
    assert result.usage.model == "main-model"


def test_legacy_single_ai_profile_still_builds_single_client():
    ai_client = build_commerce_ai_client_from_profile(
        _google_profile("legacy", "legacy-model")
    )

    result = _run_agent(
        ai_client,
        agent_name="commerce_support_summary",
    )

    assert isinstance(ai_client, GoogleCommerceAIClient)
    assert result == {"route": "legacy"}
    assert result.usage.model == "legacy-model"


def test_labeled_ai_profile_requires_main_profile():
    with pytest.raises(CommerceAIClientError, match="requires a main profile"):
        build_commerce_ai_client_from_profile(
            {
                "assistant": _google_profile("assistant", "assistant-model"),
            }
        )
