# Evaluation

## What is compared
- **plain**: a good prompt, no catalog, no tools.
- **rag**: Gemini + catalog search + remembered needs; no rule table, no validator.
- **agent**: this project.

Each system talks to simulated shoppers (`eval/personas.py`, built from the real catalog so each is feasible; some are
deliberately impossible to test honesty) across eight scenarios: vague, strong preference, price objection, indecision,
rejection, off-topic, sizing/stock, frustration. Shoppers are either scripted (free, deterministic, for harness checks) or played
by Gemini from a private persona card. A separate Gemini call judges objection handling, pitching after a "no" and invented
facts; deterministic checks against the catalog score relevance, invented prices and honesty.

## Running it
```bash
python -m eval.run --offline --systems agent --sim scripted --n 48              # harness check, free, NOT a result
python -m eval.run --systems plain,rag,agent --sim llm --n 16 --seed 23         # small real run
python -m eval.run --systems plain,rag,agent --sim llm --n 200 --workers 4 --resume
python -m eval.show --results eval/results --system agent --failed              # read what happened
python -m eval.review export --n 30 && python -m eval.review summarize          # human review
```
An LLM-simulated conversation is roughly 6-10 turns with a simulator call and 1-3 system calls per turn plus one judge call:
`--n 200` with three systems is on the order of 10,000+ API calls. Run `--n 16` first and extrapolate from the token counts.

## Latest results (seed 23, 16 shoppers per system, `gemini-3.5-flash-lite`, rubric v3)

| Metric | plain | rag | agent |
|---|---|---|---|
| Task completion (95% CI) | 88% [64-97] | 88% [64-97] | 94% [72-99] |
| Simulated purchase intent (1-5) | 4.19 | 4.00 | 4.00 |
| Felt natural (1-5) | 4.38 | 4.69 | 4.75 |
| Felt pressured | 6% | 6% | 0% |
| Stated buy followed by a real mock order | n/a | n/a | 12/12 |
| Turns to decision (buyers) | 9.8 | 4.4 | 4.0 |
| Shown items that fit | n/a | 83% | 100% |
| Replies with an invented price | 12% | 0% | 0% |
| Objections resolved | 3/3 | 4/4 | 4/4 |
| Respected a "no" | 2/3 | 2/2 | 1/2 |
| Honest when nothing matches | 0/2 | 1/2 | 2/2 |
| Tokens per conversation (in / out) | 4729 / 425 | 2998 / 344 | 2535 / 378 |
| Hidden thinking tokens per conversation | 1251 | 76 | 11 |
| Latency per reply | 1.35 s | 1.98 s | 1.27 s |

## Analysis
On task completion the three systems are statistically indistinguishable at this sample size (the intervals overlap almost
completely), so this run does not show that the decision layer sells more. What it shows is how the systems get there: the two
catalog-backed systems decide in about 4 turns against about 10 for the plain prompt, and the agent's replies were the fastest
and cheapest. Grounding is where the agent is clearest: everything it showed fit the shopper's stated constraints (rag: 83%),
it quoted no invented price, it told shoppers plainly when nothing matched, and every stated purchase became a real mock order.
The plain prompt invented a price in 2 of 16 conversations, the same rate as the previous run, as expected without a catalog.

Where the agent is not better: shopper-rated naturalness is within noise of rag (4.75 vs 4.69; it was 4.38 in the previous
run). The one clear miss was the "no" test (1 of 2 against rag's 2 of 2). The transcript showed the cause: after "no thanks",
the shopper said "Thanks, just browsing" and the browse rule showed products. "Just browsing, thanks" is now a quiet reply,
not a request to be shown things; this fix was made after run 4 and has **not** been re-measured at scale.

Caveats: the plain baseline cannot check stock by construction, so scenarios about honest "nothing matches" answers
structurally favour systems with a catalog; the plain system used far more hidden thinking tokens (1,251 per conversation vs 11) at
the same setting, which inflates its cost; simulated shoppers and the judge come from one model family; scoring changed
between runs (v2, v3), so runs are not directly comparable. The human review is what should settle naturalness and pressure.

## What the real runs found (and fixed)
Run 1: closing messages never reached the system; scoring false positives; named shoes not understood; "cheaper" claims that
were not true. Run 2: price complaints about a named shoe routed to the wrong handler; two same-name shoes made names ambiguous.
Run 3: stated buys never became orders (no next step after "added to cart"); an exact budget ignored; "do these run small?" answered by
re-showing shoes; malformed model responses. Run 4: "just browsing" after a "no" re-opened selling. Latency: default thinking
cost 2-3x per call (1.5 s at `low`, 3.1 s `medium`, 4.4 s `high` on the same model). Full detail: DEVELOPMENT_LOG.md.
