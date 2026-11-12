# Aura Deck Fixes: Validated Plan (for the coding agent)

Scope: (1) one unified, image-first swipe card for items and looks, (2) 10-15 items per search instead of 5, (3) "Find more like my likes" must keep the category and never repeat items.

Files reviewed: `tools.py`, `media.py`, `prompts.py`, `SwipeDeck.tsx`, `LookDeck.tsx`, `ProductPanel.tsx`, `useShopper.ts` (partly truncated). Not yet reviewed, so confirm before editing: `schemas.py`, `memory.py`, `main.py`, `offline.py`, `lib/types.ts`, `lib/api.ts`, `lib/stream.ts`, `Thumb.tsx`.

## 0. Verdict on the first plan

All four root causes are confirmed in code. The plan's fixes are right in direction but miss these:

| Gap in first plan | What the code shows |
|---|---|
| Item cap lives in more places than listed | `CARD_EXTRACTOR_INSTRUCTION` (prompts.py) says "Extract 4 to 6" and `_wrap_untrusted_web` truncates `grounding_links[:18]`, in addition to the prompt, `[:6]` slice and `offline.py` |
| Images will go missing at 12-15 items | `enrich_item_images(max_gen=4)` only AI-generates for the first 4 items; items 5+ with no retailer image get **no image at all** |
| Latency will balloon | One `_FETCH_SEMAPHORE(4)` is held during page fetch + vision check + up to 9s AI generation, so 15 items run in about 4 serial waves |
| "Find more" will return repeats | `search_fashion_online` has no exclusion and the search cache key has no exclusion, so the same query can return the cached 5 items |
| Fixing the prompt text is fragile | The LLM picks `category` itself (default `"apparel"`), so a longer prompt can still drift. Looks already avoid this by calling a direct endpoint with `exclude_look_ids`; items should do the same |
| Gesture meaning differs between decks | `SwipeDeck` up = "Style This" (super_like); `LookDeck` up = Buy. `prompts.py` also still tells users "swipe up (build an outfit)" |
| Append would reset the deck | `SwipeDeck` resets index on `[items]`; `LookDeck` resets on a joined-id `batchKey`. Appending more cards would restart at card 1 |

## 1. Findings (code locations)

1. **Two UIs**: `curate_outfit` -> `ui_action=outfit_board` -> `LookDeck` (framer-motion, up = buy). `search_fashion_online` -> `swipe_deck` -> `SwipeDeck` (hand-rolled pointer drag, text-heavy, up = style).
2. **Why only 5**: tools.py `"Find 5-6 real..."` and `batch.items[:6]`; prompts.py `WEB_FINDER_INSTRUCTION` ("5-6") and `CARD_EXTRACTOR_INSTRUCTION` ("4 to 6"); offline.py `pool[:5]`.
3. **Why shoes -> hoodie**: `ProductPanel.tsx` `onFindMore` sends `"Find more pieces online inspired by what I just liked!"`; no category, no exclusions, routed through the LLM.
4. **Why Puma shows "AI visualization"**: items without a verified grounding URL skip `fetch_page_image` and fall to AI generation. Expect more of this at higher counts.
5. **Possible existing bug**: images are stored as `signed_media_url(..., ttl_seconds=3600)` but search results are cached for `config.SEARCH_CACHE_TTL_SEC`. If that TTL exceeds 3600s, cached items return expired image URLs. Either keep the cache TTL under 3600s or re-sign URLs when reading from cache.
6. **Dead branch**: in `LookDeck.commit`, both sides of `if (action !== "buy_intent")` do the same thing. Harmless; simplify.

## 2. Backend fixes

### B1. Candidate and deck sizes (config, not magic numbers)
Add to `app/config.py`: `ITEM_CANDIDATES = 20`, `ITEM_DECK_MIN = 10`, `ITEM_DECK_MAX = 15`.

Change all of these together:
- `tools.py` search prompt: `"Find {ITEM_CANDIDATES} distinct ..."` per the multi-angle rule below.
- `tools.py`: replace `batch.items[:6]` with `batch.items[:ITEM_CANDIDATES + 4]`.
- `prompts.py`: `WEB_FINDER_INSTRUCTION` ("5-6" -> "8-10 distinct items per request"), `CARD_EXTRACTOR_INSTRUCTION` ("4 to 6" -> "up to 24 distinct items; never invent items to reach a count").
- `_wrap_untrusted_web`: `grounding_links[:18]` -> `[:40]`.
- `offline.py`: expand pools to 12+ items per category and return `pool[:limit]`.

### B2. Multi-angle search (one grounded call will not give 20 good items)
In `LiveGoogleSearchBackend.search`, run 2 grounded searches in parallel and merge:

```python
_ANGLES = (
    "best-selling mainstream options from major retailers",
    "different brands and price tiers than the obvious picks (include budget and premium)",
)

async def _multi_search(self, base_prompt: str, per_angle: int = 10):
    results = await asyncio.gather(
        *(self._run_google_search(f"{base_prompt}\nFocus: {a}. Find {per_angle} distinct items.") for a in _ANGLES),
        return_exceptions=True,
    )
    findings, links, seen = [], [], set()
    for r in results:
        if isinstance(r, Exception):
            continue
        text, lks = r
        findings.append(text)
        for l in lks:
            if l["url"] not in seen:
                seen.add(l["url"]); links.append(l)
    if not findings:
        raise RuntimeError("all grounded searches failed")
    return "\n\n".join(findings), links
```
Then one extraction call on the merged text, as today.

### B3. Image pipeline for 15-20 items
In `media.py`:
- Split semaphores: `_FETCH_SEM = Semaphore(8)` for page fetch/download/vision, `_GEN_SEM = Semaphore(2)` for AI generation. Do not hold the fetch semaphore while generating.
- Add `enrich_item_stream(items)` using `asyncio.as_completed` (same pattern as `enrich_look_deck_stream`) so cards can appear as they finish.
- Order candidates by `rerank_items` **before** enrichment so the AI-generation budget (`max_gen`, keep about 4) goes to the best matches, not to list position.
- After enrichment, **drop items with no image** (the UI is image-first, a blank card is worse than a missing card). Keep order: retailer image first, AI-generated after.
- Keep the final list at `ITEM_DECK_MAX`; if fewer than `ITEM_DECK_MIN` survive, return what exists. Never pad.
- AI-generated items must not show a plain "Buy". Show "AI visualization" and only "View store" if `url_verified`.

### B4. Pool cache + pagination + exclusion (fixes repeats and saves LLM calls)
Cache the **candidate pool**, not the first page:

```python
pool_key = f"pool:{query.lower()}:{category}:{budget}:{pref_hash(dna)}"
# 1. read pool (or build: multi-search -> extract -> rank -> enrich -> drop imageless)
# 2. page = [i for i in pool if i.id not in exclude_ids][:limit]
# 3. if len(page) < ITEM_DECK_MIN: run one more search with
#    "Different from these (do not repeat): <names of excluded + shown>", merge into pool, re-page
```
Add to the backend and tool signatures with defaults so tests and the offline backend keep working:
`search(..., exclude_ids: set[str] | None = None, limit: int = ITEM_DECK_MAX)`.

Stable identity: `_stable_id(brand, name)` is stable for identical strings, but the model may rephrase. Add `_item_key(i) = re.sub(r"[^a-z0-9]+", "", f"{i.brand}{i.name}".lower())` and dedupe on that and on verified URL.

### B5. `search_fashion_online` returns search metadata
- Make `category` an explicit enum-like set and normalize unknown values to `"apparel"`.
- Add `exclude_item_ids: list[str] | None = None` and `limit`.
- Put `search_meta = {query, category, max_budget_inr}` into the `UIAction` for `swipe_deck` (add the field in `schemas.py` and `lib/types.ts`).
- Persist shown item ids per user (same mechanism as `seen_look_ids`) so exclusions survive reloads.
- Update `current_cards` to the union of previous and new items so `compare_fashion_items` still works.

### B6. Direct item search endpoint (mirrors `/looks/search`)
Add `POST /items/search` (JSON first; SSE streaming later using `enrich_item_stream`):
`{session_id, user_id, query, category, max_budget_inr, exclude_item_ids}` -> `{items, style_dna}`.
"Find more" and prefetch use this endpoint and **bypass the LLM agent entirely**.

### B7. `prompts.py`
- Rule 1: replace "swipe up (build an outfit around it)" with "swipe up to buy".
- Rule 2: "5-look Swipe Stack" -> "swipe stack of looks".
- Add: "If the user asks for more of what they just browsed, keep the same category as the current deck; the UI handles this directly."
- Fix duplicate numbering (two rules are numbered 4).

## 3. Frontend fixes

### F1. One shared swipe engine
Extract the gesture/stack logic from `LookDeck.tsx` into `components/SwipeStack.tsx`:

```tsx
interface SwipeStackProps<T> {
  items: T[];
  getKey: (item: T) => string;
  deckId: string;                    // reset index ONLY when this changes, not when items are appended
  renderFront: (item: T, ctl: { expanded: boolean; toggle: () => void }) => React.ReactNode;
  renderInfo: (item: T, ctl: { toggle: () => void }) => React.ReactNode;
  onCommit: (item: T, action: "save" | "skip" | "buy") => void;
  onUndo?: () => void;
  onNeedMore?: () => void;           // fire once when <= 3 cards remain
  empty: React.ReactNode;
}
```
Keep: framer-motion drag, stamps (SAVE / SKIP / BUY), 4 buttons (Skip, Info, Buy, Save), keyboard (left/right/up/Esc), undo, haptics, preload next 3 images.
`LookDeck` becomes a thin wrapper with a `LookFront` / `LookInfo` renderer. Delete `SwipeDeck.tsx`'s custom pointer code.

### F2. `ItemFront` (image-first card)
- Full-bleed image (`object-cover`, `onError` -> gradient fallback like `LookCard`).
- Overlay only: brand, one-line name, price pill, and a small "AI visualization" badge when `image_source === "ai_generated"`.
- Remove the "99% MATCH" badge (false precision).
- No tags, match reasons, "why it suits you", style tip or store links on the front.

### F3. `ItemInfo` (back face, via Info button / tap)
Holds everything removed from the front: tags, `match_reasons`, `why_it_suits_you`, `styling_tip`, store, "Full details", **Ask Aura**, **Style This** (calls `onStyleAround`; no longer a swipe).

### F4. Actions and gesture mapping (items)
- Right/Save -> `shopper.swipe(item, "like")`; Left/Skip -> `"dislike"`.
- Up/Buy -> open an item BuySheet (same pattern as the look BuySheet) with store, price and **Shop** link; log as `"like"` for now (add a `buy_intent` direction to `apply_swipe` later).
- If `image_source === "ai_generated"` and URL not verified: sheet says "Find online" instead of "Buy".
- Undo: mirror `undoSwipeLook`.

### F5. `useShopper.ts`
- Store `lastItemSearch` from `search_meta` when a `swipe_deck` action arrives; set `deckId` there.
- Add `searchMoreItems()`:

```ts
const searchMoreItems = useCallback(async () => {
  if (!ids || !lastItemSearch || busy.current) return;
  busy.current = true; setThinking(true);
  try {
    const exclude = deckItems.map(i => i.id);
    const out = await api.searchItems(ids, { ...lastItemSearch, excludeItemIds: exclude });
    const fresh = out.items.filter(i => !exclude.includes(i.id));
    if (fresh.length) {
      const merged = [...deckItems, ...fresh];
      setDeckItems(merged);
      setPanel({ kind: "swipe_deck", items: merged });   // same deckId: index is preserved
    } else {
      addMessage("bot", "That's everything I found for now. Want to try a different search?");
    }
    if (out.style_dna) updateDna(out.style_dna);
  } catch (e) { addMessage("err", errorText(e)); }
  finally { setThinking(false); busy.current = false; }
}, [ids, lastItemSearch, deckItems, updateDna, addMessage]);
```
- Expose `searchMoreItems` in the returned object.

### F6. `ProductPanel.tsx`
- `onFindMore={() => void shopper.searchMoreItems()}` (remove the hardcoded chat prompt).
- Pass `onNeedMore={() => void shopper.searchMoreItems()}` (guarded once per batch inside `SwipeStack`).
- Keep "Grid view"; keep `ProductGrid` as is.

### F7. Fix batch resets
`LookDeck`'s `batchKey` should come from a stable `deckId`, not joined ids, otherwise streamed looks reset the index and progressive append breaks.

## 4. Tests

Backend (`tests/test_adk_tools.py`, use `set_search_backend` with a fake that records arguments):
1. `test_item_search_returns_10_to_15_with_images`: fake pool of 20 (6 imageless) -> result length between 10 and 15, all have `image_url`.
2. `test_find_more_keeps_category_and_excludes_seen`: search shoes, then call more with `exclude_item_ids`; assert category is `shoes` for every item and no overlap.
3. `test_pool_pagination_reuses_cache`: second page with a counting fake performs zero new LLM/search calls while the pool has unseen items.
4. `test_unknown_category_normalized`.
5. `test_cached_items_have_valid_media_urls` (guards finding 5).

Frontend (`SwipeStack.test.tsx`, `ItemFront.test.tsx`):
1. Right/left/up produce `save`/`skip`/`buy` via drag, buttons and keys.
2. Appending items with the same `deckId` keeps the current index.
3. `onNeedMore` fires exactly once when 3 cards remain.
4. Front face renders image + name + price only (no tags/tips).

Then run: `ruff check .`, `pytest -q`, `npm run typecheck`, `npm test`, `npm run build`.

## 5. Order of work
1. B1 + B7 (counts, prompt text). Fast visible win.
2. B4 + B5 + B6 + F5 + F6 (category-safe, repeat-free "Find more"). Fixes the shoes -> hoodie bug for real.
3. F1-F4, F7 (unified card).
4. B2 + B3 (multi-angle search, image pipeline, streaming).
5. Tests throughout.

## 6. Acceptance criteria
- "shoes" returns 10-15 cards, every one with an image, in under about 15 seconds to the first card.
- After swiping the deck, "Find more like my likes" returns more **shoes**, none already shown.
- Item deck and look deck look and behave the same: image-first, same 4 buttons, same gestures (right save, left skip, up buy).
- No text block under the image; details only in Info.
- Appending more cards never resets the user to card 1.
- AI-generated images are labeled and never present a plain Buy.
