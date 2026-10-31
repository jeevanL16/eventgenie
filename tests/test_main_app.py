"""End-to-end tests for the Streamlit intake form and plan rendering."""

from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.pipeline import GenerationResult, fallback_plan
from app.schemas import PlanInputs

MAIN_APP_PATH = str(Path(__file__).resolve().parent.parent / "app" / "main.py")


def _mock_generate(inputs, *args, **kwargs):
    if isinstance(inputs, dict):
        inputs = PlanInputs.model_validate(inputs)
    plan = fallback_plan(inputs)
    return GenerationResult(
        plan=plan,
        is_fallback=True,
        notices=["Deterministic mock for testing"],
        provider="mock",
    )


def test_app_initial_render():
    at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
    at.run(timeout=20)
    assert not at.exception
    # Check that main title and disclaimer are rendered
    assert len(at.title) == 0  # we used markdown for custom styling
    assert any("EventGenie" in m.value for m in at.markdown)
    assert any("Estimates Only" in m.value for m in at.markdown)


def test_app_demo_button_generates_and_renders_plan():
    with patch("app.pipeline.generate_plan_v0", side_effect=_mock_generate):
        at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
        at.run(timeout=20)
        assert not at.exception

        # Find the "💍 Sample Wedding" button
        wedding_btn = next((b for b in at.button if "Sample Wedding" in b.label), None)
        assert wedding_btn is not None
        wedding_btn.click().run(timeout=20)

        assert not at.exception
        # Check that plan summary is rendered
        assert at.session_state["current_result"] is not None
        plan = at.session_state["current_result"].plan
        assert plan.event_type == "wedding"
        assert plan.total_budget == 1200000.0

        # Verify tabs exist
        assert len(at.tabs) == 4

        # Verify budget and timeline dataframes are rendered
        assert len(at.dataframe) >= 2


def test_app_form_submission_generates_plan():
    with patch("app.pipeline.generate_plan_v0", side_effect=_mock_generate):
        at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
        at.run(timeout=20)
        assert not at.exception

        # Submit form
        submit_btn = next((b for b in at.button if "Generate Event Plan" in b.label), None)
        assert submit_btn is not None
        submit_btn.click().run(timeout=20)

        assert not at.exception
        assert at.session_state["current_result"] is not None
        plan = at.session_state["current_result"].plan
        assert plan.event_type in ("wedding", "birthday", "community")
        assert plan.total_budget > 0
        assert len(plan.budget) > 0
        assert len(plan.timeline) > 0


def test_app_sidebar_byok_and_provider_badge():
    def _mock_llm_generate(inputs, llm=None):
        if isinstance(inputs, dict):
            inputs = PlanInputs.model_validate(inputs)
        plan = fallback_plan(inputs)
        return GenerationResult(
            plan=plan,
            is_fallback=False,
            notices=[],
            provider="groq",
        )

    with patch("app.pipeline.generate_plan_v0", side_effect=_mock_llm_generate):
        at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
        at.run(timeout=20)
        assert not at.exception

        # Verify sidebar BYOK inputs exist
        sidebar_keys = [w.key for w in at.sidebar.text_input]
        assert "byok_gemini_key" in sidebar_keys
        assert "byok_groq_key" in sidebar_keys

        # Click demo button and verify active provider badge
        wedding_btn = next((b for b in at.button if "Sample Wedding" in b.label), None)
        assert wedding_btn is not None
        wedding_btn.click().run(timeout=20)

        assert not at.exception
        # Verify provider badge in rendered markdown
        assert any("Served by: GROQ" in m.value for m in at.markdown)


def test_app_simulated_429_shows_clean_message_without_raw_json():
    from app.llm.base import LLMRateLimitError

    raw_dump = "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Quota exceeded', 'details': []}}"

    def _mock_429(inputs, *args, **kwargs):
        if isinstance(inputs, dict):
            inputs = PlanInputs.model_validate(inputs)
        plan = fallback_plan(inputs)
        # Use our production sanitize_error_message
        from app.pipeline import sanitize_error_message

        friendly = sanitize_error_message(LLMRateLimitError(raw_dump))
        return GenerationResult(
            plan=plan,
            is_fallback=True,
            notices=[f"NOTICE: {friendly}"],
            provider="fallback",
        )

    with patch("app.pipeline.generate_plan_v0", side_effect=_mock_429):
        at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
        at.run(timeout=20)

        # Trigger plan generation via sample button
        wedding_btn = next((b for b in at.button if "Sample Wedding" in b.label), None)
        assert wedding_btn is not None
        wedding_btn.click().run(timeout=20)

        assert not at.exception
        # Verify friendly message is shown in warning
        assert any("AI service is busy" in w.value for w in at.warning)
        # Verify that no warning or caption contains raw JSON dumps
        all_text = " ".join([w.value for w in at.warning] + [c.value for c in at.caption])
        assert "RESOURCE_EXHAUSTED" not in all_text
        assert "{'error'" not in all_text
        assert "googleapis.com" not in all_text
