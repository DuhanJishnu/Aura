# Architecture

## One turn, step by step

1. **Fast path** (`app/llm/fastpath.py`): exact, unambiguous messages ("9", "sports shoes", "for me", "hi", "yes" at a
   confirmation, "buy this", "compare the first and third") become structured fields with no LLM call.
2. **Parse**: otherwise Gemini turns the message into an `Extraction` (intent, use, size, budget, category, product position...).
   A malformed answer is retried once; a second failure produces a polite "say it again", never a crash.
3. **Signals and names** (`signals.py`, `resolve.py`): deterministic backstops add only what the shopper plainly said: an exact
   budget, a fit or durability question, "I'll take it", an explicit "no thanks", "just browsing, thanks" (a brush-off), a
   category word. A shoe named by brand, color or quoted price is mapped to its position on screen; same-name shoes are told
   apart by price or by the shoe the assistant just recommended; otherwise the engine asks.
4. **Policy** (`policy/rules.py`): a rule table maps the situation (intent, whether a no is in force, what is awaiting
   confirmation, what is on screen, what is missing) to one action. First match wins; the rule name is returned in the
   response so behavior can be inspected and evaluated.
5. **Action**: search, opinion, compare, objection, browse, cart, checkout, profile, complexion. Facts come from SQLite.
   `on_ui` fires as soon as the products to show are known.
6. **Wording**: only replies that carry content are worded by the LLM (plain questions, "no" replies and all money actions are
   fixed text). Opinions, comparisons and objection answers go through the **grounding validator**: regenerate once, strip
   unsupported sentences, fall back to a reply built from the data.
7. **Response**: `{reply, slots, ui_action, policy}`. Streaming sends `ui` (the panel) first, then `text`, then `done`.

## Design decisions worth knowing

- **Python decides, the LLM words.** Predictable behavior, cheaper calls, and a stable surface to test: 251 tests run with
  a fake LLM and no network.
- **A "no" is a state, not a message.** It stays in force until the shopper re-engages with shopping content; the same words
  mean different things before and after it.
- **Money actions are templates.** A model can be wrong about a price; the order total never is.
- **The validator beats streaming raw tokens.** Showing unvalidated model text would defeat grounding, so the latency win comes
  from ordering (panel first), fewer LLM calls and lower thinking, not from raw token streaming.
- **Categories share one engine.** Apparel sizes are stored as 1-6 (XS-XXL) and accessories as size 0 ("one size"); the
  product's own category decides how a size is asked for, shown and saved. Only shoe sizes are saved to the profile.
- **Evaluation is part of the product.** Every real run found bugs that unit tests with a fake LLM could not: see the log.

## Frontend (`web/`)

Next.js (App Router, TypeScript) with Tailwind. The browser only talks to its own origin: `app/api/[...path]/route.ts` proxies to
`BACKEND_URL` and streams the body through, which is what lets server-sent events work (and means no CORS). State lives in one
hook, `hooks/useShopper.ts` (chat, panel view, cart, profile, photo flow); `lib/stream.ts` reads the event stream and calls
`onUi` the moment the products are known, so the grid loads while the sentence is still arriving. `hooks/useSpeech.ts` wraps the
browser's speech recognition and synthesis. Components are small and presentational (`ProductDetail`, `CartDrawer`...), which
is what the 29 Vitest tests exercise, along with the stream client, the proxy route and the main hook (against a fake backend).
`frontend/` (plain JavaScript, served by FastAPI) is kept as a dependency-free fallback.

## State and persistence

SQLite (`data/shop.db`): `shoes` (all categories; the historical table name), `stock`, `orders`, `order_items`, `profiles`,
`profile_facts`. Conversations (slots, shortlist, cart, pending confirmation) are in memory, bounded by `MAX_SESSIONS`, with
a lock per conversation. A catalog built before categories existed is migrated on start (the new column defaults to shoes).

## Privacy

The complexion flow needs explicit consent per photo, estimates are shown for confirmation or correction, the photo exists only
inside the request (not on disk, in the database or in the session; a test checks the session), and only confirmed results are
saved. "Forget my profile" deletes the saved size and preferences. Voice recognition is done by the browser's speech service.
