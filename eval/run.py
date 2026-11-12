"""Run Google ADK Stylist evaluations (offline deterministic check or live Gemini + ADK AgentEvaluator).

Usage:
    python -m eval.run --offline
    python -m eval.run --live
    python -m eval.run --adk-eval   # runs google.adk.evaluation.AgentEvaluator on eval/adk_eval/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from eval.metrics import ScenarioResult, evaluate_scenario
from eval.personas import SCENARIOS
from eval.systems import AdkStylistEvalSystem, PlainPromptBaseline


async def run_suite(offline: bool = True, include_baseline: bool = False) -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    systems = ["adk_stylist"] + (["plain_baseline"] if include_baseline else [])

    for sys_name in systems:
        for sc in SCENARIOS:
            uid = f"{sys_name}_{sc.id}"
            sys_impl = (
                AdkStylistEvalSystem(uid, offline=offline)
                if sys_name == "adk_stylist"
                else PlainPromptBaseline(uid, offline=offline)
            )
            await sys_impl.setup_swipes(sc.pre_swipe_likes, sc.pre_swipe_dislikes)
            t0 = time.perf_counter()
            responses = []
            for msg in sc.turns:
                responses.append(await sys_impl.turn(msg))
            dt = time.perf_counter() - t0
            results.append(evaluate_scenario(sc, sys_impl.name, responses, dt))
    return results


async def run_adk_evaluator() -> None:
    from google.adk.evaluation.agent_evaluator import AgentEvaluator

    eval_path = str(Path(__file__).resolve().parent / "adk_eval" / "stylist.evalset.json")
    await AgentEvaluator.evaluate(
        agent_module="stylist_agent",
        eval_dataset_file_path_or_dir=eval_path,
        num_runs=1,
    )


def summarize(results: list[ScenarioResult]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    avg_lat = round(sum(r.latency_s for r in results) / max(total, 1), 3)
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / max(total, 1), 3),
        "avg_latency_s": avg_lat,
        "cases": [
            {
                "id": r.scenario_id,
                "system": r.system,
                "passed": r.passed,
                "scores": r.scores,
                "notes": r.notes,
                "latency_s": r.latency_s,
            }
            for r in results
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="Run deterministic offline stylist eval (no API key)")
    ap.add_argument("--live", action="store_true", help="Run live Gemini + Google Search eval")
    ap.add_argument("--baseline", action="store_true", help="Include plain no-tool baseline comparison")
    ap.add_argument("--adk-eval", action="store_true", help="Run native Google ADK AgentEvaluator")
    ap.add_argument("--out", default="eval/latest_report.json", help="Path to write JSON summary")
    args = ap.parse_args()

    if args.adk_eval:
        asyncio.run(run_adk_evaluator())
        return 0

    offline = not args.live
    results = asyncio.run(run_suite(offline=offline, include_baseline=args.baseline))
    summary = summarize(results)
    Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Eval complete ({'offline' if offline else 'live'}): {summary['passed']}/{summary['total']} passed (rate={summary['pass_rate']})")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.system} :: {r.scenario_id} -> {r.scores}" + (f" | {r.notes}" if r.notes else ""))
    adk_cases = [r for r in results if r.system.startswith("adk_stylist")]
    return 0 if all(r.passed for r in adk_cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
