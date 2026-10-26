# Evaluation results

Run: 6 simulated shoppers per system, simulator `llm`, model `gemini-3.5-flash-lite`, seed 42.

## Headline metrics

| Metric | agent |
|---|---|
| Task completion (95% CI) | 100% [61-100] |
| Simulated purchase intent (1-5) | 4.33 |
| Felt natural (1-5) | 4.50 |
| Felt pressured | 17% (1/6) |
| Stated buy followed by a real mock order (agent) | 100% (5/5) |
| Turns to decision (buyers) | 5.0 |
| Product relevance (shown items that fit) | 100% |
| Replies with an invented price | 0% (0/6) |
| Objections resolved | 0% (0/1) |
| Respected a 'no' | 100% (1/1) |
| Off-topic answered without a product push | 100% (1/1) |
| Honest when nothing matches | n/a |
| Tokens per conversation (in / out) | 3592 / 495 |
| Hidden thinking tokens per conversation | 0 |
| Latency per reply (s) | 1.54 |
| Errors (conversations) | 0 |

Relevance is n/a for `plain` because it has no catalog to show items from; its grounding is measured by the invented-price row. Token counts cover the system under test only (not the simulator or judge).

## Task completion by scenario

| Scenario | agent |
|---|---|
| vague | 100% (1/1) |
| strong_preference | 100% (1/1) |
| price_objection | 100% (1/1) |
| indecision | 100% (1/1) |
| rejection | 100% (1/1) |
| off_topic | 100% (1/1) |
| sizing_stock | n/a |
| frustration | n/a |

## Agent details

Real mock orders that met the shopper's constraints (use, size, budget): 100% (5/5).

Policy rules fired (all replies): `retrieve` 6, `cart` 5, `checkout` 5, `just_looking` 3, `no_means_no` 3, `opinion` 2, `focus` 1, `clarify_missing` 1, `compare` 1, `answer_off_topic` 1.

## Limitations (read before quoting these numbers)

- Scoring rubric v2. It changed after the first 16-shopper run (a 'stop' false positive, the honesty check now looks at the reply to the budget message, off-topic 'push' means showing products, and the shopper's closing message is now delivered to the system), so v1 and v2 numbers are not comparable.

- Rubric v3 (after the third run): the simulated shopper must read the assistant's reply before ending, so a stated buy can now be followed by a real order; price ceilings the agent states and order totals are no longer counted as invented prices. Runs scored under v2 and v3 are not directly comparable.

- Simulated shoppers and the LLM judge are proxies. They can be too cooperative or too harsh, and the same model family may favour its own style. Check against the human review (`python -m eval.review`).
- The synthetic catalog is small and generated, so relevance and stock behave more cleanly than real inventory.
- `plain` and `rag` cannot place orders, so their 'bought' comes from the simulated shopper's stated decision; only the agent places (mock) orders.
- Small per-scenario samples give wide intervals; compare overall rows first.

## Analysis

_Write 1-2 paragraphs here after reading the table: where the agent wins, where it doesn't, and what the human review changed._
