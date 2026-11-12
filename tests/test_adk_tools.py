from __future__ import annotations

import pytest
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.run_config import RunConfig
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext

from stylist_agent import root_agent
from stylist_agent.memory import PreferenceStore
from stylist_agent.offline import FakeSearchBackend
from stylist_agent.tools import (
    LiveGoogleSearchBackend,
    compare_fashion_items,
    curate_outfit,
    forget_style_profile,
    get_style_profile_and_closet,
    record_style_preference,
    search_fashion_online,
    search_items_deck,
    set_search_backend,
    set_shopping_boundary,
    set_store,
    trigger_photo_stylist,
)


async def _make_tool_context(store: PreferenceStore, user_id: str = "u_tools") -> ToolContext:
    ss = InMemorySessionService()
    session = await ss.create_session(
        app_name="test_app",
        user_id=user_id,
        session_id="s_tools",
        state={"user_id": user_id, "style_dna": store.get(user_id).model_dump()},
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


@pytest.mark.asyncio
async def test_item_search_returns_10_to_15_with_images():
    from stylist_agent.schemas import FashionItem

    class _PoolFake:
        async def search(self, query, category, max_budget_inr, dna, *, exclude_ids=None, limit=None):
            excluded = set(exclude_ids or ())
            items = []
            for idx in range(20):
                items.append(
                    FashionItem(
                        id=f"shoe_{idx}",
                        name=f"Runner Shoe {idx}",
                        brand="Nike",
                        category=category,
                        price_text="₹4,999",
                        price_estimate_inr=4999,
                        color="black",
                        image_url="" if idx < 6 else f"https://cdn.example.com/shoe_{idx}.jpg",
                        image_source="none" if idx < 6 else "retailer",
                    )
                )
            with_img = [i for i in items if i.id not in excluded and i.image_url]
            return with_img[: (limit or 15)]

    store = PreferenceStore()
    set_store(store)
    set_search_backend(_PoolFake())
    try:
        ctx = await _make_tool_context(store, "u_items_10_15")
        res = await search_fashion_online("running shoes", ctx, category="shoes")
        assert 10 <= res["count"] <= 15
        assert all(it["image_url"] for it in ctx.state["ui_action"]["items"])
        assert ctx.state["ui_action"]["search_meta"]["category"] == "shoes"
    finally:
        set_search_backend(None)


@pytest.mark.asyncio
async def test_find_more_keeps_category_and_excludes_seen():
    store = PreferenceStore()
    set_store(store)
    set_search_backend(FakeSearchBackend())
    try:
        ctx = await _make_tool_context(store, "u_shoes_more")
        first = await search_fashion_online("sneakers", ctx, category="shoes", limit=6)
        first_ids = [it["id"] for it in first["items"]]
        assert len(first_ids) == 6
        assert all(it["category"] == "shoes" for it in ctx.state["ui_action"]["items"])

        dna = store.get("u_shoes_more")
        more = await search_items_deck(
            query="sneakers",
            dna=dna,
            category="shoes",
            exclude_item_ids=first_ids,
            limit=6,
        )
        assert len(more) >= 5
        assert all(it.category == "shoes" for it in more)
        assert set(it.id for it in more).isdisjoint(set(first_ids))
    finally:
        set_search_backend(None)


@pytest.mark.asyncio
async def test_pool_pagination_reuses_cache():
    from app import config
    from stylist_agent.db import get_db
    from stylist_agent.memory import pref_hash
    from stylist_agent.schemas import FashionItem

    store = PreferenceStore()
    set_store(store)
    dna = store.get("u_pool_cache")
    backend = LiveGoogleSearchBackend()
    calls = {"count": 0}

    async def _fake_discover(**kwargs):
        calls["count"] += 1
        return [
            FashionItem(
                id=f"cached_shoe_{i}",
                name=f"Cached Shoe {i}",
                brand="Adidas",
                category="shoes",
                price_text="₹5,999",
                price_estimate_inr=5999,
                color="white",
                image_url=f"https://cdn.example.com/c_{i}.jpg",
                image_source="retailer",
            )
            for i in range(20)
        ]

    backend._discover_and_enrich = _fake_discover  # type: ignore[method-assign]
    unique_query = f"white sneakers {hash(dna.user_id)}"
    pool_key = f"pool:{unique_query}:shoes:0:{pref_hash(dna)}"
    get_db().set_search_cache(pool_key, {"items": []}, ttl_sec=0)

    page1 = await backend.search(unique_query, "shoes", None, dna, limit=10)
    assert len(page1) == 10
    assert calls["count"] == 1

    # Second page with remaining 10 unseen items should hit pool cache with 0 new discover calls
    assert config.ITEM_DECK_MIN <= 10
    page2 = await backend.search(unique_query, "shoes", None, dna, exclude_ids={i.id for i in page1}, limit=10)
    assert len(page2) == 10
    assert calls["count"] == 1
    assert {i.id for i in page1}.isdisjoint({i.id for i in page2})


@pytest.mark.asyncio
async def test_unknown_category_normalized():
    store = PreferenceStore()
    set_store(store)
    set_search_backend(FakeSearchBackend())
    try:
        ctx = await _make_tool_context(store, "u_cat_norm")
        res = await search_fashion_online("sneakers", ctx, category="footwear")
        assert res["category"] == "shoes"

        res2 = await search_fashion_online("cool outfit", ctx, category="weird_unknown_cat")
        assert res2["category"] == "apparel"
    finally:
        set_search_backend(None)


@pytest.mark.asyncio
async def test_cached_items_have_valid_media_urls():
    import time
    from urllib.parse import parse_qs, urlparse

    from stylist_agent.db import get_db
    from stylist_agent.media import signed_media_url, verify_media_token
    from stylist_agent.memory import pref_hash
    from stylist_agent.schemas import FashionItem

    store = PreferenceStore()
    set_store(store)
    dna = store.get("u_resign")
    pool_key = f"pool:loafers:shoes:0:{pref_hash(dna)}"
    expired_url = signed_media_url("item_abc123", ttl_seconds=-60)
    assert not verify_media_token("item_abc123", parse_qs(urlparse(expired_url).query)["sig"][0], parse_qs(urlparse(expired_url).query)["exp"][0])

    get_db().set_search_cache(
        pool_key,
        {
            "items": [
                FashionItem(
                    id=f"loaf_{i}",
                    name=f"Loafer {i}",
                    brand="Clarks",
                    category="shoes",
                    price_text="₹6,999",
                    color="brown",
                    image_url=expired_url,
                    image_source="ai_generated",
                ).model_dump()
                for i in range(12)
            ]
        },
        ttl_sec=600,
    )

    backend = LiveGoogleSearchBackend()
    items = await backend.search("loafers", "shoes", None, dna, limit=10)
    assert len(items) == 10
    for it in items:
        qs = parse_qs(urlparse(it.image_url).query)
        assert int(qs["exp"][0]) > int(time.time())
        assert verify_media_token("item_abc123", qs["sig"][0], qs["exp"][0])
