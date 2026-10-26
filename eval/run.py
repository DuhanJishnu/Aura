"""Run the evaluation.

Offline smoke test (no API key, agent only, scripted shoppers):
    python -m eval.run --offline --systems agent --sim scripted --n 48
Real comparison (needs GEMINI_API_KEY; start small, e.g. --n 16, and check the cost first):
    python -m eval.run --systems plain,rag,agent --sim llm --n 200 --workers 4"""
import argparse
import json
import os
import sqlite3
import sys
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from app.catalog.db import DB_PATH, init_db
from eval.metrics import Ctx, aggregate, score
from eval.personas import generate
from eval.report import render
from eval.simulators import LLMUser, ScriptedUser, judge, transcript_text
from eval.systems import SYSTEMS
from eval.types import Conversation, Turn


def copy_db(path: Path) -> sqlite3.Connection:
    """Each conversation gets its own in-memory copy, so orders and stock changes never leak between runs."""
    src = sqlite3.connect(str(path))
    dst = sqlite3.connect(":memory:", check_same_thread=False)
    src.backup(dst)
    src.close()
    dst.row_factory = sqlite3.Row
    init_db(dst)
    return dst


def make_llm(offline: bool):
    if offline:
        from tests.fakes import FakeLLM
        return FakeLLM()
    from eval.llm import EvalGemini
    return EvalGemini()


def converse_llm(conv: Conversation, bot, user, conn, max_turns: int) -> None:
    """LLM-simulated shopper loop. The shopper's closing message is still sent to the system, because it is
    often the one that matters ("yes, place the order"); the verdict is what the shopper decided at that point."""
    for turn_no in range(max_turns):
        ut = user.next(transcript_text(conv.turns, conn), force_end=turn_no == max_turns - 1)
        if ut.message:
            conv.turns.append(Turn("user", ut.message))
            conv.turns.append(bot.respond(ut.message))
        if ut.end:
            conv.verdict = ut.model_dump()
            return
    conv.verdict = {"outcome": "abandon"}


def run_one(system: str, persona, sim: str, offline: bool, db_path: Path) -> Conversation:
    conv = Conversation(persona, system)
    conn = copy_db(db_path)
    try:
        sys_llm = make_llm(offline)
        bot = SYSTEMS[system](conn, sys_llm, persona.id)
        if sim == "scripted":
            user, last = ScriptedUser(persona), None
            while (msg := user.next(last)) is not None:
                conv.turns.append(Turn("user", msg))
                last = bot.respond(msg)
                conv.turns.append(last)
            conv.verdict = user.verdict(conv)
        else:
            from eval.llm import EvalGemini
            sim_llm = EvalGemini()  # separate client: simulator and judge tokens are not charged to the system
            converse_llm(conv, bot, LLMUser(persona, sim_llm), conn, persona.max_turns)
            conv.judge = judge(sim_llm, persona, transcript_text(conv.turns, conn))
        conv.orders = [dict(r) for r in conn.execute(
            "SELECT oi.shoe_id, oi.size, oi.price, s.use_type, s.category FROM order_items oi JOIN shoes s ON s.id=oi.shoe_id")]
    except Exception:
        conv.error = traceback.format_exc(limit=3)
    finally:
        conn.close()
    return conv


def run_eval(systems, n, sim="llm", offline=False, db_path=DB_PATH, out_dir="eval/results", workers=1, seed=7, resume=False) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tpath = out / "transcripts.jsonl"
    done = set()
    if resume and tpath.exists():
        kept = []
        for line in tpath.read_text().splitlines():
            d = json.loads(line)
            if d.get("error"):
                continue  # failed conversations (e.g. an API limit) are re-run, not kept
            kept.append(line)
            done.add((d["system"], d["persona"]["id"]))
        tpath.write_text("".join(f"{x}\n" for x in kept))
    elif tpath.exists():
        tpath.unlink()
    probe = copy_db(Path(db_path))
    personas = generate(probe, n, seed)
    jobs = [(s, p) for p in personas for s in systems if (s, p.id) not in done]
    print(
        f"{len(jobs)} conversations to run ({len(personas)} shoppers x {len(systems)} systems), sim={sim}",
        file=sys.stderr,
        flush=True,
    )
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as ex, tpath.open("a") as f:
        futs = [ex.submit(run_one, s, p, sim, offline, Path(db_path)) for s, p in jobs]
        pending = set(futs)
        completed = 0
        while pending:
            finished, pending = wait(pending, timeout=30, return_when=FIRST_COMPLETED)
            if not finished:
                print(
                    f"  {completed}/{len(jobs)} completed; {len(pending)} still running "
                    f"({time.monotonic() - started:.0f}s elapsed)",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            for fut in finished:
                conv = fut.result()
                f.write(json.dumps(conv.to_json()) + "\n")
                f.flush()
                completed += 1
                status = "failed" if conv.error else "done"
                print(
                    f"  {completed}/{len(jobs)} {status} ({conv.system}, {conv.persona.id})",
                    file=sys.stderr,
                    flush=True,
                )
    convs = [Conversation.from_json(json.loads(line)) for line in tpath.read_text().splitlines() if line.strip()]
    ctx = Ctx(probe)
    rows = [score(c, ctx) for c in convs]
    results = aggregate(rows)
    (out / "scores.json").write_text(json.dumps(rows))
    (out / "results.json").write_text(json.dumps(results, indent=2))
    model = "offline-fake" if offline else os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    (out / "results.md").write_text(render(results, {"n": n, "sim": sim, "model": model, "seed": seed}))
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="plain,rag,agent")
    ap.add_argument("--n", type=int, default=16, help="simulated shoppers per system (150-300 for the full run)")
    ap.add_argument("--sim", choices=["llm", "scripted"], default="llm")
    ap.add_argument("--offline", action="store_true", help="use the fake LLM (agent + scripted only; no API key)")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="eval/results")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    systems = a.systems.split(",")
    if a.offline and (systems != ["agent"] or a.sim != "scripted"):
        sys.exit("--offline only supports --systems agent --sim scripted")
    if not a.offline and not os.getenv("GEMINI_API_KEY"):
        sys.exit("Set GEMINI_API_KEY (or use --offline for the smoke test).")
    if not Path(a.db).exists():
        sys.exit("Catalog missing. Run: python -m data.seed")
    run_eval(systems, a.n, a.sim, a.offline, a.db, a.out, a.workers, a.seed, a.resume)
    print(f"Done. See {a.out}/results.md")
