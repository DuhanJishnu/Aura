# What is left to do

Honest status: the plan's phases 0-8 are built. This list is what stands between "built" and "trusted", plus the plan items
that were skipped or only partly done.

## 1. Before quoting any result (highest priority)
1. **Run the larger evaluation**: `--n 150` or more per system on a fresh seed (so no bug was fixed by reading that seed). Runs so far are 16 per system.
2. **Do the human review** of 30 conversations (`python -m eval.review export`), then edit the analysis in `docs/EVALUATION.md`.
3. **Re-measure the "no" test** after the `just browsing` fix, and re-run `python -m eval.latency` with the current code.
4. **Extend the simulated shoppers to apparel and accessories** (they are shoes-only today; the new categories have unit tests only).

## 2. Verify what was written but not run
5. **Real browser pass** of the Next.js app: streaming, Mic and spoken replies (Chrome/Edge), the photo flow with real photos, mobile layout, dark mode.
6. **Live Gemini pass** on categories (size letters like "medium" -> 3, "a casual shirt"), apparel opinions and objections.
7. **Docker**: build and run both images (`docker compose up`), check streaming through your proxy of choice.
8. **GitHub Actions**: push the repo and make both jobs green.

## 3. Plan items not built or only partly built
9. **Embeddings / semantic search** for free-text queries ("light shoes for monsoon"): Phase 1 item 4 was never built.
10. **Jev-based decision layer** (optional, Phase 5): not built; what "Jev" refers to was never verified. The rule table is kept separate so another decision layer can be compared against it.
11. **Real token streaming** (replies are validated before they are shown, so text arrives in pieces after the panel).
12. **2-minute demo video and screenshots/GIF** (script in `docs/DEMO.md`).

## 4. Product and engineering gaps
13. **Real catalog and images** (data and product photos are synthetic; cards are colored blocks).
14. **Durable sessions** (Redis or the database) so restarts and multiple instances work; today one process, in memory.
15. **Accounts**: a profile is tied to a random browser id; real login, plus retention rules for orders and profile data.
16. **Privacy review of the photo flow** (consent wording, retention, where the browser's speech service sends audio).
17. **Prompt-injection and abuse tests** (user text reaches the model; add adversarial test cases and monitor).
18. **Observability and cost**: structured logs with request ids, per-session token budgets, spend alerts, error tracking.
19. **Load and concurrency testing**; accessibility audit; Hindi / multilingual support and Indian-English voice quality.
20. **Repo hygiene**: LICENSE, a short CONTRIBUTING, pinned dependency versions.

## 5. Known weak spots to keep watching
- Objection handling depends on the model's labels; deterministic backstops exist (`app/engine/signals.py`) but only for known phrasings.
- Fixed-text replies for plain questions trade a little warmth for speed (compare with `PHRASE_ALL=1`).
- Naturalness was within noise of the retrieval baseline; only the human review can settle it.
