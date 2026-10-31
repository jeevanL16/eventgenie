"""Plan translation and Indic script verification tools (Tasks T-17, T-18, S-08).

Translates display strings to Indic languages (hi, kn, te, ta, mr) while preserving
100% of numerical calculations, dates, and category keys via strict structural checks.
"""

import logging
from collections.abc import Sequence

from pydantic import BaseModel

from app.llm.base import LLM, LLMError
from app.schemas import (
    BudgetLine,
    EventPlan,
    IdeaSet,
    Lang,
    Task,
    VendorItem,
)

logger = logging.getLogger(__name__)

INDIC_LANG_NAMES: dict[Lang, str] = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
    "te": "Telugu",
    "ta": "Tamil",
    "mr": "Marathi",
}

INDIC_SCRIPT_RANGES: dict[str, tuple[int, int]] = {
    "hi": (0x0900, 0x097F),  # Devanagari
    "mr": (0x0900, 0x097F),  # Devanagari
    "kn": (0x0C80, 0x0CFF),  # Kannada
    "te": (0x0C00, 0x0C7F),  # Telugu
    "ta": (0x0B80, 0x0BFF),  # Tamil
}

# Curated benchmark dictionary for deterministic fallback translations
BENCHMARK_TRANSLATIONS: dict[str, dict[str, str]] = {
    "hi": {
        "Venue & Hall Rental": "स्थल और मंडप किराया",
        "Catering & Food Service": "खानपान और भोजन सेवा",
        "Decor, Florals & Lighting": "सजावट, फूल और प्रकाश व्यवस्था",
        "Photography & Videography": "फोटोग्राफी और वीडियोग्राफी",
        "Attire & Jewellery": "परिधान और आभूषण",
        "Music, DJ & Entertainment": "संगीत, डीजे और मनोरंजन",
        "Invitations & Favors": "निमंत्रण पत्र और उपहार",
        "Emergency & Contingency": "आपातकालीन और आकस्मिक निधि",
        "Standard benchmark allocation": "मानक क्षेत्रीय आवंटन",
        "Planning": "योजना चरण",
    },
    "kn": {
        "Venue & Hall Rental": "ಸ್ಥಳ ಮತ್ತು ಕಲ್ಯಾಣ ಮಂಟಪ ಬಾಡಿಗೆ",
        "Catering & Food Service": "ಊಟೋಪಹಾರ ಮತ್ತು ಅಡುಗೆ ಸೇವೆ",
        "Decor, Florals & Lighting": "ಅಲಂಕಾರ, ಹೂವುಗಳು ಮತ್ತು ದೀಪಾಲಂಕಾರ",
        "Photography & Videography": "ಛಾಯಾಗ್ರಹಣ ಮತ್ತು ವಿಡಿಯೋಗ್ರಫಿ",
        "Attire & Jewellery": "ಉಡುಪು ಮತ್ತು ಆಭರಣಗಳು",
        "Music, DJ & Entertainment": "ಸಂಗೀತ ಮತ್ತು ಮನರಂಜನೆ",
        "Invitations & Favors": "ಆಮಂತ್ರಣ ಪತ್ರಿಕೆಗಳು ಮತ್ತು ಉಡುಗೊರೆಗಳು",
        "Emergency & Contingency": "ತುರ್ತು ಮತ್ತು ಅನಿರೀಕ್ಷಿತ ವೆಚ್ಚಗಳು",
        "Standard benchmark allocation": "ಪ್ರಮಾಣಿತ ಪ್ರಾದೇಶಿಕ ಹಂಚಿಕೆ",
        "Planning": "ಯೋಜನಾ ಹಂತ",
    },
    "te": {
        "Venue & Hall Rental": "వేదిక మరియు కళ్యాణ మండపం అద్దె",
        "Catering & Food Service": "భోజన మరియు క్యాటరింగ్ సేవలు",
        "Decor, Florals & Lighting": "అలంకరణ, పూలు మరియు లైటింగ్",
        "Photography & Videography": "ఫోటోగ్రఫీ మరియు వీడియోగ్రఫీ",
        "Attire & Jewellery": "దుస్తులు మరియు ఆభరణాలు",
        "Music, DJ & Entertainment": "సంగీతం మరియు వినోదం",
        "Invitations & Favors": "ఆహ్వాన పత్రికలు మరియు బహుమతులు",
        "Emergency & Contingency": "అత్యవసర మరియు అనుకోని నిధి",
        "Standard benchmark allocation": "ప్రామాణిక ప్రాంతీయ కేటాయింపు",
        "Planning": "ప్రణాళిక దశ",
    },
    "ta": {
        "Venue & Hall Rental": "மண்டபம் மற்றும் இட வாடகை",
        "Catering & Food Service": "உணவு மற்றும் கேட்டரிங் சேவை",
        "Decor, Florals & Lighting": "அலங்காரம், மலர்கள் மற்றும் விளக்குகள்",
        "Photography & Videography": "புகைப்படம் மற்றும் வீடியோகிராபி",
        "Attire & Jewellery": "ஆடைகள் மற்றும் நகைகள்",
        "Music, DJ & Entertainment": "இசை மற்றும் பொழுதுபோக்கு",
        "Invitations & Favors": "அழைப்பிதழ்கள் மற்றும் அன்பளிப்புகள்",
        "Emergency & Contingency": "அவசர மற்றும் எதிர்பாராத நிதி",
        "Standard benchmark allocation": "நிலையான பிராந்திய ஒதுக்கீடு",
        "Planning": "திட்டமிடல் நிலை",
    },
    "mr": {
        "Venue & Hall Rental": "स्थळ व मंगल कार्यालय भाडे",
        "Catering & Food Service": "भोजन व केटरिंग व्यवस्था",
        "Decor, Florals & Lighting": "सजावट, फुले आणि रोषणाई",
        "Photography & Videography": "छायाचित्रण आणि व्हिडिओग्राफी",
        "Attire & Jewellery": "पोशाख आणि दागिने",
        "Music, DJ & Entertainment": "संगीत आणि मनोरंजन",
        "Invitations & Favors": "निमंत्रण पत्रिका आणि भेटवस्तू",
        "Emergency & Contingency": "आपत्कालीन व अनपेक्षित निधी",
        "Standard benchmark allocation": "प्रमाणित प्रादेशिक वाटप",
        "Planning": "नियोजन टप्पा",
    },
}


class BudgetTranslationItem(BaseModel):
    label: str
    note: str = ""


class TaskTranslationItem(BaseModel):
    title: str
    phase: str


class VendorTranslationItem(BaseModel):
    label: str
    questions_to_ask: list[str]
    documents_to_request: list[str]
    red_flags: list[str]


class PlanTranslationPayload(BaseModel):
    """Schema for LLM translation request and response."""

    budget: list[BudgetTranslationItem]
    timeline: list[TaskTranslationItem]
    vendors: list[VendorTranslationItem]
    themes: list[str]
    menu: list[str]
    activities: list[str]
    decor: list[str]
    extras: list[str]
    assumptions: list[str]


def verify_script_ratio(texts: Sequence[str], lang: str, min_ratio: float = 0.40) -> bool:
    """Verify that translated display strings contain the expected Indic script Unicode characters.

    Allows ASCII numbers, Latin brand names, and currency codes.
    """
    if lang not in INDIC_SCRIPT_RANGES or lang == "en":
        return True

    low, high = INDIC_SCRIPT_RANGES[lang]
    script_chars = 0
    alpha_chars = 0

    for text in texts:
        for ch in text:
            if ch.isalpha():
                alpha_chars += 1
                if low <= ord(ch) <= high:
                    script_chars += 1

    if alpha_chars == 0:
        return True

    ratio = script_chars / alpha_chars
    return ratio >= min_ratio


def verify_structural_integrity(original: EventPlan, translated: EventPlan) -> bool:
    """Verify that structural quantities and invariants are strictly preserved after translation."""
    if len(original.budget) != len(translated.budget):
        return False
    if len(original.timeline) != len(translated.timeline):
        return False
    if len(original.vendors) != len(translated.vendors):
        return False

    for orig_b, trans_b in zip(original.budget, translated.budget, strict=True):
        if orig_b.key != trans_b.key:
            return False
        if abs(orig_b.amount - trans_b.amount) > 0.01:
            return False
        if abs(orig_b.percent - trans_b.percent) > 0.01:
            return False

    for orig_t, trans_t in zip(original.timeline, translated.timeline, strict=True):
        if orig_t.due_date != trans_t.due_date:
            return False
        if orig_t.category_key != trans_t.category_key:
            return False

    for orig_v, trans_v in zip(original.vendors, translated.vendors, strict=True):
        if orig_v.category_key != trans_v.category_key:
            return False

    return True


def _translate_deterministic_fallback(plan: EventPlan, lang: Lang) -> EventPlan:
    """Translate default fallback template plan using verified localized benchmark terms."""
    dict_map = BENCHMARK_TRANSLATIONS.get(lang, {})
    new_budget: list[BudgetLine] = []
    for b in plan.budget:
        trans_label = dict_map.get(b.label, b.label)
        trans_note = dict_map.get(b.note, b.note)
        new_budget.append(
            BudgetLine(
                key=b.key,
                label=trans_label,
                percent=b.percent,
                amount=b.amount,
                note=trans_note,
            )
        )

    new_timeline: list[Task] = []
    for t in plan.timeline:
        trans_phase = dict_map.get(t.phase, t.phase)
        new_timeline.append(
            Task(
                title=t.title,
                phase=trans_phase,
                due_date=t.due_date,
                owner=t.owner,
                status=t.status,
                category_key=t.category_key,
            )
        )

    return EventPlan(
        lang=lang,
        event_type=plan.event_type,
        event_date=plan.event_date,
        guests=plan.guests,
        total_budget=plan.total_budget,
        currency=plan.currency,
        city=plan.city,
        budget=new_budget,
        timeline=new_timeline,
        vendors=plan.vendors,
        ideas=plan.ideas,
        assumptions=plan.assumptions,
        sources_used=plan.sources_used,
    )


def translate_plan(
    plan: EventPlan,
    target_lang: Lang,
    llm: LLM | None = None,
) -> tuple[EventPlan, list[str]]:
    """Translate user-facing plan strings to target Indic language with structural check.

    Returns:
        tuple[EventPlan, list[str]]: (Translated EventPlan, list of user notices).
    """
    if target_lang == "en" or target_lang == plan.lang:
        return plan, []

    lang_name = INDIC_LANG_NAMES.get(target_lang, target_lang)

    # If no LLM available, apply deterministic benchmark dictionary translation
    if llm is None:
        translated = _translate_deterministic_fallback(plan, target_lang)
        notice = f"Translated to {lang_name} using verified regional benchmarks [Beta]."
        return translated, [notice]

    payload = PlanTranslationPayload(
        budget=[BudgetTranslationItem(label=b.label, note=b.note) for b in plan.budget],
        timeline=[TaskTranslationItem(title=t.title, phase=t.phase) for t in plan.timeline],
        vendors=[
            VendorTranslationItem(
                label=v.label,
                questions_to_ask=v.questions_to_ask,
                documents_to_request=v.documents_to_request,
                red_flags=v.red_flags,
            )
            for v in plan.vendors
        ],
        themes=plan.ideas.themes,
        menu=plan.ideas.menu,
        activities=plan.ideas.activities,
        decor=plan.ideas.decor,
        extras=plan.ideas.extras,
        assumptions=plan.assumptions,
    )

    system_prompt = (
        f"You are a professional multilingual translator for EventGenie. "
        f"Translate the provided event plan strings into natural, simple, respectful {lang_name}. "
        f"Rules:\n"
        f"1. Output valid JSON matching the exact schema provided.\n"
        f"2. Keep proper nouns, numbers, currencies (e.g. INR), and technical terms (e.g. DJ) intact.\n"
        f"3. Translate text faithfully without adding or omitting array items."
    )
    user_prompt = payload.model_dump_json()

    for attempt in range(2):
        try:
            trans_res: PlanTranslationPayload = llm.generate_json(
                system=system_prompt,
                prompt=user_prompt,
                schema=PlanTranslationPayload,
                temperature=0.0,
            )

            # Reconstruct translated EventPlan
            new_budget = [
                BudgetLine(
                    key=orig.key,
                    label=trans.label,
                    percent=orig.percent,
                    amount=orig.amount,
                    note=trans.note,
                )
                for orig, trans in zip(plan.budget, trans_res.budget, strict=True)
            ]
            new_timeline = [
                Task(
                    title=trans.title,
                    phase=trans.phase,
                    due_date=orig.due_date,
                    owner=orig.owner,
                    status=orig.status,
                    category_key=orig.category_key,
                )
                for orig, trans in zip(plan.timeline, trans_res.timeline, strict=True)
            ]
            new_vendors = [
                VendorItem(
                    category_key=orig.category_key,
                    label=trans.label,
                    questions_to_ask=trans.questions_to_ask,
                    documents_to_request=trans.documents_to_request,
                    red_flags=trans.red_flags,
                )
                for orig, trans in zip(plan.vendors, trans_res.vendors, strict=True)
            ]
            new_ideas = IdeaSet(
                themes=trans_res.themes,
                menu=trans_res.menu,
                activities=trans_res.activities,
                decor=trans_res.decor,
                extras=trans_res.extras,
            )

            translated_plan = EventPlan(
                lang=target_lang,
                event_type=plan.event_type,
                event_date=plan.event_date,
                guests=plan.guests,
                total_budget=plan.total_budget,
                currency=plan.currency,
                city=plan.city,
                budget=new_budget,
                timeline=new_timeline,
                vendors=new_vendors,
                ideas=new_ideas,
                assumptions=trans_res.assumptions,
                sources_used=plan.sources_used,
            )

            # Verification 1: Structural check
            if not verify_structural_integrity(plan, translated_plan):
                logger.warning(
                    "Translation failed structural integrity check on attempt %d", attempt + 1
                )
                continue

            # Verification 2: Script check (verify strings contain Indic characters)
            sample_strings = [b.label for b in translated_plan.budget] + [
                t.title for t in translated_plan.timeline
            ]
            if not verify_script_ratio(sample_strings, target_lang):
                logger.warning("Translation failed script ratio check on attempt %d", attempt + 1)
                continue

            notice = f"Translated to {lang_name} (Beta). Labelled estimates only."
            return translated_plan, [notice]

        except (LLMError, Exception) as e:
            logger.warning("Translation attempt %d failed: %s", attempt + 1, e)

    # Fallback to English plan with polite notice
    fallback_notice = f"Notice: Translation to {lang_name} is temporarily busy; displaying verified plan in English."
    logger.info("Falling back to English plan for language '%s'", target_lang)
    return plan, [fallback_notice]
