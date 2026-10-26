# Evaluation results

Run: 16 simulated shoppers per system, simulator `llm`, model `gemini-3.8-flash`, seed 7.

## Headline metrics

| Metric | plain | rag | agent |
|---|---|---|---|
| Task completion (95% CI) | 62% [39-82] | 88% [64-97] | 75% [51-90] |
| Simulated purchase intent (1-5) | 3.44 | 3.75 | 3.50 |
| Felt natural (1-5) | 4.25 | 4.75 | 4.00 |
| Felt pressured | 0% (0/16) | 0% (0/16) | 0% (0/16) |
| Stated buy followed by a real mock order (agent) | n/a | n/a | 80% (8/10) |
| Turns to decision (buyers) | 6.6 | 3.8 | 3.8 |
| Product relevance (shown items that fit) | n/a | 92% | 100% |
| Replies with an invented price | 6% (1/16) | 0% (0/16) | 0% (0/16) |
| Objections resolved | 100% (3/3) | 100% (4/4) | 50% (2/4) |
| Respected a 'no' | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| Off-topic answered without a product push | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| Honest when nothing matches | 0% (0/1) | 100% (1/1) | 0% (0/1) |
| Tokens per conversation (in / out) | 2248 / 326 | 2574 / 259 | 3062 / 464 |
| Latency per reply (s) | 6.17 | 10.39 | 9.31 |
| Errors (conversations) | 0 | 0 | 0 |

Relevance is n/a for `plain` because it has no catalog to show items from; its grounding is measured by the invented-price row. Token counts cover the system under test only (not the simulator or judge).

## Task completion by scenario

| Scenario | plain | rag | agent |
|---|---|---|---|
| vague | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| strong_preference | 0% (0/2) | 50% (1/2) | 50% (1/2) |
| price_objection | 100% (2/2) | 50% (1/2) | 0% (0/2) |
| indecision | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| rejection | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| off_topic | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| sizing_stock | 0% (0/2) | 100% (2/2) | 50% (1/2) |
| frustration | 0% (0/2) | 100% (2/2) | 100% (2/2) |

## Agent details

Real mock orders that met the shopper's constraints (use, size, budget): 100% (8/8).

Policy rules fired (all replies): `retrieve` 13, `cart` 10, `confirm_order` 8, `no_means_no` 6, `clarify_missing` 5, `browse` 4, `refine` 4, `compare` 2, `passive_after_no` 2, `answer_off_topic` 2, `objection` 2, `opinion` 1.

## Limitations (read before quoting these numbers)

- Scoring rubric v2. It changed after the first 16-shopper run (a 'stop' false positive, the honesty check now looks at the reply to the budget message, off-topic 'push' means showing products, and the shopper's closing message is now delivered to the system), so v1 and v2 numbers are not comparable.

- Simulated shoppers and the LLM judge are proxies. They can be too cooperative or too harsh, and the same model family may favour its own style. Check against the human review (`python -m eval.review`).
- The synthetic catalog is small and generated, so relevance and stock behave more cleanly than real inventory.
- `plain` and `rag` cannot place orders, so their 'bought' comes from the simulated shopper's stated decision; only the agent places (mock) orders.
- Small per-scenario samples give wide intervals; compare overall rows first.

## Analysis

_Write 1-2 paragraphs here after reading the table: where the agent wins, where it doesn't, and what the human review changed._
