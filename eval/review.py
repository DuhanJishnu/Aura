"""Human review: export ~30 conversations (stratified) to a CSV, rate them by hand, then summarise.
    python -m eval.review export --results eval/results --n 30
    python -m eval.review summarize --results eval/results"""
import argparse
import csv
import json
import random
import sqlite3
from collections import defaultdict
from pathlib import Path

from eval.simulators import transcript_text
from eval.types import Conversation

COLS = ["conv_id", "system", "category", "transcript", "natural_1to5", "pressured_yes_no", "helpful_1to5", "notes"]


def load(results: Path) -> list[Conversation]:
    return [Conversation.from_json(json.loads(line)) for line in (results / "transcripts.jsonl").read_text().splitlines() if line.strip()]


def export(results: Path, n: int, db: Path, seed: int = 1) -> Path:
    convs = [c for c in load(results) if not c.error]
    rnd = random.Random(seed)
    by_cat = defaultdict(list)
    for c in convs:
        by_cat[c.persona.category].append(c)
    picked, cats = [], sorted(by_cat)
    for c in cats:
        rnd.shuffle(by_cat[c])
    while len(picked) < min(n, len(convs)) and any(by_cat.values()):  # round-robin across scenario types
        for c in cats:
            if by_cat[c] and len(picked) < n:
                picked.append(by_cat[c].pop())
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    out = results / "human_review.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for c in picked:
            w.writerow([f"{c.system}:{c.persona.id}", c.system, c.persona.category, transcript_text(c.turns, conn), "", "", "", ""])
    return out


def summarize(results: Path) -> dict:
    rows = list(csv.DictReader((results / "human_review.csv").open()))
    agg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for col in ("natural_1to5", "helpful_1to5"):
            if r[col].strip():
                agg[r["system"]][col].append(float(r[col]))
        if r["pressured_yes_no"].strip():
            agg[r["system"]]["pressured"].append(1.0 if r["pressured_yes_no"].strip().lower().startswith("y") else 0.0)
    return {s: {k: sum(v) / len(v) for k, v in d.items() if v} | {"n_rated": len(d.get("natural_1to5", []))} for s, d in agg.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "summarize"])
    ap.add_argument("--results", default="eval/results")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--db", default="data/shop.db")
    a = ap.parse_args()
    if a.cmd == "export":
        print("Wrote", export(Path(a.results), a.n, Path(a.db)))
    else:
        print(json.dumps(summarize(Path(a.results)), indent=2))
