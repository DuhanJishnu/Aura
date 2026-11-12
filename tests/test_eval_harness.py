from __future__ import annotations

from pathlib import Path

import pytest
from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_set import EvalSet

from eval.run import run_suite, summarize


def test_adk_evalset_and_config_valid():
    eval_dir = Path(__file__).resolve().parents[1] / "eval" / "adk_eval"
    eval_set = EvalSet.model_validate_json((eval_dir / "stylist.evalset.json").read_text(encoding="utf-8"))
    eval_cfg = EvalConfig.model_validate_json((eval_dir / "test_config.json").read_text(encoding="utf-8"))
    assert len(eval_set.eval_cases) == 4
    assert eval_cfg.criteria["tool_trajectory_avg_score"] >= 0.8


@pytest.mark.asyncio
async def test_offline_stylist_eval_suite_passes():
    results = await run_suite(offline=True, include_baseline=False)
    summary = summarize(results)
    assert summary["total"] == 8
    assert summary["passed"] == 8, f"Failed eval cases: {[r for r in results if not r.passed]}"
