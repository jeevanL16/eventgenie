"""EventGenie core pipeline for generating and managing event plans.

Orchestrates input validation, RAG context retrieval, LLM generation,
deterministic budget/date calculation, schema validation, repair loops,
and fallback template plans.
"""

from typing import Any

from app.schemas import (
    EventPlan,
    IdeaSet,
    PlanInputs,
    VendorItem,
)
from app.tools.budget import ProposedBudgetLine, calculate_budget
from app.tools.scheduler import ProposedTask, schedule_tasks

# Default budget percentage distributions from Section 7 of EVENTGENIE_MASTER_PROMPT.md
DEFAULT_BUDGET_SPLITS: dict[str, list[ProposedBudgetLine]] = {
    "wedding": [
        ProposedBudgetLine(key="venue", label="Venue & Hall Rental", percent=25.0),
        ProposedBudgetLine(key="catering", label="Catering & Food Service", percent=30.0),
        ProposedBudgetLine(key="decor", label="Decor, Florals & Lighting", percent=10.0),
        ProposedBudgetLine(key="photo_video", label="Photography & Videography", percent=9.0),
        ProposedBudgetLine(key="attire_jewellery", label="Attire & Jewellery", percent=10.0),
        ProposedBudgetLine(key="entertainment", label="Music, DJ & Entertainment", percent=5.0),
        ProposedBudgetLine(key="invitations_gifts", label="Invitations & Favors", percent=3.0),
        ProposedBudgetLine(key="contingency", label="Emergency & Contingency", percent=8.0),
    ],
    "birthday": [
        ProposedBudgetLine(key="venue", label="Venue Rental & Setup", percent=20.0),
        ProposedBudgetLine(key="food", label="Food & Beverages", percent=35.0),
        ProposedBudgetLine(key="decor", label="Theme Decor & Balloons", percent=15.0),
        ProposedBudgetLine(key="cake", label="Custom Birthday Cake", percent=8.0),
        ProposedBudgetLine(
            key="entertainment_games", label="Games, Host & Entertainment", percent=12.0
        ),
        ProposedBudgetLine(key="return_gifts", label="Party Favors & Return Gifts", percent=5.0),
        ProposedBudgetLine(key="contingency", label="Contingency Buffer", percent=5.0),
    ],
    "community": [
        ProposedBudgetLine(key="venue_permits", label="Venue & Civic Permits", percent=20.0),
        ProposedBudgetLine(
            key="logistics_sound_stage", label="Stage, Sound & AV Logistics", percent=25.0
        ),
        ProposedBudgetLine(
            key="food_refreshments", label="Community Food & Refreshments", percent=20.0
        ),
        ProposedBudgetLine(key="publicity", label="Publicity, Banners & Outreach", percent=10.0),
        ProposedBudgetLine(
            key="volunteers_safety", label="Safety, First Aid & Volunteers", percent=10.0
        ),
        ProposedBudgetLine(key="supplies", label="Event Supplies & Signage", percent=5.0),
        ProposedBudgetLine(key="contingency", label="Contingency Fund", percent=10.0),
    ],
}

# Default timeline tasks with day offsets before event date
DEFAULT_TIMELINE_TASKS: dict[str, list[ProposedTask]] = {
    "wedding": [
        ProposedTask(
            title="Book wedding venue and catering",
            phase="6 months out",
            offset_days=-180,
            category_key="venue",
        ),
        ProposedTask(
            title="Finalize photographer and videographer",
            phase="4 months out",
            offset_days=-120,
            category_key="photo_video",
        ),
        ProposedTask(
            title="Design and dispatch wedding invitations",
            phase="3 months out",
            offset_days=-90,
            category_key="invitations_gifts",
        ),
        ProposedTask(
            title="Select ceremonial attire and schedule fittings",
            phase="2 months out",
            offset_days=-60,
            category_key="attire_jewellery",
        ),
        ProposedTask(
            title="Finalize floral decor, stage design, and lighting",
            phase="1 month out",
            offset_days=-30,
            category_key="decor",
        ),
        ProposedTask(
            title="Confirm final guest headcount with caterer",
            phase="2 weeks out",
            offset_days=-14,
            category_key="catering",
        ),
        ProposedTask(
            title="Vendor coordination walk-through and rehearsal",
            phase="2 days out",
            offset_days=-2,
            category_key="general",
        ),
        ProposedTask(
            title="Wedding day ceremonies and reception coordination",
            phase="Day of event",
            offset_days=0,
            category_key="general",
        ),
    ],
    "birthday": [
        ProposedTask(
            title="Reserve party venue or outdoor space",
            phase="1 month out",
            offset_days=-30,
            category_key="venue",
        ),
        ProposedTask(
            title="Send invitations and track RSVPs",
            phase="3 weeks out",
            offset_days=-21,
            category_key="general",
        ),
        ProposedTask(
            title="Order custom birthday cake and confirm food menu",
            phase="2 weeks out",
            offset_days=-14,
            category_key="cake",
        ),
        ProposedTask(
            title="Purchase theme decorations, balloons, and return gifts",
            phase="1 week out",
            offset_days=-7,
            category_key="decor",
        ),
        ProposedTask(
            title="Finalize party games playlist and host schedule",
            phase="2 days out",
            offset_days=-2,
            category_key="entertainment_games",
        ),
        ProposedTask(
            title="Party setup, entertainment hosting, and cake cutting",
            phase="Day of event",
            offset_days=0,
            category_key="general",
        ),
    ],
    "community": [
        ProposedTask(
            title="Secure venue approval, ground permissions, and civic permits",
            phase="2 months out",
            offset_days=-60,
            category_key="venue_permits",
        ),
        ProposedTask(
            title="Launch community outreach campaign and volunteer sign-ups",
            phase="6 weeks out",
            offset_days=-45,
            category_key="publicity",
        ),
        ProposedTask(
            title="Book stage, AV equipment, sound system, and chairs",
            phase="1 month out",
            offset_days=-30,
            category_key="logistics_sound_stage",
        ),
        ProposedTask(
            title="Organize volunteer briefing, safety kits, and traffic plan",
            phase="2 weeks out",
            offset_days=-14,
            category_key="volunteers_safety",
        ),
        ProposedTask(
            title="Procure event banners, signage, and refreshments",
            phase="1 week out",
            offset_days=-7,
            category_key="supplies",
        ),
        ProposedTask(
            title="Stage assembly, AV setup, and sound check",
            phase="1 day out",
            offset_days=-1,
            category_key="logistics_sound_stage",
        ),
        ProposedTask(
            title="Event day operations, crowd safety, and venue cleanup",
            phase="Day of event",
            offset_days=0,
            category_key="general",
        ),
    ],
}

# Default vendor checklists per event type
DEFAULT_VENDORS: dict[str, list[VendorItem]] = {
    "wedding": [
        VendorItem(
            category_key="venue",
            label="Venue / Hall Manager",
            questions_to_ask=[
                "What is the maximum guest capacity and curfew timing?",
                "Are outside caterers and decorators allowed without penalty fees?",
                "Is valet parking and power backup included in the rental cost?",
            ],
            documents_to_request=[
                "Rental agreement and fire/safety NOC",
                "Itemized pricing sheet with overtime fee schedule",
                "Cancellation, refund, and date-rescheduling policy",
            ],
            red_flags=[
                "Refusal to commit overtime rates in writing",
                "Unclear policy on generator fuel charges during outages",
                "No dedicated point of contact on the event day",
            ],
        ),
        VendorItem(
            category_key="catering",
            label="Catering & Beverage Provider",
            questions_to_ask=[
                "How many live counters and service staff are provided per 50 guests?",
                "Can you conduct a full menu tasting session before final confirmation?",
                "What protocol do you follow for food replenishment and leftover disposal?",
            ],
            documents_to_request=[
                "FSSAI / Food hygiene safety license",
                "Sample menu contract with allergen declarations",
                "Staffing ratio commitment letter",
            ],
            red_flags=[
                "No food safety registration or license",
                "Vague answers regarding extra plate counts and buffet wastage",
                "Unwillingness to provide references from recent weddings",
            ],
        ),
        VendorItem(
            category_key="photo_video",
            label="Photography & Videography Lead",
            questions_to_ask=[
                "Will the primary photographer listed in the contract attend in person?",
                "What is the exact delivery timeline for raw files, teaser video, and final album?",
                "How many camera operators and drones will cover the ceremonies?",
            ],
            documents_to_request=[
                "Service contract with delivery milestone dates",
                "Portfolio of complete unedited wedding albums",
                "Equipment backup plan document",
            ],
            red_flags=[
                "Delivery timeline exceeding 90 days without penalty clause",
                "No backup camera bodies or dual SD card recording",
                "Subcontracting coverage to unvetted freelance interns",
            ],
        ),
    ],
    "birthday": [
        VendorItem(
            category_key="venue",
            label="Party Venue Host",
            questions_to_ask=[
                "What time can we access the hall for balloon and theme setup?",
                "Are outside music systems, confetti, and pinatas permitted?",
                "Is cleaning and trash removal included post-party?",
            ],
            documents_to_request=[
                "Booking receipt and time-slot contract",
                "House rules on decor attachment and wall adhesive restrictions",
            ],
            red_flags=[
                "Hidden cleaning fees added after verbal confirmation",
                "Strict noise bans that prevent normal party games and music",
            ],
        ),
        VendorItem(
            category_key="cake",
            label="Custom Cake Bakery",
            questions_to_ask=[
                "What flavors and eggless / vegan options are available for the tier cake?",
                "Do you provide temperature-controlled delivery to the venue?",
                "Can you replicate the exact design reference provided?",
            ],
            documents_to_request=[
                "Order invoice with exact weight, flavor, and delivery window",
                "Portfolio of custom birthday theme cakes",
            ],
            red_flags=[
                "No refrigerated delivery vehicle for cream/fondant cakes",
                "No confirmation of delivery time window",
            ],
        ),
    ],
    "community": [
        VendorItem(
            category_key="logistics_sound_stage",
            label="Audio-Visual & Stage Contractor",
            questions_to_ask=[
                "What is the wattage and coverage area of the sound system for outdoor crowds?",
                "Do you provide a silent diesel generator for uninterrupted power?",
                "Is an on-site audio technician stationed throughout the event?",
            ],
            documents_to_request=[
                "Equipment list and electrical load requirement calculation",
                "Public liability insurance and vendor registration",
            ],
            red_flags=[
                "No backup microphones or spare mixer channels on site",
                "Underpowered PA system for the venue size and expected crowd",
            ],
        ),
    ],
}

# Default creative ideas per event type
DEFAULT_IDEAS: dict[str, IdeaSet] = {
    "wedding": IdeaSet(
        themes=[
            "Royal Heritage: Brass lamps, marigold garlands, and raw silk draping",
            "Modern Pastel Elegance: Ivory florals, fairy lights, and subtle eucalyptus accents",
            "Eco-Conscious Botanical: Terracotta pots, banana fiber seating, and potted favors",
        ],
        menu=[
            "Welcome: Spiced coconut cooler and saffron almond thandai",
            "Live Counters: Artisanal chaat station and freshly rolled mini dosas",
            "Main Feast: Regional royal thali featuring seasonal specialties",
            "Dessert: Hot artisanal jalebi paired with saffron rabdi",
        ],
        activities=[
            "Sangeet dance performances with custom family video montages",
            "Live traditional shehnai and flute instrumental welcome",
            "Interactive Polaroid guestbook with handwritten blessings",
        ],
        decor=[
            "Mandap framed with fresh tuberose and golden bells",
            "Suspended floral canopies over dining pavilions",
            "Warm ambient LED wash lights highlighting architectural elements",
        ],
        extras=[
            "Custom luggage tags or brass diya return favors",
            "Emergency hospitality kits in restrooms (bobby pins, safety pins, mints)",
        ],
    ),
    "birthday": IdeaSet(
        themes=[
            "Space Explorer: Midnight blue starry backdrops, neon glow sticks, and rocket props",
            "Carnival Fiesta: Vibrant striped canopies, popcorn carts, and balloon arches",
            "Retro Neon Arcade: Pixel art banners, arcade games, and customized glow bands",
        ],
        menu=[
            "Sliders, mini pizzas, and loaded nachos with cheese fountain",
            "Fresh fruit skewers and mocktail slushies",
            "Theme-sculpted birthday cake with confetti cupcakes",
        ],
        activities=[
            "Interactive treasure hunt with clue cards and prizes",
            "Custom photo booth with whimsical props and instant prints",
            "High-energy musical freeze dance and party games",
        ],
        decor=[
            "Organic balloon garland backdrop with personalized LED neon name sign",
            "Color-coordinated table runners with theme centerpieces",
        ],
        extras=[
            "Personalized eco-friendly canvas tote bags with craft kits as return gifts",
            "Custom party badges and wristbands for all guests",
        ],
    ),
    "community": IdeaSet(
        themes=[
            "Green Neighborhood: Sustainable living, plant exchanges, and eco-friendly stalls",
            "Cultural Unity Festival: Folk music, heritage crafts, and multicultural food fair",
            "Wellness & Sports Day: Fun marathon, yoga workshops, and cooperative games",
        ],
        menu=[
            "Healthy wholesome grain bowls, wraps, and fresh seasonal fruit cups",
            "Local street food stalls managed by neighborhood culinary artisans",
            "Hydration stations with infused water and fresh herbal coolers",
        ],
        activities=[
            "Community talent showcase and youth battle-of-the-bands",
            "Interactive DIY craft workshops and pottery wheel demonstrations",
            "Friendly neighborhood tug-of-war and relay races",
        ],
        decor=[
            "Colorful fabric pennants and bunting made from upcycled cloth",
            "Clear bilingual directional signage and event schedule boards",
        ],
        extras=[
            "Dedicated waste segregation stations with composting volunteers",
            "Well-marked first aid booth and lost-and-found helpdesk",
        ],
    ),
}


def fallback_plan(inputs: PlanInputs | dict[str, Any]) -> EventPlan:
    """Generate a deterministic, complete, schema-valid EventPlan without calling an LLM.

    Used when:
    - LLM provider is unavailable or quota is exhausted (HTTP 429)
    - LLM generation fails Pydantic schema validation after repair retries
    - Running offline test suites or demo fallbacks

    Args:
        inputs: User intake inputs (PlanInputs instance or equivalent dict).

    Returns:
        A fully validated, self-consistent EventPlan object.

    Raises:
        ValidationError: If inputs fail validation.
    """
    if isinstance(inputs, dict):
        validated_inputs = PlanInputs.model_validate(inputs)
    elif isinstance(inputs, PlanInputs):
        validated_inputs = inputs
    else:
        raise TypeError(f"Expected PlanInputs or dict, got {type(inputs)}")

    event_type = validated_inputs.event_type.lower()
    if event_type not in DEFAULT_BUDGET_SPLITS:
        event_type = "community"

    # 1. Compute exact budget lines using deterministic budget tool
    budget_proposals = DEFAULT_BUDGET_SPLITS[event_type]
    budget_lines = calculate_budget(
        lines=budget_proposals,
        total_budget=validated_inputs.total_budget,
    )

    # 2. Compute timeline dates and sort chronologically using scheduler tool
    timeline_proposals = DEFAULT_TIMELINE_TASKS[event_type]
    timeline_tasks = schedule_tasks(
        tasks=timeline_proposals,
        event_date=validated_inputs.event_date,
    )

    # 3. Retrieve vendor guidelines and creative ideas
    vendors = DEFAULT_VENDORS.get(event_type, DEFAULT_VENDORS["community"])
    ideas = DEFAULT_IDEAS.get(event_type, DEFAULT_IDEAS["community"])

    # 4. Formulate explicit assumptions
    assumptions = [
        "All budget line items are estimated benchmark allocations and subject to local vendor quotes.",
        "Timeline tasks are scheduled backward from the event date and clamped within current calendar bounds.",
        "Customs, rituals, and ceremonies vary widely by family, community, and region; confirm specifics with elders.",
        "Generated using deterministic fallback template (no external LLM call).",
    ]

    return EventPlan(
        lang=validated_inputs.lang,
        event_type=validated_inputs.event_type,
        event_date=validated_inputs.event_date,
        guests=validated_inputs.guests,
        total_budget=validated_inputs.total_budget,
        currency=validated_inputs.currency,
        city=validated_inputs.city,
        budget=budget_lines,
        timeline=timeline_tasks,
        vendors=vendors,
        ideas=ideas,
        assumptions=assumptions,
        sources_used=["Standard Event Benchmarks (v1)"],
    )
