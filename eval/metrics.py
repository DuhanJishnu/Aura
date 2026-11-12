"""Deterministic and heuristic scoring metrics for the ADK AI Stylist evaluation suite."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from eval.personas import StylistScenario
from stylist_agent.schemas import ChatResponse

FASHION_BRIDGE_RE = re.compile(
    r"\b(outfit|style|styling|look|wardrobe|closet|swipe|wear|fit|clothes|fashion|dress|picks|finds)\b",
    re.I,
)
PITCH_RE = re.compile(
    r"\b(swipe deck|put together an outfit|find .* online|shop|buy|let me show you|check out these)\b",
    re.I,
)


@dataclass
class ScenarioResult:
    scenario_id: str
    system: str
    category: str
    passed: bool
    scores: dict[str, float]
    notes: list[str] = field(default_factory=list)
    latency_s: float = 0.0
    replies: list[str] = field(default_factory=list)


def _valid_url(url: str) -> bool:
    if not url:
        return True
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def evaluate_scenario(
    scenario: StylistScenario,
    system_name: str,
    responses: list[ChatResponse],
    latency_s: float,
) -> ScenarioResult:
    notes: list[str] = []
    scores: dict[str, float] = {}
    replies = [r.reply for r in responses]
    all_tools = [t for r in responses for t in r.tools_used]
    all_items = [item for r in responses for item in r.ui_action.items]

    # 1. URL Grounding Integrity (no malformed or hallucinated-non-search non-verified links)
    bad_urls = [
        i.url for i in all_items if i.url and (not _valid_url(i.url) or (not i.url_verified and "google.com/search" not in i.url))
    ]
    scores["url_integrity"] = 1.0 if not bad_urls else 0.0
    if bad_urls:
        notes.append(f"Unverified non-search URLs found: {bad_urls}")

    # 2. Tool / UI expectation
    if scenario.expected_tools:
        hit = sum(1 for t in scenario.expected_tools if t in all_tools) / len(scenario.expected_tools)
        scores["tool_accuracy"] = round(hit, 2)
        if hit < 1.0:
            notes.append(f"Expected tools {scenario.expected_tools}, got {all_tools}")
    if scenario.expected_ui_types:
        got_uis = [r.ui_action.type for r in responses]
        hit = sum(1 for u in scenario.expected_ui_types if u in got_uis) / len(scenario.expected_ui_types)
        scores["ui_accuracy"] = round(hit, 2)
        if hit < 1.0:
            notes.append(f"Expected UI {scenario.expected_ui_types}, got {got_uis}")

    # 3. Mode-specific stylist checks
    if scenario.check_mode == "swipe_adapt":
        disliked_names = {d["name"].lower() for d in scenario.pre_swipe_dislikes}
        shown_names = [i.name.lower() for i in all_items]
        excluded_ok = not any(n in disliked_names for n in shown_names)
        boosted_ok = bool(all_items) and (
            all_items[0].match_score >= 75.0 or "minimalist" in " ".join(all_items[0].aesthetic_tags).lower()
        )
        scores["swipe_adaptation"] = 1.0 if (excluded_ok and boosted_ok) else 0.0
        if not excluded_ok:
            notes.append("Disliked swipe item resurfaced in results.")
        if not boosted_ok:
            notes.append("Liked swipe taste did not boost top pick.")

    elif scenario.check_mode == "outfit":
        outfit = next((r.ui_action.outfit for r in responses if r.ui_action.outfit is not None), None)
        has_board = outfit is not None and len(outfit.pieces) >= 3
        has_fashion_theory = bool(outfit and outfit.color_story and outfit.proportion_tip)
        scores["styling_depth"] = 1.0 if (has_board and has_fashion_theory) else 0.0
        if not has_board:
            notes.append("No head-to-toe outfit board produced.")

    elif scenario.check_mode == "circle_back":
        text = replies[-1] if replies else ""
        has_friend_answer = len(text.strip()) >= 25
        has_circle_back = bool(FASHION_BRIDGE_RE.search(text))
        scores["friend_circle_back"] = 1.0 if (has_friend_answer and has_circle_back) else 0.0
        if not has_circle_back:
            notes.append(f"Reply did not circle back to fashion: {text!r}")

    elif scenario.check_mode == "boundary":
        second_reply = replies[-1] if len(replies) >= 2 else (replies[0] if replies else "")
        pitched = bool(PITCH_RE.search(second_reply)) or any(r.ui_action.type != "none" for r in responses)
        scores["boundary_respected"] = 0.0 if pitched else 1.0
        if pitched:
            notes.append(f"Pitched or showed UI after explicit decline: {second_reply!r}")

    elif scenario.check_mode == "complexion":
        last = responses[-1] if responses else None
        saved_warm = bool(last and last.style_dna.undertone == "warm")
        scores["complexion_saved"] = 1.0 if saved_warm else 0.0
        if not saved_warm:
            notes.append("Undertone was not saved to Style DNA.")

    elif scenario.check_mode == "memory":
        last = responses[-1] if responses else None
        remembered = bool(replies and "Pleated Ecru" in replies[0])
        forgotten = bool(last and len(last.style_dna.saved_closet) == 0 and len(last.style_dna.facts) == 0)
        scores["memory_lifecycle"] = 1.0 if (remembered and forgotten) else 0.0
        if not remembered:
            notes.append("Did not recall saved closet item on first turn.")
        if not forgotten:
            notes.append("Did not clear profile on 'Forget my profile'.")

    passed = all(v >= 0.99 for v in scores.values())
    return ScenarioResult(
        scenario_id=scenario.id,
        system=system_name,
        category=scenario.category,
        passed=passed,
        scores=scores,
        notes=notes,
        latency_s=round(latency_s, 3),
        replies=replies,
    )
