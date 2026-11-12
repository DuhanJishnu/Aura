from __future__ import annotations

import pytest
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.run_config import RunConfig
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext

from stylist_agent import root_agent
from stylist_agent.offline import FakeSearchBackend
from stylist_agent.tools import (
    compare_fashion_items,
    curate_outfit,
    forget_style_profile,
    get_style_profile_and_closet,
    record_style_preference,
    search_fashion_online,
    set_search_backend,
    set_shopping_boundary,
    trigger_photo_stylist,
)


async def _make_tool_context(store) -> ToolContext:
    ss = InMemorySessionService()
    session = await ss.create_session(
        app_name="test_app",
        user_id="u_tools",
        session_id="s_tools",
        state={"user_id": "u_tools", "style_dna": store.get("u_tools").model_dump()},
    )
    inv = InvocationContext(
        invocation_id="inv_1",
        agent=root_agent,
        session=session,
        session_service=ss,
        run_config=RunConfig(),
    )
    return ToolContext(invocation_context=inv)


def test_root_agent_adk_structure():
    assert root_agent.name == "aura_stylist"
    assert len(root_agent.tools) == 8
    assert "{style_dna_summary?}" in root_agent.instruction


@pytest.mark.asyncio
async def test_adk_tools_end_to_end(store):
    set_search_backend(FakeSearchBackend())
    try:
        ctx = await _make_tool_context(store)

        pref = record_style_preference(
            ctx,
            shoe_size="9",
            liked_color="olive",
            disliked_color="neon yellow",
            aesthetic="minimalist",
            budget_max_inr=4000,
            undertone="warm",
            skin_tone="medium",
        )
        assert pref["status"] == "saved"
        assert "shoes size 9" in pref["updated"]

        search_res = await search_fashion_online("olive minimalist shirt", ctx, category="tops", max_budget_inr=4000)
        assert search_res["status"] == "ok"
        assert search_res["count"] >= 3
        assert ctx.state["ui_action"]["type"] == "swipe_deck"

        cmp_res = compare_fashion_items(ctx, ["1", "2"])
        assert cmp_res["status"] == "ok"
        assert ctx.state["ui_action"]["type"] == "compare"

        outfit_res = await curate_outfit("rooftop date night", ctx, vibe="quiet luxury")
        assert outfit_res["status"] == "ok"
        assert ctx.state["ui_action"]["type"] == "outfit_board"
        assert len(outfit_res["outfit"]["pieces"]) >= 3

        photo_res = trigger_photo_stylist(ctx, mode="outfit_check")
        assert photo_res["photo_mode"] == "outfit_check"
        assert ctx.state["ui_action"]["type"] == "request_photo"

        closet_res = get_style_profile_and_closet(ctx, open_closet_ui=True)
        assert closet_res["status"] == "ok"
        assert closet_res["closet_opened"] is True
        assert ctx.state["ui_action"]["type"] == "closet"

        boundary_res = set_shopping_boundary(ctx, declined=True)
        assert boundary_res["declined"] is True

        profile_res = get_style_profile_and_closet(ctx)
        assert "shoes=9" in profile_res["summary"]

        # Prompt-injection safeguard: autonomous forget_style_profile asks UI confirmation first
        forget_res = forget_style_profile(ctx)
        assert forget_res["status"] == "confirmation_required"
        assert ctx.state["ui_action"]["type"] == "confirm_forget"
        assert store.get("u_tools").facts != []

        # Only proceeds when explicitly allowed after confirmation
        ctx.state["allow_destructive_forget"] = True
        confirmed_forget = forget_style_profile(ctx)
        assert confirmed_forget["status"] == "forgotten"
        assert store.get("u_tools").facts == []
    finally:
        set_search_backend(None)
