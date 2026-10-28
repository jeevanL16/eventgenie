"""End-to-end tests for the Streamlit intake form and plan rendering."""

from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.pipeline import GenerationResult, fallback_plan
from app.schemas import PlanInputs

MAIN_APP_PATH = str(Path(__file__).resolve().parent.parent / "app" / "main.py")


def _mock_generate(inputs):
    if isinstance(inputs, dict):
        inputs = PlanInputs.model_validate(inputs)
    plan = fallback_plan(inputs)
    return GenerationResult(plan=plan, is_fallback=True, notices=["Deterministic mock for testing"])


def test_app_initial_render():
    at = AppTest.from_file(MAIN_APP_PATH)
    at.run()
    assert not at.exception
    # Check that main title and disclaimer are rendered
    assert len(at.title) == 0  # we used markdown for custom styling
    assert any("EventGenie" in m.value for m in at.markdown)
    assert any("Estimates Only" in m.value for m in at.markdown)


def test_app_demo_button_generates_and_renders_plan():
    with patch("app.pipeline.generate_plan_v0", side_effect=_mock_generate):
        at = AppTest.from_file(MAIN_APP_PATH)
        at.run()
        assert not at.exception

        # Find the "💍 Sample Wedding" button
        wedding_btn = next((b for b in at.button if "Sample Wedding" in b.label), None)
        assert wedding_btn is not None
        wedding_btn.click().run()

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
        at = AppTest.from_file(MAIN_APP_PATH)
        at.run()
        assert not at.exception

        # Submit form
        submit_btn = next((b for b in at.button if "Generate Event Plan" in b.label), None)
        assert submit_btn is not None
        submit_btn.click().run()

        assert not at.exception
        assert at.session_state["current_result"] is not None
        plan = at.session_state["current_result"].plan
        assert plan.event_type in ("wedding", "birthday", "community")
        assert plan.total_budget > 0
        assert len(plan.budget) > 0
        assert len(plan.timeline) > 0
