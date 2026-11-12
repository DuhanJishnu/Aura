# Evaluation

Evaluation covers two complementary layers:
1. **Google ADK Native Evaluation (`eval/adk_eval/`)** via `AgentEvaluator` / `adk eval`
2. **Stylist Behavioral & Grounding Suite (`eval/run.py`)** comparing the ADK Stylist against a plain no-tool baseline.

## 1. Google ADK `AgentEvaluator` (`eval/adk_eval/`)
- Dataset: [`eval/adk_eval/stylist.evalset.json`](../eval/adk_eval/stylist.evalset.json)
- Config: [`eval/adk_eval/test_config.json`](../eval/adk_eval/test_config.json)
- Criteria: `tool_trajectory_avg_score >= 0.8`, `response_match_score >= 0.4`.
- Run natively with your Gemini API key:
  ```bash
  python -m eval.run --adk-eval
  # or via ADK CLI:
  adk eval stylist_agent eval/adk_eval/stylist.evalset.json --config_file_path eval/adk_eval/test_config.json
  ```

## 2. Custom Stylist Rubric (`eval/run.py`)
Tests 8 core scenarios (`eval/personas.py`) across:
- **Online Discovery (`search_fashion_online`)**: triggers live search, returns `swipe_deck`, `url_integrity = 1.0` (zero fabricated non-search URLs).
- **Outfit Curation (`curate_outfit`)**: produces `outfit_board` with >=3 pieces, color story, and proportion tips (`styling_depth = 1.0`).
- **Swipe Adaptation (`apply_swipe` + `rerank_items`)**: excludes passed items and boosts liked aesthetics/colors (`swipe_adaptation = 1.0`).
- **Friend + Fashion Circle-Back**: answers off-topic queries (cooking, work stress) warmly and bridges back to fashion/styling (`friend_circle_back = 1.0`).
- **Boundary Compliance ("No Means No")**: stops pitching and stops circling back after an explicit decline (`boundary_respected = 1.0`).
- **Complexion & Memory Lifecycle**: saves undertone/season, recalls Saved Closet items, and clears everything on `"Forget my profile"`.

### Running Evals
```bash
# Free deterministic offline check (used in CI / pytest)
python -m eval.run --offline --baseline

# Live Gemini + Google Search evaluation (uses GEMINI_API_KEY)
python -m eval.run --live --baseline
```

### Observed Offline Harness Check
Running `python -m eval.run --offline --baseline`:
- `adk_stylist_offline`: **8/8 passed** across all rubric dimensions (`url_integrity`, `tool_accuracy`, `ui_accuracy`, `styling_depth`, `swipe_adaptation`, `friend_circle_back`, `boundary_respected`, `complexion_saved`, `memory_lifecycle`).
- `plain_baseline`: failed tool/UI/swipe-adaptation/memory checks as expected without tools or Style DNA.
