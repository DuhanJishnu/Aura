from eval.metrics import wilson  # noqa: F401  (re-exported for callers)
from eval.personas import CATEGORIES


def _pct(kn) -> str:
    k, n = kn[0], kn[1]
    return "n/a" if n == 0 else f"{100 * k / n:.0f}% ({k}/{n})"


def _num(x, d=2) -> str:
    return "n/a" if x is None else f"{x:.{d}f}"


def render(results: dict, meta: dict) -> str:
    ov, cat = results["overall"], results["by_category"]
    systems = [s for s in ("plain", "rag", "agent") if s in ov]
    L = ["# Evaluation results\n", f"Run: {meta.get('n')} simulated shoppers per system, simulator `{meta.get('sim')}`, "
         f"model `{meta.get('model')}`, seed {meta.get('seed')}.\n"]
    L.append("## Headline metrics\n")
    L.append("| Metric | " + " | ".join(systems) + " |\n|---|" + "---|" * len(systems))

    def row(label, fn):
        L.append(f"| {label} | " + " | ".join(fn(ov[s]) for s in systems) + " |")

    row("Task completion (95% CI)", lambda o: f"{100 * o['success'][0] / max(o['success'][1], 1):.0f}% [{100 * o['success'][2]:.0f}-{100 * o['success'][3]:.0f}]")
    row("Simulated purchase intent (1-5)", lambda o: _num(o["purchase_intent"]))
    row("Felt natural (1-5)", lambda o: _num(o["natural"]))
    row("Felt pressured", lambda o: _pct(o["pressured"]))
    row("Stated buy followed by a real mock order (agent)", lambda o: _pct(o["order_follow_through"]))
    row("Turns to decision (buyers)", lambda o: _num(o["turns_to_decision"], 1))
    row("Product relevance (shown items that fit)", lambda o: "n/a" if o["relevance"] is None else f"{100 * o['relevance']:.0f}%")
    row("Replies with an invented price", lambda o: _pct(o["hallucination"]))
    row("Objections resolved", lambda o: _pct(o["objection_resolved"]))
    row("Respected a 'no'", lambda o: _pct(o["respected_no"]))
    row("Off-topic answered without a product push", lambda o: _pct(o["not_hijacked"]))
    row("Honest when nothing matches", lambda o: _pct(o["honest_empty"]))
    row("Tokens per conversation (in / out)", lambda o: f"{_num(o['tokens_in'], 0)} / {_num(o['tokens_out'], 0)}")
    row("Hidden thinking tokens per conversation", lambda o: _num(o.get("tokens_thought"), 0))
    row("Latency per reply (s)", lambda o: _num(o["latency"], 2))
    row("Errors (conversations)", lambda o: str(o["errors"]))
    L.append("\nRelevance is n/a for `plain` because it has no catalog to show items from; its grounding is measured by "
             "the invented-price row. Token counts cover the system under test only (not the simulator or judge).\n")

    L.append("## Task completion by scenario\n")
    L.append("| Scenario | " + " | ".join(systems) + " |\n|---|" + "---|" * len(systems))
    for c in CATEGORIES:
        cells = [(_pct(cat[f"{s}|{c}"]["success"][:2]) if f"{s}|{c}" in cat else "n/a") for s in systems]
        L.append(f"| {c} | " + " | ".join(cells) + " |")
    if "agent" in ov:
        a = ov["agent"]
        L.append(f"\n## Agent details\n\nReal mock orders that met the shopper's constraints (use, size, budget): {_pct(a['strict_success'])}.\n")
        L.append("Policy rules fired (all replies): " + ", ".join(f"`{k}` {v}" for k, v in a["rules"].items()) + ".\n")
    L.append("## Limitations (read before quoting these numbers)\n")
    L.append("- Scoring rubric v2. It changed after the first 16-shopper run (a 'stop' false positive, the honesty check now looks at "
             "the reply to the budget message, off-topic 'push' means showing products, and the shopper's closing message "
             "is now delivered to the system), so v1 and v2 numbers are not comparable.\n")
    L.append("- Rubric v3 (after the third run): the simulated shopper must read the assistant's reply before ending, so a "
             "stated buy can now be followed by a real order; price ceilings the agent states and order totals are no longer "
             "counted as invented prices. Runs scored under v2 and v3 are not directly comparable.\n")
    L.append("- Simulated shoppers and the LLM judge are proxies. They can be too cooperative or too harsh, and the "
             "same model family may favour its own style. Check against the human review (`python -m eval.review`).\n"
             "- The synthetic catalog is small and generated, so relevance and stock behave more cleanly than real inventory.\n"
             "- `plain` and `rag` cannot place orders, so their 'bought' comes from the simulated shopper's stated decision; "
             "only the agent places (mock) orders.\n- Small per-scenario samples give wide intervals; compare overall rows first.\n")
    L.append("## Analysis\n\n_Write 1-2 paragraphs here after reading the table: where the agent wins, where it doesn't, and what the human review changed._\n")
    return "\n".join(L)
