from smx_commerce.smxcp import _render_setup_file


def test_smxcp_setup_file_passes_host_built_ai_profile():
    content = _render_setup_file()

    assert "def setup_commerce(app, *, init_schema: bool = True, ai_profile=None):" in content
    assert "ai_profile=ai_profile" in content


def test_smxcp_setup_file_does_not_build_provider_profile():
    content = _render_setup_file()

    assert "from google import genai" not in content
    assert "from dotenv import load_dotenv" not in content
    assert "GEMINI_API_KEY" not in content
    assert "GEMINI_MODEL" not in content
    assert "SMX_COMMERCE_AI_PROVIDER" not in content
    assert "_build_ai_profile" not in content
    assert "commerce_support_reply_planner" not in content
    assert "commerce_support_issue_classifier" not in content
    assert "run_agent_task" not in content
