"""Accessibility and usability tests for EventGenie (Task S-07).

Tests form label help attributes, non-color-only indicators,
and semantic text representations.
"""

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
        notices=["Accessibility test mock"],
        provider="mock",
    )


class TestAccessibilityAndUsability:
    """Tests for WCAG compliance, input help annotations, and text alternatives."""

    def test_form_inputs_have_help_annotations(self):
        """All primary intake inputs must feature explanatory help text for screen readers."""
        at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
        at.run(timeout=20)
        assert not at.exception

        # Check selectboxes have help text
        for sb in at.selectbox:
            assert sb.help is not None and len(sb.help) > 0, f"Selectbox {sb.key} missing help text"

        # Check number inputs have help text
        for ni in at.number_input:
            assert ni.help is not None and len(ni.help) > 0, (
                f"NumberInput {ni.key} missing help text"
            )

        # Check text inputs have help text
        for ti in at.text_input:
            assert ti.help is not None and len(ti.help) > 0, f"TextInput {ti.key} missing help text"

        # Check text area has help text
        for ta in at.text_area:
            assert ta.help is not None and len(ta.help) > 0, f"TextArea {ta.key} missing help text"

    def test_plan_presentation_provides_tabular_text_alternatives(self):
        """Data must be presented in structured text tables, avoiding charts that lack text equivalents."""
        with patch("app.pipeline.generate_plan_v0", side_effect=_mock_generate):
            at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
            at.run(timeout=20)
            assert not at.exception

            # Click sample wedding demo
            wedding_btn = next((b for b in at.button if "Sample Wedding" in b.label), None)
            assert wedding_btn is not None
            wedding_btn.click().run(timeout=20)
            assert not at.exception

            # Verify that dataframes are rendered for both budget and timeline
            assert len(at.dataframe) >= 2

            # Verify that status indicators include text words (e.g. "TODO", "DOING", "DONE")
            timeline_df = at.dataframe[1].value
            assert "Status" in timeline_df.columns
            assert all(isinstance(s, str) and len(s) > 0 for s in timeline_df["Status"])
