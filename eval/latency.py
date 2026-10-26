"""Measure where the time goes. Needs GEMINI_API_KEY and costs a few dozen small calls.

    python -m eval.latency                      # compares thinking levels, then times a scripted agent conversation
    python -m eval.latency --levels low,high --repeats 5
It prints, per thinking level: median seconds for one parse call and one wording call, and the hidden thinking tokens
each call used. If 'medium' or 'high' is several seconds slower than 'low' and uses hundreds of thinking tokens,
thinking is what is making replies slow."""
import argparse
import os
import statistics as st
import sys
import time

from app import config
from app.catalog.db import DB_PATH
from app.engine.engine import handle
from app.engine.state import Session
from eval.llm import EvalGemini
from eval.run import copy_db

SCRIPT = ["hi", "sports shoes", "for me", "9", "show me the first one", "what do you think of it?", "buy this", "yes, place the order"]
KNOWN = {"slots": {}, "shortlist_size": 0, "has_focused_product": False, "awaiting_order_confirmation": False, "items_in_cart": 0}


def timed(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def bench_levels(levels, repeats):
    print(f"model={config.GEMINI_MODEL}  fast_model={config.GEMINI_FAST_MODEL or '(same)'}\n")
    print(f"{'thinking':10} {'parse s':>8} {'word s':>8} {'think tok/call':>15} {'out tok/call':>13}")
    for level in levels:
        llm = EvalGemini(thinking=level)
        llm.extract("sports shoes, size 9", KNOWN)  # warm-up: connection setup is not what we are measuring
        parse = [timed(lambda: llm.extract("I need casual shoes for my brother, size 8, under 3000", KNOWN)) for _ in range(repeats)]
        top = [{"name": "Nike Runner", "color": "black", "price": 4999, "rating": 4.5}]
        word = [timed(lambda: llm.phrase("Say you've put matching shoes on screen and mention the top pick.", {"count": 6, "top_picks": top}, "ok")) for _ in range(repeats)]
        calls = max(llm.usage["calls"], 1)
        print(f"{level:10} {st.median(parse):8.1f} {st.median(word):8.1f} {llm.usage['thought'] / calls:15.0f} {llm.usage['out'] / calls:13.0f}")


def bench_agent():
    print(f"\nScripted agent conversation (thinking={config.GEMINI_THINKING}, fastpath={config.FASTPATH}, phrase_all={config.PHRASE_ALL})")
    conn, llm, s = copy_db(DB_PATH), EvalGemini(), Session(user_id="latency")
    total = 0.0
    print(f"{'user message':32} {'secs':>5} {'LLM calls':>9}  rule")
    for msg in SCRIPT:
        c0 = llm.usage["calls"]
        t0 = time.perf_counter()
        r = handle(s, msg, llm, conn)
        dt = time.perf_counter() - t0
        total += dt
        tag = (r.policy or {}).get("rule", "") + (" (fast)" if (r.policy or {}).get("fast") else "")
        print(f"{msg:32} {dt:5.1f} {llm.usage['calls'] - c0:9}  {tag}")
    print(f"{'total':32} {total:5.1f} {llm.usage['calls']:9}  thinking tokens used: {llm.usage['thought']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default="low,medium,high")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--skip-levels", action="store_true")
    a = ap.parse_args()
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("Set GEMINI_API_KEY first.")
    if not DB_PATH.exists():
        sys.exit("Catalog missing. Run: python -m data.seed")
    if not a.skip_levels:
        bench_levels(a.levels.split(","), a.repeats)
    bench_agent()
