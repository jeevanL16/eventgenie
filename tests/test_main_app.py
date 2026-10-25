"""End-to-end tests for the Streamlit intake form and plan rendering."""

from streamlit.testing.v1 import AppTest


def test_app_initial_render():
    at = AppTest.from_file("app/main.py")
    at.run()
    assert not at.exception
    # Check that main title and disclaimer are rendered
    assert len(at.title) == 0  # we used markdown for custom styling
    assert any("EventGenie" in m.value for m in at.markdown)
    assert any("Estimates Only" in m.value for m in at.markdown)


def test_app_demo_button_generates_and_renders_plan():
    at = AppTest.from_file("app/main.py")
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
    at = AppTest.from_file("app/main.py")
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
