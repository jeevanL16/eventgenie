"""Tests for multilingual plan translation and structural verification (Task S-08).

Tests structural integrity checking, Indic script ratio verification,
deterministic fallback translations, and LLM translation failover.
"""

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.pipeline import fallback_plan
from app.schemas import EventPlan, PlanInputs
from app.tools.translate import (
    INDIC_LANG_NAMES,
    PlanTranslationPayload,
    translate_plan,
    verify_script_ratio,
    verify_structural_integrity,
)


@pytest.fixture
def sample_english_plan() -> EventPlan:
    inputs = PlanInputs(
        event_type="wedding",
        event_date=date(2027, 11, 20),
        guests=150,
        total_budget=800000.0,
        city="Bengaluru",
        lang="en",
    )
    return fallback_plan(inputs)


class TestIndicScriptAndStructuralCheck:
    """Tests for Unicode script range analysis and structural invariance."""

    @pytest.mark.parametrize(
        "text, lang, expected",
        [
            (["ಸ್ಥಳ ಮತ್ತು ಕಲ್ಯಾಣ ಮಂಟಪ ಬಾಡಿಗೆ", "ಊಟೋಪಹಾರ ಸೇವೆ"], "kn", True),
            (["వేదిక మరియు కళ్యాణ మండపం అద్దె", "భోజన సేవలు"], "te", True),
            (["மண்டபம் மற்றும் இட வாடகை", "உணவு சேவை"], "ta", True),
            (["स्थल और मंडप किराया", "खानपान सेवा"], "hi", True),
            (["स्थळ व मंगल कार्यालय भाडे", "भोजन व्यवस्था"], "mr", True),
            (["Pure English Text without Indic Script"], "kn", False),
            (["Venue & Catering with minimal words"], "hi", False),
        ],
    )
    def test_verify_script_ratio(self, text: list[str], lang: str, expected: bool):
        assert verify_script_ratio(text, lang, min_ratio=0.40) is expected

    def test_structural_integrity_preservation(self, sample_english_plan):
        # A plan with same amounts, dates, and keys is valid
        assert verify_structural_integrity(sample_english_plan, sample_english_plan) is True

        # Modified budget amount violates integrity
        tampered_plan = sample_english_plan.model_copy(deep=True)
        tampered_plan.budget[0].amount += 500.0
        assert verify_structural_integrity(sample_english_plan, tampered_plan) is False

        # Altered task date violates integrity
        tampered_task_plan = sample_english_plan.model_copy(deep=True)
        tampered_task_plan.timeline[0].due_date += date.resolution
        assert verify_structural_integrity(sample_english_plan, tampered_task_plan) is False


class TestDeterministicFallbackTranslations:
    """Tests for offline deterministic translation for all 5 Indic languages."""

    @pytest.mark.parametrize("lang", ["hi", "kn", "te", "ta", "mr"])
    def test_fallback_plan_translates_indic_languages(self, lang):
        inputs = PlanInputs(
            event_type="wedding",
            event_date=date(2027, 10, 15),
            guests=100,
            total_budget=500000.0,
            lang=lang,
        )
        plan = fallback_plan(inputs)
        assert plan.lang == lang

        # Verify budget sum remains exact in Indic language
        assert round(sum(b.amount for b in plan.budget), 2) == 500000.0

        # Verify localized strings contain target script
        labels = [b.label for b in plan.budget]
        assert verify_script_ratio(labels, lang, min_ratio=0.30) is True


class TestLLMTranslationFlow:
    """Tests for LLM-based translation and structural check repair loop."""

    @pytest.mark.parametrize("lang", ["kn", "te", "ta", "hi", "mr"])
    def test_translate_plan_success_with_mock_llm(self, sample_english_plan, lang):
        lang_name = INDIC_LANG_NAMES[lang]
        mock_llm = MagicMock()

        sample_script_words = {
            "kn": "ಸ್ಥಳ ಯೋಜನೆ ಹಂತ",
            "te": "వేదిక ప్రణాళిక దశ",
            "ta": "மண்டபம் திட்டமிடல்",
            "hi": "स्थल योजना चरण",
            "mr": "स्थळ नियोजन टप्पा",
        }
        word = sample_script_words[lang]

        mock_payload = PlanTranslationPayload(
            budget=[
                {"label": f"{word} {idx}", "note": f"{word} {idx}"}
                for idx, b in enumerate(sample_english_plan.budget, 1)
            ],
            timeline=[
                {"title": f"{word} {idx}", "phase": f"{word} {idx}"}
                for idx, t in enumerate(sample_english_plan.timeline, 1)
            ],
            vendors=[
                {
                    "label": f"{word} {idx}",
                    "questions_to_ask": [f"{word} Q{idx}"],
                    "documents_to_request": [f"{word} Doc{idx}"],
                    "red_flags": [f"{word} Flag{idx}"],
                }
                for idx, v in enumerate(sample_english_plan.vendors, 1)
            ],
            themes=[f"{word} 1"],
            menu=[f"{word} 1"],
            activities=[f"{word} 1"],
            decor=[f"{word} 1"],
            extras=[f"{word} 1"],
            assumptions=[f"{word} 1"],
        )
        mock_llm.generate_json.return_value = mock_payload

        translated, notices = translate_plan(sample_english_plan, target_lang=lang, llm=mock_llm)

        assert translated.lang == lang
        assert verify_structural_integrity(sample_english_plan, translated) is True
        assert any(lang_name in n for n in notices)

    def test_translate_plan_fails_structural_check_falls_back_to_english(self, sample_english_plan):
        mock_llm = MagicMock()
        # Mock returns truncated budget list (violates structural check)
        bad_payload = PlanTranslationPayload(
            budget=[],
            timeline=[],
            vendors=[],
            themes=[],
            menu=[],
            activities=[],
            decor=[],
            extras=[],
            assumptions=[],
        )
        mock_llm.generate_json.return_value = bad_payload

        fallback_res, notices = translate_plan(sample_english_plan, target_lang="kn", llm=mock_llm)

        # Must fall back to English with a polite notice
        assert fallback_res.lang == "en"
        assert len(fallback_res.budget) == len(sample_english_plan.budget)
        assert any("temporarily busy" in n for n in notices)
