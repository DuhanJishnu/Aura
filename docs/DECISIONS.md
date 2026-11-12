# Architecture Decision Records (ADRs)

## ADR-001: Replace Custom Rule Table & SQLite Engine with Google ADK
- **Context**: The previous system used a custom regex/extraction pipeline, a deterministic rule table (`app/policy/rules.py`), and a 450-item synthetic SQLite catalog (`data/shop.db`). While predictable for a toy shoe store, a fixed database cannot keep up with real fashion trends, brands, or full-outfit styling.
- **Decision**: Migrate the entire agent core to **Google ADK (`google-adk`)** exposing `root_agent` (`aura_stylist`), `Runner`, `InMemorySessionService`, `InMemoryMemoryService`, and `FunctionTool`s.
- **Consequences**: Native compatibility with `adk web`, `adk run`, `adk eval`, and `Runner.run_live()`; cleaner multi-turn tool calling and easier extensibility. Deterministic guarantees (like URL verification, swipe exclusion, and UI state updates) live inside the Python tools rather than in a rigid intent router.

## ADR-002: Remove Database Completely; Use In-Memory + JSON + `localStorage` Sync
- **Context**: The user requested removing all database dependencies and keeping hosting 100% free (paying only for Gemini API).
- **Decision**: Removed SQLite (`data/shop.db`, `app/catalog/`). User preferences, Swipe History, and Saved Closet live in `StyleDNA` via `PreferenceStore` (in-memory + optional local JSON) backed by browser `localStorage` sync (`POST /profile/sync`).
- **Consequences**: Zero database cost, zero migrations, and instant portability to stateless free-tier containers (Render Free, Hugging Face Spaces, Fly.io). Trade-off: multi-device cross-browser login is out of scope unless auth + cloud store are added later.

## ADR-003: Isolate `google_search` in a Sub-Runner Inside `search_fashion_online`
- **Context**: Gemini API restricts combining native `google_search` with custom `FunctionTool` schemas on the same LLM call unless wrapped via `AgentTool` or `bypass_multi_tools_limit`, and raw search text alone does not populate structured Swipe Deck cards.
- **Decision**: Run a dedicated ADK `web_fashion_finder` agent (`tools=[google_search]`) inside `search_fashion_online`, extract `grounding_metadata.grounding_chunks`, structure cards via `response_schema=_CardBatch`, and re-rank by `StyleDNA`.
- **Consequences**: Every search returns both real grounded URLs (`url_verified=True` when matched) AND structured Swipe Deck cards written directly to `tool_context.state["ui_action"]`.

## ADR-004: Gemini Live API (`StreamingMode.BIDI`) + Web Speech Fallback over OpenRouter Voice
- **Context**: User wants real-time conversational voice while paying only for the Gemini API.
- **Decision**: Use Google ADK's `Runner.run_live()` with `StreamingMode.BIDI` and `gemini-2.5-flash-native-audio-preview-12-2025` over FastAPI WebSockets, with the browser Web Speech API (`useSpeech.ts`) retained as a zero-cost fallback.
- **Consequences**: True full-duplex native speech-to-speech with barge-in and live tool UI updates using the same `GEMINI_API_KEY` — zero third-party voice fees.

## ADR-005: Tinder/Instagram Swipe Deck as Primary Discovery UX
- **Context**: Static product grids collect weak implicit preference signals; fashion taste is visual and iterative.
- **Decision**: Render search results in an interactive `SwipeDeck` (`←` Pass, `→` Like/Save, `↑` Style Outfit Around This) backed by `POST /swipe` -> `apply_swipe()` & `rerank_items()`.
- **Consequences**: Every swipe immediately updates `StyleDNA` (aesthetic tag weights, color affinities, brand preferences, and exclusion list), measurably improving subsequent searches and outfit curations.
