"""Print conversations from a results folder so you can read what actually happened.
    python -m eval.show --results eval/results_v4 --system agent --category rejection
    python -m eval.show --results eval/results_v4 --system agent --failed
    python -m eval.show --results eval/results_v4 --id p004"""
import argparse
import json
from pathlib import Path

from eval.review import load


def render(conv, ok: bool | None) -> str:
    p = conv.persona
    mark = "" if ok is None else ("  [PASSED]" if ok else "  [FAILED]")
    lines = ["=" * 90, f"{conv.system} {p.id} {p.category}{mark} | use={p.use} size={p.size} budget={p.budget} empty={p.expected_empty}",
             f"verdict={ {k: v for k, v in (conv.verdict or {}).items() if k != 'message'} }", f"judge={conv.judge}"]
    if conv.error:
        lines.append("ERROR: " + conv.error[-400:])
    for t in conv.turns:
        if t.role == "user":
            lines.append(f"U: {t.text}")
        else:
            lines.append(f"A: {t.text}\n   [{t.action} | rule={t.rule} | ids={t.shown_ids} | order={t.order_id} | {t.latency:.1f}s]")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="eval/results")
    ap.add_argument("--system")
    ap.add_argument("--category")
    ap.add_argument("--id")
    ap.add_argument("--failed", action="store_true")
    a = ap.parse_args()
    root = Path(a.results)
    scores = {(r["system"], r["id"]): r for r in json.loads((root / "scores.json").read_text())}
    for c in load(root):
        ok = scores.get((c.system, c.persona.id), {}).get("success")
        if (a.system and c.system != a.system) or (a.category and c.persona.category != a.category) or (a.id and c.persona.id != a.id):
            continue
        if a.failed and ok:
            continue
        print(render(c, ok))
