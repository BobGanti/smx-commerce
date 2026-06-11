from smx_commerce.ai import GeminiEnvCommerceAIClient, load_gemini_env_client


class FakeGeminiTransport:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return '{"issue_type": "payment_problem", "confidence": 0.91}'


def test_load_gemini_env_client_returns_none_when_env_is_missing(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    client = load_gemini_env_client(
        env_file=env_file,
        environ={},
        transport=FakeGeminiTransport(),
    )

    assert client is None


def test_gemini_env_client_loads_from_env_file_and_runs_agent_task(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_MODEL=gemini-test-model\nGEMINI_API_KEY=test-secret-key\n",
        encoding="utf-8",
    )

    transport = FakeGeminiTransport()

    client = load_gemini_env_client(
        env_file=env_file,
        environ={},
        transport=transport,
    )

    assert client is not None

    result = client.run_agent_task(
        agent_name="triage",
        system_prompt="You classify commerce support requests.",
        task_prompt="Classify this support request.",
        expected_schema={
            "type": "object",
            "required": ["issue_type", "confidence"],
            "properties": {
                "issue_type": {"type": "string"},
                "confidence": {"type": "number"},
            },
        },
        context={
            "customer_message": "I paid but did not receive access.",
        },
    )

    assert result == {
        "issue_type": "payment_problem",
        "confidence": 0.91,
    }

    assert len(transport.calls) == 1
    assert transport.calls[0]["model"] == "gemini-test-model"
    assert transport.calls[0]["api_key"] == "test-secret-key"
    assert "GEMINI_API_KEY" not in transport.calls[0]["task_prompt"]


def test_gemini_env_client_accepts_plain_json_from_transport():
    transport = FakeGeminiTransport()

    client = GeminiEnvCommerceAIClient(
        api_key="test-secret-key",
        model="gemini-test-model",
        transport=transport,
    )

    result = client.run_agent_task(
        agent_name="triage",
        system_prompt="You classify commerce support requests.",
        task_prompt="Classify this support request.",
        expected_schema={"type": "object"},
        context={"message": "Refund please."},
    )

    assert result["issue_type"] == "payment_problem"
