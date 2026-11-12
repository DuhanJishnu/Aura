"""Stylist evaluation scenarios covering fashion sense, swipe memory, friend circle-back, and boundaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class StylistScenario:
    id: str
    category: str
    turns: list[str]
    expected_tools: list[str] = field(default_factory=list)
    expected_ui_types: list[str] = field(default_factory=list)
    pre_swipe_likes: list[dict] = field(default_factory=list)
    pre_swipe_dislikes: list[dict] = field(default_factory=list)
    must_circle_back: bool = False
    must_not_pitch: bool = False
    check_mode: Literal["search", "outfit", "swipe_adapt", "circle_back", "boundary", "memory", "complexion"] = "search"


SCENARIOS: list[StylistScenario] = [
    StylistScenario(
        id="sc_online_discovery",
        category="online_discovery",
        turns=["Find clean retro casual sneakers online under ₹7000"],
        expected_tools=["search_fashion_online"],
        expected_ui_types=["swipe_deck"],
        check_mode="search",
    ),
    StylistScenario(
        id="sc_outfit_occasion",
        category="outfit_occasion",
        turns=["I have a rooftop date night this Saturday — build a smart-casual outfit for me"],
        expected_tools=["curate_outfit"],
        expected_ui_types=["outfit_board"],
        check_mode="outfit",
    ),
    StylistScenario(
        id="sc_swipe_adaptation",
        category="swipe_adaptation",
        pre_swipe_likes=[
            {
                "id": "item_olive_linen",
                "name": "Relaxed Olive Linen Overshirt",
                "brand": "Uniqlo",
                "category": "tops",
                "price_text": "₹2,490",
                "price_estimate_inr": 2490,
                "color": "olive",
                "color_hex": "#556B2F",
                "aesthetic_tags": ["minimalist", "quiet luxury", "linen"],
            }
        ],
        pre_swipe_dislikes=[
            {
                "id": "item_neon_runner",
                "name": "Volt Neon Mesh Trail Runners",
                "brand": "Nike",
                "category": "shoes",
                "price_text": "₹6,995",
                "price_estimate_inr": 6995,
                "color": "neon yellow",
                "color_hex": "#D9FF00",
                "aesthetic_tags": ["sporty", "bold", "athleisure"],
            }
        ],
        turns=["Show me casual shirts or shoes that match my taste"],
        expected_tools=["search_fashion_online"],
        expected_ui_types=["swipe_deck"],
        check_mode="swipe_adapt",
    ),
    StylistScenario(
        id="sc_offtopic_circle_back",
        category="off_topic_circle_back",
        turns=["How do I make creamy pasta at home?"],
        must_circle_back=True,
        check_mode="circle_back",
    ),
    StylistScenario(
        id="sc_stress_friend_circle_back",
        category="friend_empathy_circle_back",
        turns=["I'm super stressed about a big presentation on Monday"],
        must_circle_back=True,
        check_mode="circle_back",
    ),
    StylistScenario(
        id="sc_boundary_no_means_no",
        category="boundary_no_means_no",
        turns=[
            "No thanks, I'm not shopping right now — stop pitching outfits",
            "Okay, anyway how's the weather usually in October?",
        ],
        must_not_pitch=True,
        check_mode="boundary",
    ),
    StylistScenario(
        id="sc_complexion_palette",
        category="complexion_undertone",
        turns=["I have a warm undertone — which colors suit me best?"],
        expected_tools=["record_style_preference"],
        check_mode="complexion",
    ),
    StylistScenario(
        id="sc_closet_memory_and_forget",
        category="profile_memory",
        pre_swipe_likes=[
            {
                "id": "item_ecru_chino",
                "name": "Pleated Ecru Wide-Leg Trousers",
                "brand": "Zara",
                "category": "bottoms",
                "price_text": "₹3,290",
                "price_estimate_inr": 3290,
                "color": "cream",
                "color_hex": "#EDE6D6",
                "aesthetic_tags": ["quiet luxury", "minimalist"],
            }
        ],
        turns=[
            "What do you know about me and my closet?",
            "Forget my profile",
        ],
        expected_tools=["get_style_profile_and_closet", "forget_style_profile"],
        check_mode="memory",
    ),
]
