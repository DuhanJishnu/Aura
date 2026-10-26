# Evaluation results

Run: 16 simulated shoppers per system, simulator `llm`, model `gemini-3.5-flash-lite`, seed 23.

## Headline metrics

| Metric | plain | rag | agent |
|---|---|---|---|
| Task completion (95% CI) | 88% [64-97] | 88% [64-97] | 94% [72-99] |
| Simulated purchase intent (1-5) | 4.19 | 4.00 | 4.00 |
| Felt natural (1-5) | 4.38 | 4.69 | 4.75 |
| Felt pressured | 6% (1/16) | 6% (1/16) | 0% (0/16) |
| Stated buy followed by a real mock order (agent) | n/a | n/a | 100% (12/12) |
| Turns to decision (buyers) | 9.8 | 4.4 | 4.0 |
| Product relevance (shown items that fit) | n/a | 83% | 100% |
| Replies with an invented price | 12% (2/16) | 0% (0/16) | 0% (0/16) |
| Objections resolved | 100% (3/3) | 100% (4/4) | 100% (4/4) |
| Respected a 'no' | 67% (2/3) | 100% (2/2) | 50% (1/2) |
| Off-topic answered without a product push | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| Honest when nothing matches | 0% (0/2) | 50% (1/2) | 100% (2/2) |
| Tokens per conversation (in / out) | 4729 / 425 | 2998 / 344 | 2535 / 378 |
| Hidden thinking tokens per conversation | 1251 | 76 | 11 |
| Latency per reply (s) | 1.35 | 1.98 | 1.27 |
| Errors (conversations) | 0 | 0 | 0 |

Relevance is n/a for `plain` because it has no catalog to show items from; its grounding is measured by the invented-price row. Token counts cover the system under test only (not the simulator or judge).

## Task completion by scenario

| Scenario | plain | rag | agent |
|---|---|---|---|
| vague | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| strong_preference | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| price_objection | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| indecision | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| rejection | 100% (2/2) | 100% (2/2) | 50% (1/2) |
| off_topic | 100% (2/2) | 50% (1/2) | 100% (2/2) |
| sizing_stock | 0% (0/2) | 50% (1/2) | 100% (2/2) |
| frustration | 100% (2/2) | 100% (2/2) | 100% (2/2) |

## Agent details

Real mock orders that met the shopper's constraints (use, size, budget): 100% (12/12).

Policy rules fired (all replies): `retrieve` 16, `cart` 12, `checkout` 12, `no_means_no` 6, `browse` 4, `clarify_missing` 2, `objection` 2, `compare` 2, `answer_off_topic` 2, `greet` 1.

## Limitations (read before quoting these numbers)

- Scoring rubric v2. It changed after the first 16-shopper run (a 'stop' false positive, the honesty check now looks at the reply to the budget message, off-topic 'push' means showing products, and the shopper's closing message is now delivered to the system), so v1 and v2 numbers are not comparable.

- Rubric v3 (after the third run): the simulated shopper must read the assistant's reply before ending, so a stated buy can now be followed by a real order; price ceilings the agent states and order totals are no longer counted as invented prices. Runs scored under v2 and v3 are not directly comparable.

- Simulated shoppers and the LLM judge are proxies. They can be too cooperative or too harsh, and the same model family may favour its own style. Check against the human review (`python -m eval.review`).
- The synthetic catalog is small and generated, so relevance and stock behave more cleanly than real inventory.
- `plain` and `rag` cannot place orders, so their 'bought' comes from the simulated shopper's stated decision; only the agent places (mock) orders.
- Small per-scenario samples give wide intervals; compare overall rows first.

## Analysis

_Write 1-2 paragraphs here after reading the table: where the agent wins, where it doesn't, and what the human review changed._
