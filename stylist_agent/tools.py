"""Google ADK tools for the AI Fashion Stylist.

Includes:
- `search_fashion_online`: ADK Google Search sub-runner + SSRF-safe grounding + StyleDNA re-ranking + search TTL cache.
- `curate_outfit`: Head-to-toe 5-look OutfitLook builder with fingerprint dedupe, verified totals, & SSE streaming support.
- `record_style_preference` / `get_style_profile_and_closet` / `forget_style_profile`: Confirmation-gated StyleDNA tools.
- `compare_fashion_items`, `trigger_photo_stylist`, `set_shopping_boundary`.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any, Protocol, TypeVar
from urllib.parse import quote_plus, urlparse

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from google.adk.tools.google_search_tool import google_search
from google.genai import types
from pydantic import BaseModel, Field

from app import config
from stylist_agent.db import get_db
from stylist_agent.media import (
    enrich_item_images,
    enrich_look_deck_images,
    enrich_look_deck_stream,
    enrich_outfit_images,
    resign_media_url,
)
from stylist_agent.memory import (
    PreferenceStore,
    _upsert_fact,
    infer_season,
    item_key,
    look_fingerprint,
    pref_hash,
    rerank_items,
    summarize_dna_for_prompt,
)
from stylist_agent.prompts import (
    CARD_EXTRACTOR_INSTRUCTION,
    OUTFIT_ARCHITECT_INSTRUCTION,
    WEB_FINDER_INSTRUCTION,
)
from stylist_agent.schemas import (
    FashionItem,
    OutfitLook,
    OutfitPiece,
    SearchMeta,
    StyleDNA,
    UIAction,
)

log = logging.getLogger("shopper.tools")

# Shared preference store (swappable in tests)
_STORE = PreferenceStore()
_T = TypeVar("_T", bound=BaseModel)


def get_store() -> PreferenceStore:
    return _STORE


def set_store(store: PreferenceStore) -> None:
    global _STORE
    _STORE = store


class SearchBackend(Protocol):
    async def search(
        self,
        query: str,
        category: str,
        max_budget_inr: int | None,
        dna: StyleDNA,
    ) -> list[FashionItem]: ...

    async def curate_outfit(
        self,
        occasion: str,
        vibe: str,
        anchor_item: str,
        max_budget_inr: int | None,
        dna: StyleDNA,
    ) -> OutfitLook: ...


_SEARCH_BACKEND: SearchBackend | None = None


def set_search_backend(backend: SearchBackend | None) -> None:
    """Allow unit tests and offline evals to inject a deterministic search backend."""
    global _SEARCH_BACKEND
    _SEARCH_BACKEND = backend


class _CardBatch(BaseModel):
    items: list[FashionItem] = Field(default_factory=list)


class _LookDeckBatch(BaseModel):
    looks: list[OutfitLook] = Field(default_factory=list)


def _stable_id(brand: str, name: str) -> str:
    digest = hashlib.sha1(f"{brand.lower()}|{name.lower()}".encode()).hexdigest()[:10]
    return f"item_{digest}"


def _shop_search_url(brand: str, name: str) -> str:
    q = quote_plus(f"{brand} {name} buy online {config.DEFAULT_REGION}".strip())
    return f"https://www.google.com/search?tbm=shop&q={q}"


def _domain_of(url: str, fallback_title: str = "") -> str:
    if fallback_title and "." in fallback_title and " " not in fallback_title:
        return fallback_title.lower()
    try:
        host = urlparse(url).netloc.lower()
        return host.removeprefix("www.") or "google.com"
    except Exception:
        return "google.com"


def _wrap_untrusted_web(findings: str, grounding_links: list[dict[str, str]]) -> str:
    """Delimit external search snippets clearly to defend against indirect prompt injection."""
    safe_findings = findings.replace("</untrusted_web_results>", "")
    safe_links = json.dumps(grounding_links[:40], ensure_ascii=False).replace("</untrusted_web_results>", "")
    return (
        "<untrusted_web_results>\n"
        f"SEARCH_SUMMARY:\n{safe_findings}\n\n"
        f"GROUNDING_LINKS:\n{safe_links}\n"
        "</untrusted_web_results>"
    )


def _compute_look_total(pieces: list[OutfitPiece], fallback_inr: int | None, fallback_text: str) -> tuple[int | None, str]:
    """Deterministically sum piece prices when available so LLM arithmetic cannot drift."""
    prices = [p.price_estimate_inr for p in pieces if p.price_estimate_inr and p.price_estimate_inr > 0]
    if prices:
        total = int(sum(prices))
        prefix = "~" if len(prices) < len(pieces) else ""
        return total, f"{prefix}₹{total:,}"
    return fallback_inr, fallback_text


def _finalize_look(
    look: OutfitLook,
    occasion: str,
    valid_urls: dict[str, str],
    idx: int = 0,
) -> OutfitLook:
    fixed_pieces: list[OutfitPiece] = []
    for piece in look.pieces:
        has_verified = bool(piece.url and piece.url in valid_urls)
        url = piece.url if has_verified else _shop_search_url(piece.brand, piece.search_query or piece.name)
        store = piece.store or _domain_of(url, valid_urls.get(piece.url, "") if has_verified else "google.com")
        fixed_pieces.append(
            piece.model_copy(update={"url": url, "url_verified": has_verified, "store": store})
        )
    total_inr, total_text = _compute_look_total(fixed_pieces, look.total_estimate_inr, look.total_estimate_text)
    look_id = "look_" + hashlib.sha1(f"{look.title}|{occasion}|{idx}".encode()).hexdigest()[:8]
    interim = look.model_copy(
        update={
            "id": look_id,
            "occasion": look.occasion or occasion,
            "pieces": fixed_pieces,
            "tags": look.tags or [look.vibe.lower(), occasion.lower()],
            "total_estimate_inr": total_inr,
            "total_estimate_text": total_text,
        }
    )
    return interim.model_copy(update={"look_fingerprint": look_fingerprint(interim)})


def _resolve_dna(tool_context: ToolContext) -> StyleDNA:
    user_id = str(tool_context.state.get("user_id") or "default")
    return _STORE.get(user_id)


def _persist_dna(tool_context: ToolContext, dna: StyleDNA) -> None:
    saved = _STORE.save(dna)
    tool_context.state["style_dna"] = saved.model_dump()
    tool_context.state["style_dna_summary"] = summarize_dna_for_prompt(saved)


_VALID_CATEGORIES = {"apparel", "tops", "bottoms", "outerwear", "dresses", "shoes", "accessories", "ethnic"}
_CAT_ALIASES = {
    "footwear": "shoes",
    "sneakers": "shoes",
    "boots": "shoes",
    "heels": "shoes",
    "sandals": "shoes",
    "loafers": "shoes",
    "top": "tops",
    "shirt": "tops",
    "shirts": "tops",
    "bottom": "bottoms",
    "pants": "bottoms",
    "trousers": "bottoms",
    "jeans": "bottoms",
    "jacket": "outerwear",
    "jackets": "outerwear",
    "dress": "dresses",
    "accessory": "accessories",
    "bag": "accessories",
    "bags": "accessories",
}


def _normalize_category(category: str) -> str:
    c = (category or "apparel").strip().lower()
    c = _CAT_ALIASES.get(c, c)
    return c if c in _VALID_CATEGORIES else "apparel"


def _dedupe_items(items: list[FashionItem], exclude_ids: set[str] | None = None) -> list[FashionItem]:
    seen_ids = set(exclude_ids or ())
    seen_keys: set[str] = set()
    seen_urls: set[str] = set()
    out: list[FashionItem] = []
    for item in items:
        key = item_key(item)
        if item.id in seen_ids or key in seen_keys:
            continue
        if item.url_verified and item.url and item.url in seen_urls:
            continue
        seen_ids.add(item.id)
        seen_keys.add(key)
        if item.url_verified and item.url:
            seen_urls.add(item.url)
        out.append(item)
    return out


_ANGLES = (
    "best-selling mainstream options from major retailers",
    "different brands and price tiers than the obvious picks (include budget and premium)",
)


class LiveGoogleSearchBackend:
    """Uses a dedicated Google ADK Agent with `google_search` + resilient structured extraction."""

    def __init__(self, model: str | None = None):
        self.model = model or config.GEMINI_SEARCH_MODEL
        self._client = None

    def _genai_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
        return self._client

    def _model_candidates(self) -> list[str]:
        return list(dict.fromkeys([self.model, config.GEMINI_SEARCH_MODEL_FALLBACK]))

    async def _run_google_search(self, prompt: str) -> tuple[str, list[dict[str, str]]]:
        last_exc: Exception | None = None
        for model_name in self._model_candidates():
            try:
                search_agent = Agent(
                    name="web_fashion_finder",
                    model=model_name,
                    description="Searches the live web for real buyable clothes, shoes, and accessories.",
                    instruction=WEB_FINDER_INSTRUCTION,
                    tools=[google_search],
                )
                session_service = InMemorySessionService()
                runner = Runner(agent=search_agent, app_name="fashion_search_sub", session_service=session_service)
                await session_service.create_session(app_name="fashion_search_sub", user_id="search", session_id="s1")
                msg = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])

                text_parts: list[str] = []
                links: list[dict[str, str]] = []
                seen_urls: set[str] = set()

                async for event in runner.run_async(user_id="search", session_id="s1", new_message=msg):
                    if event.content and event.content.parts:
                        for p in event.content.parts:
                            if p.text:
                                text_parts.append(p.text)
                    gm = getattr(event, "grounding_metadata", None)
                    if gm and getattr(gm, "grounding_chunks", None):
                        for chunk in gm.grounding_chunks:
                            web = getattr(chunk, "web", None)
                            if web and getattr(web, "uri", None) and web.uri not in seen_urls:
                                seen_urls.add(web.uri)
                                links.append({"url": web.uri, "title": getattr(web, "title", "") or ""})

                return "\n".join(text_parts).strip(), links
            except Exception as exc:
                last_exc = exc
                log.warning("Google Search sub-agent failed on %s: %s", model_name, exc)
        if last_exc:
            raise last_exc
        return "", []

    async def _generate_structured_resilient(
        self,
        *,
        prompt: str,
        system_instruction: str,
        schema: type[_T],
        temperature: float,
        list_field: str | None = None,
        item_model: type[BaseModel] | None = None,
    ) -> _T:
        """Structured Gemini call with model fallback, 1 repair retry, and partial item salvage."""
        client = self._genai_client()
        raw_text = ""
        for attempt_prompt in (
            prompt,
            f"{prompt}\n\nIMPORTANT: Return valid JSON strictly matching the requested schema.",
        ):
            for model_name in self._model_candidates():
                try:
                    resp = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=attempt_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=temperature,
                            response_mime_type="application/json",
                            response_schema=schema,
                        ),
                    )
                    parsed = getattr(resp, "parsed", None)
                    if isinstance(parsed, schema):
                        return parsed
                    raw_text = (getattr(resp, "text", None) or "").strip()
                    return schema.model_validate_json(raw_text)
                except Exception as exc:
                    log.debug("Structured decode retry (%s): %s", model_name, exc)
                    continue

        # Partial salvage if we received a JSON object with a partial array
        if raw_text and list_field and item_model is not None:
            try:
                raw_obj = json.loads(raw_text)
                raw_entries = raw_obj.get(list_field, []) if isinstance(raw_obj, dict) else []
                salvaged = []
                for entry in raw_entries:
                    try:
                        salvaged.append(item_model.model_validate(entry))
                    except Exception:
                        continue
                if salvaged:
                    return schema.model_validate({list_field: salvaged})
            except Exception:
                pass
        return schema.model_validate({})

    async def _multi_search(self, base_prompt: str, per_angle: int = 10) -> tuple[str, list[dict[str, str]]]:
        results = await asyncio.gather(
            *(self._run_google_search(f"{base_prompt}\nFocus: {angle}. Find {per_angle} distinct items.") for angle in _ANGLES),
            return_exceptions=True,
        )
        findings: list[str] = []
        links: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for res in results:
            if isinstance(res, Exception):
                continue
            text, lks = res
            if text:
                findings.append(text)
            for lk in lks:
                if lk.get("url") and lk["url"] not in seen_urls:
                    seen_urls.add(lk["url"])
                    links.append(lk)
        if not findings:
            raise RuntimeError("All grounded Google Search calls failed")
        return "\n\n".join(findings), links

    async def _discover_and_enrich(
        self,
        *,
        query: str,
        category: str,
        max_budget_inr: int | None,
        dna: StyleDNA,
        exclude_names: list[str] | None = None,
        multi_angle: bool = True,
    ) -> list[FashionItem]:
        budget_clause = f"under ₹{max_budget_inr}" if max_budget_inr else (
            f"around or under ₹{dna.budget_max}" if dna.budget_max else "various mid-range budgets"
        )
        size_clause = f"Size: {dna.sizes.get(category)}" if dna.sizes.get(category) else ""
        taste_clause = summarize_dna_for_prompt(dna)
        avoid_clause = (
            f"\nDifferent from these (do not repeat): {', '.join(exclude_names[:20])}"
            if exclude_names
            else ""
        )

        search_prompt = (
            f"Find {config.ITEM_CANDIDATES} distinct real, currently buyable {category} items online in {config.DEFAULT_REGION} ({config.DEFAULT_CURRENCY}) "
            f"for this request: '{query}'. Budget: {budget_clause}. {size_clause}{avoid_clause}\n"
            f"User Style DNA to prioritize:\n{taste_clause}"
        )
        if multi_angle:
            findings, grounding_links = await self._multi_search(
                search_prompt, per_angle=max(8, config.ITEM_CANDIDATES // 2)
            )
        else:
            findings, grounding_links = await self._run_google_search(search_prompt)

        extract_prompt = (
            f"User query: {query}\nCategory: {category}\nUser Style DNA:\n{taste_clause}\n\n"
            f"Untrusted External Search Results (ONLY use URLs from GROUNDING_LINKS if they match the item; otherwise leave url empty):\n"
            f"{_wrap_untrusted_web(findings, grounding_links)}"
        )

        batch = await self._generate_structured_resilient(
            prompt=extract_prompt,
            system_instruction=CARD_EXTRACTOR_INSTRUCTION,
            schema=_CardBatch,
            temperature=0.2,
            list_field="items",
            item_model=FashionItem,
        )

        valid_urls = {link["url"]: link["title"] for link in grounding_links}
        normalized: list[FashionItem] = []
        for item in batch.items[: config.ITEM_CANDIDATES + 4]:
            has_verified = bool(item.url and item.url in valid_urls)
            url = item.url if has_verified else _shop_search_url(item.brand, item.name)
            domain = _domain_of(url, valid_urls.get(item.url, "") if has_verified else "google.com")
            normalized.append(
                item.model_copy(
                    update={
                        "id": _stable_id(item.brand, item.name),
                        "category": _normalize_category(item.category or category),
                        "url": url,
                        "url_verified": has_verified,
                        "source_domain": domain,
                    }
                )
            )
        ranked = rerank_items(_dedupe_items(normalized), dna)
        return await enrich_item_images(ranked, max_gen=4, user_id=dna.user_id)

    async def search(
        self,
        query: str,
        category: str,
        max_budget_inr: int | None,
        dna: StyleDNA,
        *,
        exclude_ids: set[str] | None = None,
        limit: int | None = None,
    ) -> list[FashionItem]:
        cat = _normalize_category(category)
        page_limit = limit or config.ITEM_DECK_MAX
        excluded = set(exclude_ids or ())
        pool_key = f"pool:{query.strip().lower()}:{cat}:{max_budget_inr or dna.budget_max or 0}:{pref_hash(dna)}"

        pool: list[FashionItem] = []
        cached = get_db().get_search_cache(pool_key)
        if cached and isinstance(cached.get("items"), list):
            for raw in cached["items"]:
                try:
                    it = FashionItem.model_validate(raw)
                    if it.image_url:
                        it = it.model_copy(update={"image_url": resign_media_url(it.image_url)})
                    pool.append(it)
                except Exception:
                    continue

        if not pool:
            pool = await self._discover_and_enrich(
                query=query,
                category=cat,
                max_budget_inr=max_budget_inr,
                dna=dna,
                multi_angle=True,
            )

        page = [it for it in pool if it.id not in excluded]
        if len(page) < config.ITEM_DECK_MIN:
            avoid_names = [it.name for it in pool if it.id in excluded or it in page]
            extra = await self._discover_and_enrich(
                query=query,
                category=cat,
                max_budget_inr=max_budget_inr,
                dna=dna,
                exclude_names=avoid_names,
                multi_angle=len(pool) == 0,
            )
            pool = _dedupe_items([*pool, *extra])
            page = [it for it in pool if it.id not in excluded]

        if pool:
            get_db().set_search_cache(
                pool_key,
                {"items": [i.model_dump() for i in pool]},
                ttl_sec=config.SEARCH_CACHE_TTL_SEC,
            )
        return page[:page_limit]

    async def curate_outfit(
        self,
        occasion: str,
        vibe: str,
        anchor_item: str,
        max_budget_inr: int | None,
        dna: StyleDNA,
    ) -> OutfitLook:
        closet_summary = [
            {
                "id": i.id,
                "name": i.name,
                "brand": i.brand,
                "category": i.category,
                "color": i.color,
                "price_text": i.price_text,
            }
            for i in dna.saved_closet[:10]
        ]
        search_q = f"{vibe} {occasion} outfit pieces {anchor_item}".strip()
        findings, grounding_links = await self._run_google_search(
            f"Find real buyable pieces in {config.DEFAULT_REGION} to assemble a cohesive outfit for: {search_q}. "
            f"Budget: {'under ₹' + str(max_budget_inr) if max_budget_inr else 'versatile'}."
        )
        prompt = (
            f"Occasion: {occasion}\nVibe: {vibe}\nAnchor piece to build around: {anchor_item or 'none specified'}\n"
            f"Budget: {max_budget_inr or dna.budget_max or 'flexible'}\n"
            f"User Style DNA:\n{summarize_dna_for_prompt(dna, occasion=occasion)}\n"
            f"Saved Closet Items:\n{json.dumps(closet_summary, ensure_ascii=False)}\n"
            f"{_wrap_untrusted_web(findings, grounding_links[:12])}"
        )
        look = await self._generate_structured_resilient(
            prompt=prompt,
            system_instruction=OUTFIT_ARCHITECT_INSTRUCTION,
            schema=OutfitLook,
            temperature=0.4,
        )
        valid_urls = {link["url"]: link.get("title", "") for link in grounding_links}
        built = _finalize_look(look, occasion, valid_urls, idx=0)
        return await enrich_outfit_images(built, user_id=dna.user_id)

    async def _build_look_deck_raw(
        self,
        occasion: str,
        vibe: str,
        anchor_item: str,
        max_budget_inr: int | None,
        exclude_look_ids: list[str],
        dna: StyleDNA,
    ) -> list[OutfitLook]:
        cache_key = f"deck:{occasion.strip().lower()}:{vibe.strip().lower()}:{anchor_item.strip().lower()}:{max_budget_inr or dna.budget_max or 0}:{pref_hash(dna)}"
        exclude_set = set(exclude_look_ids) | set(dna.seen_look_ids)
        seen_fps = set(dna.seen_look_fingerprints)

        cached = get_db().get_search_cache(cache_key)
        if cached and isinstance(cached.get("looks"), list):
            try:
                rehydrated = [OutfitLook.model_validate(x) for x in cached["looks"]]
                fresh = [
                    lk
                    for lk in rehydrated
                    if lk.id not in exclude_set and look_fingerprint(lk) not in seen_fps
                ]
                if fresh:
                    return fresh[:5]
            except Exception:
                pass

        closet_summary = [
            {
                "id": i.id,
                "name": i.name,
                "brand": i.brand,
                "category": i.category,
                "color": i.color,
                "price_text": i.price_text,
            }
            for i in dna.saved_closet[:10]
        ]
        search_q = f"{vibe} {occasion} outfit ideas buyable pieces {anchor_item}".strip()
        findings, grounding_links = await self._run_google_search(
            f"Find real buyable garments, footwear, and accessories in {config.DEFAULT_REGION} ({config.DEFAULT_CURRENCY}) "
            f"to build 5 distinct cohesive outfits for: {search_q}. Budget: {'under ₹' + str(max_budget_inr) if max_budget_inr else 'varied ₹4k-₹15k'}.\n"
            f"User Style DNA:\n{summarize_dna_for_prompt(dna, occasion=occasion)}"
        )
        prompt = (
            f"Build 5 DISTINCT, swipe-worthy head-to-toe OutfitLook options for occasion '{occasion}' (vibe '{vibe}').\n"
            f"Anchor piece: {anchor_item or 'none specified'}\n"
            f"Budget target per full look: {max_budget_inr or dna.budget_max or 'versatile mid-range'}\n"
            f"Exclude already-seen look IDs/themes: {exclude_look_ids[-20:]}\n"
            f"User Style DNA:\n{summarize_dna_for_prompt(dna, occasion=occasion)}\n"
            f"Saved Closet Items:\n{json.dumps(closet_summary, ensure_ascii=False)}\n"
            f"Untrusted Search Data:\n{_wrap_untrusted_web(findings, grounding_links[:18])}\n\n"
            f"Vary the silhouettes, color stories, and stores across all 5 looks! Fill `brand`, `store`, `price_estimate_inr`, `total_estimate_inr`, and 2-3 `tags` per look."
        )
        batch = await self._generate_structured_resilient(
            prompt=prompt,
            system_instruction=OUTFIT_ARCHITECT_INSTRUCTION,
            schema=_LookDeckBatch,
            temperature=0.55,
            list_field="looks",
            item_model=OutfitLook,
        )

        valid_urls = {link["url"]: link.get("title", "") for link in grounding_links}
        normalized_looks: list[OutfitLook] = []
        batch_fps: set[str] = set()
        for idx, look in enumerate(batch.looks[:7]):
            built = _finalize_look(look, occasion, valid_urls, idx=idx)
            fp = built.look_fingerprint
            if built.id in exclude_set or fp in seen_fps or fp in batch_fps:
                continue
            batch_fps.add(fp)
            normalized_looks.append(built)
            if len(normalized_looks) >= 5:
                break

        if not normalized_looks:
            fallback = await self.curate_outfit(occasion, vibe, anchor_item, max_budget_inr, dna)
            normalized_looks = [fallback]

        get_db().set_search_cache(
            cache_key,
            {"looks": [lk.model_dump() for lk in normalized_looks]},
            ttl_sec=config.SEARCH_CACHE_TTL_SEC,
        )
        return normalized_looks

    async def curate_outfit_deck(
        self,
        occasion: str,
        vibe: str,
        anchor_item: str,
        max_budget_inr: int | None,
        exclude_look_ids: list[str],
        dna: StyleDNA,
    ) -> list[OutfitLook]:
        normalized_looks = await self._build_look_deck_raw(
            occasion=occasion,
            vibe=vibe,
            anchor_item=anchor_item,
            max_budget_inr=max_budget_inr,
            exclude_look_ids=exclude_look_ids,
            dna=dna,
        )
        return await enrich_look_deck_images(normalized_looks, user_id=dna.user_id)

    async def stream_outfit_deck(
        self,
        occasion: str,
        vibe: str,
        anchor_item: str,
        max_budget_inr: int | None,
        exclude_look_ids: list[str],
        dna: StyleDNA,
    ) -> AsyncIterator[OutfitLook]:
        normalized_looks = await self._build_look_deck_raw(
            occasion=occasion,
            vibe=vibe,
            anchor_item=anchor_item,
            max_budget_inr=max_budget_inr,
            exclude_look_ids=exclude_look_ids,
            dna=dna,
        )
        async for enriched in enrich_look_deck_stream(normalized_looks, user_id=dna.user_id):
            yield enriched


def _backend() -> SearchBackend:
    return _SEARCH_BACKEND or LiveGoogleSearchBackend()


async def _invoke_backend_search(
    backend: SearchBackend,
    *,
    query: str,
    category: str,
    max_budget_inr: int | None,
    dna: StyleDNA,
    exclude_ids: set[str],
    limit: int,
) -> list[FashionItem]:
    """Call backend.search while staying compatible with minimal 4-arg test fakes."""
    sig = inspect.signature(backend.search)
    kwargs: dict[str, Any] = {}
    if "exclude_ids" in sig.parameters:
        kwargs["exclude_ids"] = exclude_ids
    if "limit" in sig.parameters:
        kwargs["limit"] = limit
    items = await backend.search(query=query, category=category, max_budget_inr=max_budget_inr, dna=dna, **kwargs)
    filtered = [it for it in _dedupe_items(items, exclude_ids=exclude_ids) if it.image_url or getattr(backend, "allow_imageless", False)]
    # If a test backend didn't set image_url on mock items, fall back to keeping them unless real pipeline ran
    if not filtered and items:
        filtered = _dedupe_items(items, exclude_ids=exclude_ids)
    return filtered[:limit]


async def search_items_deck(
    query: str,
    dna: StyleDNA,
    category: str = "apparel",
    max_budget_inr: int | None = None,
    exclude_item_ids: list[str] | None = None,
    limit: int | None = None,
) -> list[FashionItem]:
    """Direct item search / pagination helper used by POST /items/search (bypasses LLM)."""
    cat = _normalize_category(category)
    page_limit = max(1, min(limit or config.ITEM_DECK_MAX, config.ITEM_CANDIDATES))
    excluded = set(dna.seen_item_ids) | set(exclude_item_ids or [])
    items = await _invoke_backend_search(
        _backend(),
        query=query,
        category=cat,
        max_budget_inr=max_budget_inr,
        dna=dna,
        exclude_ids=excluded,
        limit=page_limit,
    )
    return rerank_items(items, dna)


async def search_fashion_online(
    query: str,
    tool_context: ToolContext,
    category: str = "apparel",
    max_budget_inr: int | None = None,
    exclude_item_ids: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Search online for individual buyable fashion pieces (tops, bottoms, shoes, accessories) matching Style DNA.

    Do NOT use this for head-to-toe outfit lookbooks; use `curate_outfit` for full multi-piece outfits.

    Args:
        query: Natural descriptive fashion search query (e.g., 'sage green linen overshirt relaxed fit',
               'chunky white casual sneakers', 'minimalist tan leather crossbody bag').
        category: One of 'apparel', 'tops', 'bottoms', 'outerwear', 'dresses', 'shoes', 'accessories', 'ethnic'.
        max_budget_inr: Optional maximum price budget in INR.
        exclude_item_ids: Optional list of item IDs to exclude from results.
        limit: Optional max number of cards to return (defaults to ITEM_DECK_MAX).
    """
    dna = _resolve_dna(tool_context)
    dna.declined = False
    cat = _normalize_category(category)
    page_limit = max(1, min(limit or config.ITEM_DECK_MAX, config.ITEM_CANDIDATES))
    excluded = set(dna.seen_item_ids) | set(exclude_item_ids or [])

    items = await _invoke_backend_search(
        _backend(),
        query=query,
        category=cat,
        max_budget_inr=max_budget_inr,
        dna=dna,
        exclude_ids=excluded,
        limit=page_limit,
    )
    ranked = rerank_items(items, dna)

    prev_cards = list(tool_context.state.get("current_cards") or [])
    merged_cards: list[dict[str, Any]] = []
    seen_card_ids: set[str] = set()
    for raw in [i.model_dump() for i in ranked] + prev_cards:
        cid = str(raw.get("id") or "")
        if cid and cid in seen_card_ids:
            continue
        if cid:
            seen_card_ids.add(cid)
        merged_cards.append(raw)
    tool_context.state["current_cards"] = merged_cards[:60]

    tool_context.state["ui_action"] = UIAction(
        type="swipe_deck",
        items=ranked,
        search_meta=SearchMeta(query=query, category=cat, max_budget_inr=max_budget_inr),
    ).model_dump()
    _persist_dna(tool_context, dna)

    return {
        "status": "ok",
        "category": cat,
        "count": len(ranked),
        "shown_in_swipe_deck": True,
        "items": [
            {
                "id": i.id,
                "name": i.name,
                "brand": i.brand,
                "price": i.price_text,
                "color": i.color,
                "match_score": i.match_score,
                "url_verified": i.url_verified,
                "image_source": i.image_source,
                "why_it_suits_you": i.why_it_suits_you,
                "styling_tip": i.styling_tip,
                "source": i.source_domain,
            }
            for i in ranked
        ],
    }


def _dedupe_looks(looks: list[OutfitLook], dna: StyleDNA, extra_exclude: list[str] | None = None) -> list[OutfitLook]:
    exclude_ids = set(dna.seen_look_ids) | set(extra_exclude or [])
    exclude_fps = set(dna.seen_look_fingerprints)
    out: list[OutfitLook] = []
    batch_fps: set[str] = set()
    for lk in looks:
        fp = look_fingerprint(lk)
        if lk.id in exclude_ids or (fp in exclude_fps and len(looks) > 1) or fp in batch_fps:
            continue
        batch_fps.add(fp)
        out.append(lk.model_copy(update={"look_fingerprint": fp}) if not lk.look_fingerprint else lk)
    return out or looks


async def search_looks_deck(
    occasion: str,
    dna: StyleDNA,
    vibe: str = "effortless modern",
    anchor_item: str = "",
    max_budget_inr: int | None = None,
    exclude_look_ids: list[str] | None = None,
) -> list[OutfitLook]:
    """Build a multi-look swipe deck using the active backend with fingerprint dedupe."""
    backend = _backend()
    combined_exclude = list(dict.fromkeys([*dna.seen_look_ids, *(exclude_look_ids or [])]))
    if hasattr(backend, "curate_outfit_deck"):
        looks = await backend.curate_outfit_deck(  # type: ignore[attr-defined]
            occasion=occasion,
            vibe=vibe,
            anchor_item=anchor_item,
            max_budget_inr=max_budget_inr,
            exclude_look_ids=combined_exclude,
            dna=dna,
        )
        if looks:
            return _dedupe_looks(looks, dna, exclude_look_ids)
    single = await backend.curate_outfit(
        occasion=occasion,
        vibe=vibe,
        anchor_item=anchor_item,
        max_budget_inr=max_budget_inr,
        dna=dna,
    )
    return _dedupe_looks([single], dna, exclude_look_ids)


async def stream_looks_deck(
    occasion: str,
    dna: StyleDNA,
    vibe: str = "effortless modern",
    anchor_item: str = "",
    max_budget_inr: int | None = None,
    exclude_look_ids: list[str] | None = None,
) -> AsyncIterator[OutfitLook]:
    """Stream validated & image-enriched looks incrementally over SSE."""
    backend = _backend()
    combined_exclude = list(dict.fromkeys([*dna.seen_look_ids, *(exclude_look_ids or [])]))
    seen_fps = set(dna.seen_look_fingerprints)
    if hasattr(backend, "stream_outfit_deck"):
        async for lk in backend.stream_outfit_deck(  # type: ignore[attr-defined]
            occasion=occasion,
            vibe=vibe,
            anchor_item=anchor_item,
            max_budget_inr=max_budget_inr,
            exclude_look_ids=combined_exclude,
            dna=dna,
        ):
            fp = look_fingerprint(lk)
            if fp not in seen_fps:
                seen_fps.add(fp)
                yield lk
        return
    looks = await search_looks_deck(
        occasion=occasion,
        dna=dna,
        vibe=vibe,
        anchor_item=anchor_item,
        max_budget_inr=max_budget_inr,
        exclude_look_ids=exclude_look_ids,
    )
    for lk in looks:
        yield lk


async def curate_outfit(
    occasion: str,
    tool_context: ToolContext,
    vibe: str = "effortless modern",
    anchor_item: str = "",
    max_budget_inr: int | None = None,
) -> dict[str, Any]:
    """Design a swipeable lookbook stack of head-to-toe OutfitLooks (Top, Bottom, Footwear, Accessory)
    for an occasion or anchor piece using color theory, proportion rules, Saved Closet, and live search.

    Args:
        occasion: Event or setting (e.g., 'rooftop date night', 'smart-casual office', 'jaipur wedding', 'weekend coffee').
        vibe: Aesthetic mood (e.g., 'quiet luxury', 'streetwear', 'minimalist', 'boho chic').
        anchor_item: Optional specific piece or saved closet item to style the outfit around.
        max_budget_inr: Optional total or per-piece budget hint in INR.
    """
    dna = _resolve_dna(tool_context)
    dna.declined = False
    looks = await search_looks_deck(
        occasion=occasion,
        dna=dna,
        vibe=vibe,
        anchor_item=anchor_item,
        max_budget_inr=max_budget_inr,
    )
    look = looks[0]
    tool_context.state["current_outfit"] = look.model_dump()
    tool_context.state["current_looks"] = [lk.model_dump() for lk in looks]
    tool_context.state["ui_action"] = UIAction(type="outfit_board", outfit=look, looks=looks).model_dump()
    _persist_dna(tool_context, dna)

    return {
        "status": "ok",
        "shown_in_outfit_board": True,
        "look_count": len(looks),
        "outfit": look.model_dump(),
    }


def record_style_preference(
    tool_context: ToolContext,
    shoe_size: str | None = None,
    top_size: str | None = None,
    bottom_size: str | None = None,
    liked_color: str | None = None,
    disliked_color: str | None = None,
    aesthetic: str | None = None,
    fit_preference: str | None = None,
    budget_max_inr: int | None = None,
    undertone: str | None = None,
    skin_tone: str | None = None,
) -> dict[str, Any]:
    """Save lasting user-stated style preferences into their Style DNA memory."""
    dna = _resolve_dna(tool_context)
    updated: list[str] = []

    for cat, val in (("shoes", shoe_size), ("tops", top_size), ("bottoms", bottom_size)):
        if val:
            dna.sizes[cat] = str(val).strip()
            _upsert_fact(dna, f"{cat}_size", str(val).strip(), "stated", singleton=True)
            updated.append(f"{cat} size {val}")

    if liked_color:
        c = liked_color.strip().lower()
        dna.disliked_colors = [x for x in dna.disliked_colors if x.lower() != c]
        if c not in dna.liked_colors:
            dna.liked_colors.append(c)
        _upsert_fact(dna, "liked_color", c, "stated", singleton=False)
        updated.append(f"likes {c}")

    if disliked_color:
        c = disliked_color.strip().lower()
        dna.liked_colors = [x for x in dna.liked_colors if x.lower() != c]
        if c not in dna.disliked_colors:
            dna.disliked_colors.append(c)
        _upsert_fact(dna, "disliked_color", c, "stated", singleton=False)
        updated.append(f"avoids {c}")

    if aesthetic:
        a = aesthetic.strip().lower()
        dna.aesthetics[a] = round(max(dna.aesthetics.get(a, 0.0), 4.0), 2)
        _upsert_fact(dna, "aesthetic", a, "stated", singleton=False)
        updated.append(f"aesthetic: {a}")

    if fit_preference:
        dna.fit_preference = fit_preference.strip().lower()
        _upsert_fact(dna, "fit_preference", dna.fit_preference, "stated", singleton=True)
        updated.append(f"fit: {dna.fit_preference}")

    if budget_max_inr is not None and budget_max_inr > 0:
        dna.budget_max = int(budget_max_inr)
        _upsert_fact(dna, "budget_max", f"₹{dna.budget_max:,}", "stated", singleton=True)
        updated.append(f"max budget ₹{dna.budget_max:,}")

    if skin_tone:
        dna.skin_tone = skin_tone.strip().lower()
        _upsert_fact(dna, "skin_tone", dna.skin_tone, "stated", singleton=True)
        updated.append(f"skin tone: {dna.skin_tone}")

    if undertone:
        dna.undertone = undertone.strip().lower()
        _upsert_fact(dna, "undertone", dna.undertone, "stated", singleton=True)
        season = infer_season(dna.skin_tone or "medium", dna.undertone)
        if season:
            dna.color_season = season
            _upsert_fact(dna, "color_season", season, "inferred", singleton=True)
        updated.append(f"undertone: {dna.undertone}")

    _persist_dna(tool_context, dna)
    return {"status": "saved", "updated": updated, "summary": summarize_dna_for_prompt(dna)}


def get_style_profile_and_closet(tool_context: ToolContext, open_closet_ui: bool = False) -> dict[str, Any]:
    """Read Style DNA summary, preference facts, swipe stats, and optionally open the Saved Closet panel in UI."""
    dna = _resolve_dna(tool_context)
    if open_closet_ui:
        tool_context.state["ui_action"] = UIAction(type="closet", items=dna.saved_closet).model_dump()
    likes = sum(1 for s in dna.swipe_history if s.direction in ("like", "super_like"))
    passes = sum(1 for s in dna.swipe_history if s.direction == "dislike")
    return {
        "status": "ok",
        "closet_opened": open_closet_ui,
        "summary": summarize_dna_for_prompt(dna),
        "facts": [f.model_dump() for f in dna.facts],
        "saved_closet": [
            {"id": i.id, "name": i.name, "brand": i.brand, "color": i.color, "price": i.price_text, "category": i.category}
            for i in dna.saved_closet
        ],
        "swipe_stats": {"liked": likes, "passed": passes},
    }


def compare_fashion_items(tool_context: ToolContext, item_indices_or_names: list[str] | None = None) -> dict[str, Any]:
    """Compare 2 to 3 items from the current Swipe Deck or Saved Closet side-by-side in the UI."""
    dna = _resolve_dna(tool_context)
    pool_raw = tool_context.state.get("current_cards") or []
    pool = [FashionItem.model_validate(x) for x in pool_raw] + list(dna.saved_closet)

    selected: list[FashionItem] = []
    if item_indices_or_names:
        for token in item_indices_or_names:
            t = str(token).strip().lower()
            if re.fullmatch(r"\d+", t):
                idx = int(t) - 1
                if 0 <= idx < len(pool) and pool[idx] not in selected:
                    selected.append(pool[idx])
            else:
                match = next((p for p in pool if t in p.name.lower() or t in p.brand.lower()), None)
                if match and match not in selected:
                    selected.append(match)
    if len(selected) < 2:
        selected = pool[:3]

    selected = selected[:3]
    if len(selected) >= 2:
        tool_context.state["ui_action"] = UIAction(type="compare", items=selected).model_dump()
    return {
        "status": "ok" if len(selected) >= 2 else "need_more_items",
        "items": [i.model_dump() for i in selected],
    }


def trigger_photo_stylist(tool_context: ToolContext, mode: str = "complexion") -> dict[str, Any]:
    """Open the consent-first Photo Studio in the UI for either 'complexion' (undertone/season)
    or 'outfit_check' (rate my outfit / match a piece)."""
    clean_mode = "outfit_check" if mode == "outfit_check" else "complexion"
    tool_context.state["ui_action"] = UIAction(type="request_photo", photo_mode=clean_mode).model_dump()
    return {"status": "ok", "photo_mode": clean_mode, "note": "User must consent and upload in the UI; photos are never saved."}


def forget_style_profile(tool_context: ToolContext) -> dict[str, Any]:
    """Request explicit UI confirmation to delete all saved Style DNA, swipes, closet, and complexion data.

    To protect against prompt injection from external web pages, autonomous chat/voice tool invocations ALWAYS
    open a UI confirmation modal rather than silently deleting user data immediately.
    """
    user_id = str(tool_context.state.get("user_id") or "default")
    if tool_context.state.get("allow_destructive_forget") is True:
        fresh = _STORE.forget(user_id)
        tool_context.state["allow_destructive_forget"] = False
        tool_context.state["style_dna"] = fresh.model_dump()
        tool_context.state["style_dna_summary"] = summarize_dna_for_prompt(fresh)
        tool_context.state["current_cards"] = []
        tool_context.state["ui_action"] = UIAction(type="none").model_dump()
        return {"status": "forgotten"}

    tool_context.state["ui_action"] = UIAction(type="confirm_forget").model_dump()
    return {
        "status": "confirmation_required",
        "message": "Opened confirmation prompt in the UI — profile will only be cleared once the user clicks confirm.",
    }


def set_shopping_boundary(tool_context: ToolContext, declined: bool) -> dict[str, Any]:
    """Set or clear the user's 'no thanks / stop pitching' boundary so we respect a no."""
    dna = _resolve_dna(tool_context)
    dna.declined = bool(declined)
    _persist_dna(tool_context, dna)
    return {"status": "ok", "declined": dna.declined}
