# Implementation Plan: Google ADK AI Fashion Stylist

## Objective
Replace the SQLite catalog + deterministic rule-table engine with a **Google ADK (`google-adk`)** multi-agent AI Fashion Stylist that:
1. Discovers real, buyable items online via Google Search grounding (`google_search`) — **zero database required**.
2. Acts as an expert personal stylist & fashion-savvy best friend (color theory, silhouettes, head-to-toe outfit curation, seasonal undertones, wardrobe photo checks).
3. Learns continuously from **Tinder/Instagram-style swipes** (Like / Pass / Super-Like) and explicit preferences stored in **Style DNA** memory (server JSON + browser `localStorage` sync for free stateless hosting).
4. Supports **real-time bidirectional voice** via **Gemini Live API** (`Runner.run_live` + `StreamingMode.BIDI` WebSocket) with browser Web Speech API fallback.
5. Preserves the **friend-first + fashion circle-back** behavior on off-topic queries and strict **"no means no"** boundary respect.
6. Includes **ADK native evaluations (`AgentEvaluator`) + custom stylist rubric evals**, complete prompting & ADR documentation, and **100% free-tier deployment** (paying only for Gemini API).

---

## Phase 1 — Cleanup & Foundation
- Remove SQLite database layer and legacy rule-table engine:
  - `app/catalog/`, `app/engine/`, `app/policy/`, `app/llm/`, `app/validators.py`, `data/seed.py`, `data/shop.db`.
- Update `requirements.txt` and `requirements-dev.txt` with `google-adk>=2.14.0`, `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, `websockets`.
- Update `app/config.py` and `.env.example` for `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_LIVE_MODEL`, `GEMINI_THINKING`, `ALLOWED_ORIGINS`, `RATE_LIMIT_PER_MIN`.

## Phase 2 — Google ADK Agent Architecture (`stylist_agent/`)
- `stylist_agent/schemas.py`: `FashionItem`, `OutfitPiece`, `OutfitLook`, `StyleDNA`, `SwipeRequest`, `UIAction`, `ChatResponse`, `ComplexionEstimate`, `OutfitCheckResult`.
- `stylist_agent/memory.py`:
  - `StyleDNA` preference model (aesthetics affinity map, liked/avoided colors, sizes, budget comfort range, seasonal color palette, liked/saved closet items, disliked items, swipe history, fact provenance).
  - `PreferenceStore` (in-memory + lightweight optional JSON file cache + client-sync).
  - `apply_swipe()` and `rerank_items()` to directly improve future search ranking and outfit suggestions from swipes.
- `stylist_agent/prompts.py`:
  - Modular prompts with few-shot behavioral anchors:
    - `STYLIST_ORCHESTRATOR_INSTRUCTION` (stylist expertise, friend warmth, off-topic fashion circle-back, no-means-no boundary, grounded link discipline).
    - `WEB_FINDER_INSTRUCTION` (online retail search query formulation & grounded extraction).
    - `OUTFIT_ARCHITECT_INSTRUCTION` (rule-of-thirds proportions, 60-30-10 color harmony, occasion fit).
    - `COMPLEXION_PROMPT` & `OUTFIT_CHECK_PROMPT` (consent-gated vision prompts).
- `stylist_agent/tools.py`:
  - `search_fashion_online`: runs dedicated ADK `web_fashion_finder` agent with `google_search`, captures `grounding_metadata.grounding_chunks` for real URLs, structures `FashionItem` cards, filters out passed items, re-ranks via `StyleDNA`, and writes `ui_action = swipe_deck` to `tool_context.state`.
  - `curate_outfit`: builds head-to-toe `OutfitLook` combining saved closet pieces + live online search, writes `ui_action = outfit_board` to `tool_context.state`.
  - `record_style_preference`, `get_style_profile_and_closet`, `compare_fashion_items`, `open_saved_closet`, `trigger_photo_stylist`.
- `stylist_agent/agent.py`:
  - Exposes `root_agent` (`Agent` / `LlmAgent`) + `web_fashion_finder` + `create_runner(session_service, memory_service)` for ADK CLI (`adk run`, `adk web`, `adk eval`) and FastAPI.

## Phase 3 — FastAPI Backend, SSE Streaming & Gemini Live Voice (`app/`)
- `app/service.py`:
  - Wraps ADK `Runner` (`InMemorySessionService` + `InMemoryMemoryService`).
  - Streams SSE events (`status`, `ui`, `text`, `done`) as soon as ADK tool calls populate `state["ui_action"]`.
  - Implements `run_live_session()` using `Runner.run_live(..., RunConfig(streaming_mode=StreamingMode.BIDI, response_modalities=["AUDIO"], ...))` over WebSocket.
  - Consent-first photo analysis (`complexion` + `outfit_check`), zero image persistence.
- `app/main.py`:
  - Endpoints: `/health`, `/ready`, `/chat`, `/chat/stream`, `/ws/live/{user_id}/{session_id}`, `/swipe`, `/profile`, `/profile/sync`, `/profile/forget`, `/closet/{item_id}`, `/complexion/*`, `/outfit-check/analyze`.
- `scripts/serve_fake.py`: Key-less demo mode for offline UI testing.

## Phase 4 — Next.js Frontend: Swipe Deck, Outfit Board, Closet, Photo Studio & Live Voice (`web/`)
- `SwipeDeck.tsx`: Tinder/Instagram drag-to-swipe card stack (`←` Pass, `→` Like & Save, `↑` Style Outfit Around This), keyboard shortcuts, retailer links, and post-deck summary.
- `OutfitBoard.tsx`: Head-to-toe lookbook card with piece breakdown, color harmony & proportion notes, and quick online search per piece.
- `ClosetView.tsx`: Saved swiped items & looks with "Style an outfit from my closet".
- `ComparePanel.tsx`, `ProductGrid.tsx`, `ProductDetail.tsx`: Updated for online `FashionItem` schema.
- `PhotoFlow.tsx`: Complexion & Seasonal Color Analysis + "Rate My Outfit / Match This Piece".
- `ProfileDrawer.tsx`: Visualizes `StyleDNA` (aesthetics, color swatches, swipe counts, sizes, budget) + Forget button.
- `hooks/useLiveVoice.ts` + `hooks/useSpeech.ts`: Gemini Live bidirectional PCM audio hook (AudioWorklet/ScriptProcessor 16kHz mic -> WS -> 24kHz speaker playback with barge-in) + Web Speech API fallback.
- `hooks/useShopper.ts`: Unified state + `localStorage` StyleDNA/Closet sync.

## Phase 5 — Evaluation Harness & Tests (`eval/` + `tests/`)
- `eval/adk_eval/stylist.evalset.json` + `eval/adk_eval/test_config.json`: Native ADK `AgentEvaluator` evalset.
- `eval/run.py`: Offline + live comparison (`plain` baseline vs `adk_stylist`) measuring:
  - Fashion styling quality & preference adaptation after swipes
  - Off-topic warm answer + fashion circle-back rate
  - "No means no" boundary compliance
  - Grounded search/link integrity (0 fabricated URLs)
  - ADK tool-call accuracy
- `tests/`: Comprehensive backend `pytest` suite (no API key needed) + frontend `vitest` suite.

## Phase 6 — Documentation & Free-Tier Deployment Configs
- `docs/ARCHITECTURE.md`, `docs/PROMPTING.md`, `docs/EVALUATION.md`, `docs/DECISIONS.md`, `docs/DEPLOYMENT.md`, `README.md`.
- Free deployment templates: `Dockerfile`, `render.yaml`, `docker-compose.yml`, Vercel + Render / Hugging Face Spaces guide.
