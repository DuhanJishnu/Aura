import csv
import json

import pytest

from data.seed import seed
from eval.metrics import Ctx, score, wilson
from eval.personas import CATEGORIES, availability, generate
from eval.review import export, summarize
from eval.run import run_eval
from eval.types import Conversation, Persona, Turn


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("evaldb") / "shop.db"
    seed(path=path)
    return path


def test_personas_are_deterministic_feasible_and_cover_every_scenario(db):
    from eval.run import copy_db
    conn = copy_db(db)
    a, b = generate(conn, 48, seed=3), generate(conn, 48, seed=3)
    assert a == b and {p.category for p in a} == set(CATEGORIES)
    av = availability(conn)
    for p in a:
        if p.category in ("rejection", "vague") or p.expected_empty:
            continue
        prices = av[(p.use, p.size)]
        assert prices and (not p.budget or min(prices) <= p.budget), p
    assert all(p.expected_empty for p in a if p.category == "sizing_stock" and p.budget and p.budget < min(av[(p.use, p.size)]))


def test_wilson_interval():
    lo, hi = wilson(8, 10)
    assert 0.49 < lo < 0.50 and 0.94 < hi < 0.95 and wilson(0, 0) == (0.0, 0.0)


def test_offline_agent_run_end_to_end(db, tmp_path):
    res = run_eval(["agent"], 48, sim="scripted", offline=True, db_path=db, out_dir=tmp_path, workers=2)
    o = res["overall"]["agent"]
    assert o["errors"] == 0
    assert o["hallucination"][0] == 0                       # no invented prices
    assert o["respected_no"][0] == o["respected_no"][1] > 0  # every "no" respected
    assert o["not_hijacked"][0] == o["not_hijacked"][1] > 0
    assert o["relevance"] == 1.0                             # everything shown fit the stated constraints
    k, n = o["success"][:2]
    assert k / n >= 0.85, res["by_category"]
    assert o["strict_success"][0] == o["strict_success"][1]  # every real order met the constraints
    assert (tmp_path / "results.md").read_text().startswith("# Evaluation results")
    assert "Limitations" in (tmp_path / "results.md").read_text()


def test_resume_skips_finished_conversations(db, tmp_path):
    run_eval(["agent"], 8, "scripted", True, db, tmp_path)
    before = (tmp_path / "transcripts.jsonl").read_text()
    run_eval(["agent"], 8, "scripted", True, db, tmp_path, resume=True)
    assert (tmp_path / "transcripts.jsonl").read_text() == before


def test_scoring_catches_bad_behaviour(db):
    from eval.run import copy_db
    conn = copy_db(db)
    p = Persona("x", "rejection", None, None, None, "self", None, "hi", None, "", False)
    turns = [Turn("user", "hi"), Turn("assistant", "Hi! What size are you?"), Turn("user", "no thanks"),
             Turn("assistant", "Are you sure? Here are shoes at ₹12,345.", shown_ids=[1])]
    s = score(Conversation(p, "plain", turns, {"outcome": "no_buy"}), Ctx(conn))
    assert s["pitched_after_no"] is True and s["success"] is False and s["hallucinated"] is True


def test_human_review_export_is_stratified_and_summarises(db, tmp_path):
    run_eval(["agent"], 40, "scripted", True, db, tmp_path)
    out = export(tmp_path, 30, db)
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 30 and {r["category"] for r in rows} == set(CATEGORIES)
    for r in rows[:4]:
        r["natural_1to5"], r["helpful_1to5"], r["pressured_yes_no"] = "4", "5", "no"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    s = summarize(tmp_path)
    assert s["agent"]["natural_1to5"] == 4.0 and s["agent"]["pressured"] == 0.0 and s["agent"]["n_rated"] == 4
    json.loads((tmp_path / "results.json").read_text())
