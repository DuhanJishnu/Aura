"""Regression tests for the price-objection failures in the second real evaluation run.

The shopper looked at six office shoes in size 11, said the ₹1,999 Hush Puppies Derby was too pricey and asked for
something clearly cheaper. The agent claimed to show cheaper options but showed MORE expensive ones, because it
could not tell which Derby (two were on screen) the shopper meant, and lowered the range from the priciest shoe."""
import pytest

from app.catalog.search import get_shoes_by_ids
from app.engine.engine import handle
from app.engine.resolve import resolve_by_price, resolve_mentions
from app.engine.state import Session
from app.llm.schemas import Extraction
from tests.fakes import FakeLLM

MSG = ("That Hush Puppies Derby at ₹1,999 is a bit too pricey for me. "
       "Do you have anything clearly cheaper that works for the office in a size 11?")


class GeminiLike(FakeLLM):
    """Returns what Gemini actually returned in the failing runs, whatever the message says."""

    def __init__(self, ex):
        self.ex = ex

    def extract(self, message, known):
        return self.ex


def office_session(conn):
    s = Session(user_id="u")
    r = handle(s, "office shoes, size 11", FakeLLM(), conn)
    assert r.ui_action.product_ids == [179, 282, 27, 141, 148, 264]  # the same six the shopper saw
    return s


def prices(conn, ids):
    return [x["price"] for x in get_shoes_by_ids(conn, ids)]


@pytest.mark.parametrize("label", [
    Extraction(intent="refine", refine="cheaper"),                         # what Gemini returned
    Extraction(intent="refine", refine="cheaper", budget=1999),            # or with the quoted price as a budget
    Extraction(intent="object", objection="price"),                        # or labelled as an objection
])
def test_named_shoe_price_complaint_gets_cheaper_alternatives_than_that_shoe(conn, label):
    s = office_session(conn)
    r = handle(s, MSG, GeminiLike(label), conn)
    assert r.policy["action"] == "objection"
    ids = r.ui_action.product_ids
    assert r.ui_action.type == "show_products" and ids[0] == 179           # the Derby they named, then alternatives
    alts = get_shoes_by_ids(conn, ids[1:])
    assert alts and all(a["price"] < 1999 and 11.0 in a["sizes_in_stock"] and a["use_type"] == "office" for a in alts)
    assert 203 in ids                                                       # Clarks Derby, ₹1,599, rated 4.6
    assert "cheaper than" not in r.reply.lower() or all(p < 1999 for p in prices(conn, ids[1:]))


def test_the_same_complaint_by_color_or_by_price_only(conn):
    for msg in ("The grey Hush Puppies Derby is too pricey, anything cheaper?", "That ₹1,999 pair is too pricey, anything cheaper?"):
        r = handle(office_session(conn), msg, GeminiLike(Extraction(intent="refine", refine="cheaper")), conn)
        assert r.policy["action"] == "objection" and r.ui_action.product_ids[0] == 179, msg


def test_the_fit_question_about_the_recommended_derby_is_no_longer_ambiguous(conn):
    # two Hush Puppies Derbys were on screen (grey 179 and navy 148); the assistant had just named the grey one
    s = office_session(conn)
    msg = "The Hush Puppies Derby looks like a solid option! Do you know if they run small at all?"
    r = handle(s, msg, GeminiLike(Extraction(intent="object", objection="fit")), conn)
    assert "Which pair" not in r.reply and r.ui_action.product_id == 179 and "don't have fit" in r.reply


def test_a_general_cheaper_request_states_its_ceiling(conn):
    s = office_session(conn)
    r = handle(s, "show me something cheaper", GeminiLike(Extraction(intent="refine", refine="cheaper")), conn)
    ceiling = r.ui_action.filters["max_price"]
    assert f"₹{ceiling:,} or less" in r.reply and max(prices(conn, r.ui_action.product_ids)) <= ceiling


# ---- resolution rules ----
SHOES = [
    {"id": 1, "name": "Hush Puppies Derby", "color": "grey", "price": 1999},
    {"id": 2, "name": "Hush Puppies Derby", "color": "navy", "price": 2299},
    {"id": 3, "name": "Red Tape Brogue", "color": "white", "price": 3399},
]
COLORS = {"grey", "navy", "white"}


def test_duplicate_models_resolve_by_quoted_price_then_by_the_assistants_top_pick():
    assert [s["id"] for s in resolve_mentions("the Hush Puppies Derby at ₹2,299", SHOES, COLORS)] == [2]
    assert [s["id"] for s in resolve_mentions("the Hush Puppies Derby", SHOES, COLORS, prefer_id=1)] == [1]
    assert resolve_mentions("the Hush Puppies Derby", SHOES, COLORS) == []              # still ambiguous: ask


def test_price_only_reference_needs_exactly_one_match():
    assert [s["id"] for s in resolve_by_price("the 3,399 one", SHOES)] == [3]
    assert resolve_by_price("the 5000 one", SHOES) == []


# ---- evaluation fixes from the same run ----
def test_honesty_is_scored_even_when_the_shopper_paraphrases_the_budget(conn):
    from eval.metrics import Ctx, score
    from eval.types import Conversation, Persona, Turn
    p = Persona("e", "sizing_stock", "office", 11.0, 1399, "self", "fit", "x", None, "", True)
    turns = [Turn("user", "office shoes"), Turn("assistant", "Here are some.", shown_ids=[179]),
             Turn("user", "anything in size 11 under ₹1,400?"),   # persona budget was 1399
             Turn("assistant", "I am sorry, but we do not have anything in stock that matches all of your filters."),
             Turn("user", "thanks for being upfront, I'll pass"), Turn("assistant", "No worries at all.")]
    s = score(Conversation(p, "agent", turns, {"outcome": "no_buy"}), Ctx(conn))
    assert s["honest_empty"] is True and s["success"] is True


def test_price_objection_personas_are_always_satisfiable(conn):
    from app.catalog.search import search_shoes
    from eval.personas import availability, generate
    av = availability(conn)
    for p in (x for x in generate(conn, 80, seed=5) if x.category == "price_objection"):
        cat = getattr(p, "product_category", "shoes")
        sz = None if cat == "accessories" else p.size
        top = search_shoes(conn, use=p.use, size=sz, category=cat, limit=1)[0]
        assert sum(1 for x in av[(p.use, p.size)] if x <= top["price"] * 0.9) >= 2, p
