# Development log

The chronological record of how Shopper was built: per-phase notes, the four real evaluation runs, and every bug they
exposed. The current README is the place to start; this file is the "why is it like this" history.

# Shopper — conversational shopping agent (Jarvis-style)

A chat agent that talks like a friendly salesperson, drives a product panel from the
conversation, gives honest grounded opinions, and takes the user to checkout.

**Core rule:** Python decides *what to do next* (missing slot, retrieve or not). The LLM handles
understanding and wording.

## Run
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m data.seed          # builds data/shop.db with 300 synthetic shoes
pytest
export GEMINI_API_KEY=...   # optional GEMINI_MODEL, see .env.example
uvicorn app.main:app --reload
```

## Chat API contract
```json
{"reply": "...", "slots": {...}, "ui_action": {"type": "show_products", "filters": {...}}}
```
Actions: `show_products`, `focus_product`, `add_to_cart`, `checkout`, `none`.

## Spec: the Jarvis flow
greet → category → who it's for / size → use type → browse → opinion → buy.
Saved profile size is used if present; someone else's size is session-only.
One question at a time; several slots accepted in one message.

## Demo scenarios
1. **Happy path:** "hi" → sports shoes → size 9 → browse → ask opinion → buy.
2. **Size up front:** "sports shoes, size 9" skips straight to results.
3. **Shopping for someone else:** size is session-only, profile untouched.
4. **Change of mind:** "actually office shoes" updates filters, no restart.
5. **Off-topic question:** answer briefly, don't hijack, offer to continue.
6. **"No thanks":** back off and don't re-pitch.
7. **Out of stock:** say so honestly, suggest nearest size or alternatives.
8. **Price objection:** respond with evidence and cheaper alternatives.

## Status
- [x] Phase 0: repo, spec, scenarios
- [x] Phase 1: catalog, search, tests (embeddings still to add)
- [x] Phase 2: conversation engine (Gemini via google-genai; set GEMINI_API_KEY)
- [x] Phase 3: frontend (chat + product panel + cart drawer) served at `/`
- [x] Phase 4: opinion mode, grounding validator, refinement, server cart, mock checkout, saved size (MVP)
- [x] Phase 5: salesperson intelligence (rule-based policy; Jev experiment not built)

## How Phase 4 behaves
- **Opinions** send only that product's DB row plus computed context (price vs category average,
  rating vs average, whether your size is in stock) to Gemini. Replies pass `app/validators.py`
  (prices, ratings, brands, colors, sizes must match the DB); bad sentences trigger one regenerate,
  then get stripped, then a data-built fallback is used.
- **Cart, checkout and order confirmation** replies are fixed templates, never free LLM text.
  "Buy this" adds to the cart and asks for confirmation; the order is placed only on "place order"
  or the Place order button. Checkout re-checks stock, decrements it and records the order.
- **Refinement:** "cheaper" (budget x0.8), "other colors", "show more" update filters, no restart.
- **Saved size** is written only after buying for yourself; gift sizes stay session-only.
- API additions: `GET /products?ids=`, `/cart`, `/cart/add`, `/cart/remove`, `/checkout`, `/orders/{id}`;
  `ui_action` gained `product_ids` and `order_id`; `ChatRequest` gained `user_id`, `focus_product_id`.

## Phase 5: the decision policy (`app/policy/rules.py`)
First matching rule wins; every reply reports `policy: {action, rule}` so behavior can be inspected and evaluated.

| # | Rule | Situation | Action |
|---|---|---|---|
| 1 | no_means_no | explicit "no thanks / never mind" (beats anything else in the message) | respect the no: back off, no question |
| 2 | answer_off_topic | unrelated question | answer briefly, change nothing |
| 3 | passive_after_no | after a no, small talk ("ok", "hi", "yes") | quiet reply, no question, no products |
| 4 | confirm_order | "yes / place order" while an order is awaiting confirmation | place the mock order |
| 5 | reject_item | "not this one" | drop that shoe, no pitch |
| 6 | opinion | asks what you think | grounded, honest opinion |
| 7 | focus | "show me the second one" | open that shoe |
| 8 | compare | "compare the first and third" | side-by-side table + plain trade-offs |
| 9 | objection | price / fit / quality concern | evidence, cheaper in-size alternatives, or an honest "I don't have that" |
| 10 | just_looking | "just browsing, thanks" with no request | stay quiet, show nothing, say the door is open (no offer after a no) |
| 10b | browse | "I'm bored", "surprise me", "show me something" | relaxed best-rated picks across styles, no questions, no size |
| 11-12 | cart / cart_remove | buy, add, remove | templated cart actions |
| 13 | resume_pending_cart | size just arrived for a waiting cart add | finish the add |
| 14 | refine | cheaper / other colors / show more | update filters |
| 15-16 | greet / clarify_missing | start, or a slot is missing | ask exactly one question |
| 17 | retrieve | enough info | search and show |

A "no" stays in force until the user re-engages with shopping content (a use, size, budget, a product
question, browsing, etc.). Off-topic questions are still answered while a no is in force.

Objection handling: **price** shows the shoe's price versus the category average plus up to 3 cheaper
alternatives in the same use and size (or says it is already among the cheapest); **fit** is a fixed template
that admits there is no fit data and lists in-stock sizes; **quality** admits there is no durability data.
- [x] Phase 6: style profile and complexion flow
- [x] Phase 7: evaluation harness (real results need your API key)

## Phase 6: profile and complexion
- **Profile** (`app/profile/`): size, budget range, style, liked/avoided colors, undertone, skin tone. Every fact
  carries its source: `stated` (you said it), `confirmed` (you confirmed an estimate) or `inferred` (a guess, e.g. a
  color from something you bought; used with less weight, labelled as a guess, never overwrites a stated fact).
  "What do you know about me" lists everything; "I don't like black" corrects a guess.
- **Complexion flow:** explicit consent in chat or via a button (covers exactly one photo) -> upload ->
  Gemini vision estimates skin tone and undertone -> you confirm or correct -> only the confirmed result is
  saved. The photo exists only inside the request: it is not written to disk, the database or the session
  (a test checks this). You can skip the photo and just say "I have a warm undertone".
- **Ranking:** the confirmed undertone maps to a palette (`app/profile/ranking.py`), liked colors add, avoided colors
  sink, budget range adds a little. It re-ranks the top 30 matches and shows 6; nothing is hidden. Replies explain
  the reason in soft wording ("tends to complement warm undertones"), only naming colors actually on screen.
  The palettes are a general styling heuristic, not a fact about anyone, and the reply says so when saving.
- **Forget my profile:** a chat command (works even after a "no") and a button; deletes the saved size,
  preferences and complexion.
- New rules in the policy table: forget_profile, show_profile, update_profile (all work after a no and never pitch),
  grant_consent, confirm_complexion, complexion.
- New endpoints: `GET /profile`, `POST /profile/forget`, `POST /complexion/{consent,analyze,confirm,cancel}`.

## Phase 7: evaluation (`eval/`)
Three systems behind one interface: **plain** (good prompt, no catalog), **rag** (retrieval + remembered needs, no
policy or validator) and **agent** (this project). Simulated shoppers come from `eval/personas.py` (8 scenario types,
deterministic per seed, built from the real catalog so each is feasible; some are deliberately impossible to test honesty).

```
# 1. Harness check, free, no key: scripted shoppers + the keyword fake LLM, agent only.
#    This validates the plumbing and regressions. It is NOT a result (the fake LLM is far easier than Gemini).
python -m eval.run --offline --systems agent --sim scripted --n 48

# 2. Small real run (set GEMINI_API_KEY first). Look at results.md and a few transcripts before scaling.
python -m eval.run --systems plain,rag,agent --sim llm --n 16 --workers 2

# 3. Full run: 150-300 shoppers per system. Resumable if interrupted.
python -m eval.run --systems plain,rag,agent --sim llm --n 200 --workers 4 --resume

# 4. Human review of 30 stratified conversations, then compare with the simulated ratings.
python -m eval.review export --n 30      # fill natural_1to5 / pressured_yes_no / helpful_1to5 in eval/results/human_review.csv
python -m eval.review summarize
```
Outputs in `eval/results/`: `transcripts.jsonl` (every turn, tokens, latency, policy rule), `scores.json`,
`results.json`, `results.md` (tables with Wilson 95% intervals and a Limitations section; write the Analysis yourself).

**Cost:** an LLM-simulated conversation is roughly 6-10 turns, and each turn costs a simulator call plus 1-3 system
calls, plus one judge call per conversation. So `--n 200` with 3 systems is on the order of 10,000+ API calls. Run
`--n 16` first, read the token counts in results.md, and extrapolate before scaling.

Metrics: task completion (scenario-specific), simulated purchase intent, turns to decision, product relevance (shown
items matching the constraints the shopper had stated), invented prices, objections resolved, "no" respected,
off-topic not hijacked, honest when nothing matches, tokens, latency. All are proxies for real customers.

**Notes after the first real run (scoring rubric v2).** `--resume` now re-runs conversations that errored (for example
an API spend limit) and keeps the finished ones. The shopper's closing message ("yes, place the order") is now delivered
to the system. Scoring changes: "stop" no longer counts as a "no", the honesty check looks at the reply to the budget
message, an off-topic "hijack" means pushing products (a friendly steer back is fine), and the report adds how many stated
buys became a real mock order. v1 and v2 numbers are not comparable; rerun all systems on the same rubric.

## Performance
The first real evaluation showed ~6 s for a *single* Gemini call and ~9-10 s per agent reply, even for a 20-token
answer, which points at fixed per-call overhead rather than output length. Gemini 3 models think by default, and those
hidden thinking tokens cost time. What changed:

- `GEMINI_THINKING` (default `low`): Gemini 3 takes a thinking level, Gemini 2.5 a token budget (the code translates).
  If a model rejects the setting, the client drops it automatically. Use `default` to leave the model's own setting.
- A fast path (`app/llm/fastpath.py`) understands exact simple messages without an LLM call: a bare size, "sports shoes",
  "for me", "hi", "yes" when something is waiting for confirmation, a short "no thanks". Anything else still goes to Gemini.
  Disable with `FASTPATH=0`.
- Plain questions ("what size?") and the no/quiet replies are fixed text; only replies that carry content (results,
  comparisons, opinions, objections) are worded by the LLM. `PHRASE_ALL=1` restores LLM wording everywhere.
- `GEMINI_FAST_MODEL` (optional) runs parsing and short wording on a smaller model; opinions, comparisons and
  objections stay on `GEMINI_MODEL`.
- The evaluation now records hidden thinking tokens per conversation.

Measure it: `python -m eval.latency` times one parse call and one wording call at each thinking level (with thinking
tokens per call), then runs a scripted agent conversation and prints seconds and LLM calls per message.

## Price objections: what the second real run found
The agent resolved 0 of 2 price objections. In both, the shopper said the ₹1,999 Hush Puppies Derby was too pricey and
asked for something cheaper (the catalog does have cheaper office shoes in size 11, such as the ₹1,599 Clarks Derby).
The agent replied "I've lowered the price range" and showed *more expensive* shoes. Causes and fixes:
- Two Hush Puppies Derbys were on screen, so the name was ambiguous and the shoe was never identified. Same-name shoes
  are now disambiguated by a quoted price ("at ₹1,999"), then by the shoe the assistant itself just recommended.
- "Anything cheaper?" was routed to the generic "cheaper" refinement, which lowers the ceiling from the *priciest* shoe
  on screen. A price complaint about a named (or quoted-price) shoe now goes to the objection handler for that shoe:
  alternatives strictly cheaper than it, same use and size, best rated first, or an honest "nothing cheaper".
- Generic "cheaper" replies now state the ceiling ("Everything shown is ₹X or less") so the claim can be checked.
- Scoring: "honest when nothing matches" failed when the simulated shopper paraphrased the budget (1,399 -> 1,400); it
  now checks that the system said there was nothing and showed nothing afterwards.

## Third real run (seed 11): findings and fixes
- **Latency:** `python -m eval.latency` on the same model: thinking `low` 1.5 s per call (71 thinking tokens), `medium` 3.1 s
  (637), `high` 4.4 s (898). Typical agent reply is now 1.5-3 s, and exact-pattern messages cost 0 s.
- **0 of 13 stated buys became a real order.** The simulated shopper ended the chat in the same message as "I'll take them"
  and "Added to your cart" gave no next step. Fixes: "I'll take it" is a purchase and asks for confirmation; a plain
  add-to-cart says "Say “place order” when you're ready"; "place order" / "check out" works any time the cart has something
  (new `checkout` intent); an old offer to confirm expires after an unrelated turn; the simulator now waits for the reply.
- **Invented price 2/16 was a scoring artifact:** the agent's own sentence "Everything shown is ₹4,559 or less" is a
  filter ceiling, not a product price. Ceilings and order totals are no longer counted.
- **Two real objection misses**, both a lighter model mislabelling the message: an exact budget inside a price complaint
  ("way too expensive, I'm looking for something under ₹899") was ignored, and "Do these run small?" was answered by
  re-showing the shoes. `app/engine/signals.py` now backs the LLM with deterministic checks for an exact budget, fit and
  durability questions, and "I'll take it". A stated budget is applied as stated, and with nothing in stock the agent
  says so.
- A malformed or empty model response (`MALFORMED_RESPONSE`) is retried once and then answered with a polite "say it
  again", not a crash. Common commands ("show me the second one", "buy this", "compare the first and third", "cheaper") skip the
  LLM when they match exactly. Run `pip install -U google-genai` to silence the unknown-`FinishReason` warning.

## Evaluation results (run 4: seed 23, 16 simulated shoppers per system, `gemini-3.5-flash-lite`)
This is the first run on a seed that was not used to find bugs, scored under rubric v3. n is small: treat differences
smaller than the intervals as noise. Re-run with `--n 150-300` and the human review before quoting these anywhere.

| Metric | plain | rag | agent |
|---|---|---|---|
| Task completion (95% CI) | 88% [64-97] | 88% [64-97] | 94% [72-99] |
| Felt natural (1-5) | 4.38 | 4.69 | 4.75 |
| Turns to decision (buyers) | 9.8 | 4.4 | 4.0 |
| Product relevance (shown items that fit) | n/a | 83% | 100% |
| Replies with an invented price | 12% (2/16) | 0% | 0% |
| Objections resolved | 3/3 | 4/4 | 4/4 |
| Respected a "no" | 2/3 | 2/2 | 1/2 |
| Honest when nothing matches | 0/2 | 1/2 | 2/2 |
| Stated buy followed by a real mock order | n/a | n/a | 12/12 |
| Latency per reply (s) | 1.35 | 1.98 | 1.27 |
| Tokens per conversation (in / out) | 4729 / 425 | 2998 / 344 | 2535 / 378 |

**Analysis (draft, edit after the human review).** On task completion the three systems are statistically
indistinguishable at this sample size (the intervals overlap almost completely), so this run does not show that the
decision layer sells more. What it does show is about *how* the systems get there. The two catalog-backed systems reach a
decision in roughly 4 turns against about 10 for the plain prompt, and the agent's replies were the fastest and cheapest
of the three. Grounding is where the agent is clearest: everything it showed fit the shopper's stated constraints
(rag: 83%), it never quoted an invented price, it told shoppers plainly when nothing in stock matched (2 of 2), and
every stated purchase became a real mock order. The plain prompt invented a price in 2 of 16 conversations, the same rate
as in the previous run, which is expected for a system that cannot see the catalog.

Where the agent is not better: shopper-rated naturalness is within noise of rag (4.75 vs 4.69) and its numbers swung
between runs (4.38 in the previous one), so no claim is warranted. The one clear miss is the "no" test: the agent
respected 1 of 2 and completed 1 of 2 rejection scenarios while rag respected both, a weakness the earlier
scoring had hidden. Two caveats apply to the comparisons: the plain baseline cannot check stock by construction, so scenarios
about honest "nothing matches" answers structurally favour systems with a catalog; and the plain system used far more hidden
thinking tokens (1,251 per conversation vs 11 for the agent) even at the same setting, which inflates its cost and may
reflect its longer prompt. The simulated shoppers and the LLM judge come from one model family and are proxies; the 30-conversation
human review is what should settle naturalness and pressure.

## Run 4 rejection failure: "just browsing" after a "no"
Transcript: shopper says "Hi, just looking around today, no thanks." (agent correctly backs off), then "Thanks, just
browsing." and the agent showed six products. The phrase "just browsing" had been routed to the relaxed-browse rule, and
browsing counts as re-engaging, which lifts the stop-selling state. The same phrase was fine for two bored shoppers
("just looking around out of boredom") but is a brush-off in a shop. Decision: when in doubt do not push; a quiet reply
costs one turn, an unwanted pitch costs trust.
- New `just_looking` rule: "just browsing/looking, thanks" with no request gets a quiet reply and no products. Before any
  no it adds "or say “show me something”"; after a no it says nothing more. Actual invitations ("I'm bored", "surprise me",
  "show me something", "just looking, what do you have?") still go to browse.
- The same sentence is never repeated back to back (two "No problem at all..." replies, and two identical "nothing in stock"
  replies, were visible in the transcripts); a short alternate is used instead.
- The harmless `MALFORMED_RESPONSE is not a valid FinishReason` SDK warning is filtered (the response is already retried).
