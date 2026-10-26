
from app.catalog.search import get_shoes_by_ids
from app.engine.engine import handle
from app.engine.state import Session
from app.profile.model import Profile
from app.profile.ranking import PALETTES, color_score, explain, rerank
from tests.fakes import FakeLLM

BANNED = ("won't suit", "wont suit", "doesn't suit", "does not suit", "not suit you", "bad for you", "ugly")


def profile(undertone=None, **colors):
    p = Profile()
    if undertone:
        p.set("undertone", undertone, "confirmed")
    for c in colors.get("liked", []):
        p.set_color(c, True, "stated")
    for c in colors.get("rejected", []):
        p.set_color(c, False, "stated")
    return p


def test_palettes_score_as_designed():
    assert color_score(profile("warm"), "brown") == 2 and color_score(profile("warm"), "black") == 1
    assert color_score(profile("cool"), "navy") == 2 and color_score(profile("cool"), "brown") == 0
    assert color_score(profile(rejected=["red"]), "red") < 0


def test_same_query_ranks_differently_for_different_profiles(conn):
    results = {}
    for name, undertone in (("w", "warm"), ("c", "cool")):
        s = Session(profile=profile(undertone))
        r = handle(s, "sports shoes, size 9", FakeLLM(), conn)
        results[name] = (r.ui_action.product_ids, r.reply)
    warm_ids, cool_ids = results["w"][0], results["c"][0]
    assert warm_ids != cool_ids
    def total(ids, under):
        return sum(color_score(profile(under), s["color"]) for s in get_shoes_by_ids(conn, ids))
    assert total(warm_ids, "warm") > total(cool_ids, "warm")
    assert total(cool_ids, "cool") > total(warm_ids, "cool")


def test_reply_explains_why_in_soft_language(conn):
    for undertone in PALETTES:
        r = handle(Session(profile=profile(undertone)), "sports shoes, size 9", FakeLLM(), conn)
        assert "tend to" in r.reply and f"{undertone} undertone" in r.reply
        assert not any(b in r.reply.lower() for b in BANNED)


def test_explanation_only_names_colors_that_are_on_screen(conn):
    rows = [{"color": "navy"}, {"color": "black"}]
    note = explain(rows, profile("warm"))
    assert "brown" not in note.split("because")[0] and "pairs up" not in note  # no warm-best color shown


def test_no_profile_means_no_reranking_or_explanation(conn):
    r = handle(Session(), "sports shoes, size 9", FakeLLM(), conn)
    assert "I've moved" not in r.reply and "favoured" not in r.reply


def test_rejected_color_sinks_and_liked_color_rises(conn):
    base = handle(Session(), "sports shoes, size 9", FakeLLM(), conn).ui_action.product_ids
    colors = [s["color"] for s in get_shoes_by_ids(conn, base)]
    target = colors[0]
    sunk = handle(Session(profile=profile(rejected=[target])), "sports shoes, size 9", FakeLLM(), conn)
    top_colors = [s["color"] for s in get_shoes_by_ids(conn, sunk.ui_action.product_ids)]
    assert target not in top_colors and "pushed" in sunk.reply
    liked = "olive" if "olive" not in colors else "tan"
    raised = handle(Session(profile=profile(liked=[liked])), "sports shoes, size 9", FakeLLM(), conn)
    assert liked in [s["color"] for s in get_shoes_by_ids(conn, raised.ui_action.product_ids)]


def test_rerank_is_stable_for_ties():
    rows = [{"color": "navy", "price": 1, "id": i} for i in range(5)]
    assert [r["id"] for r in rerank(rows, profile("warm"), 5)] == list(range(5))
