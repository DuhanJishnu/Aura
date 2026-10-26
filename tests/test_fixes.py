"""Regression tests for problems found in the first real evaluation run."""
import json

from app.catalog.search import get_shoes_by_ids
from app.engine.engine import handle
from app.engine.resolve import resolve_mentions
from app.engine.state import Session
from eval.metrics import DECLINE, Ctx, score
from eval.personas import generate
from eval.run import converse_llm, run_eval
from eval.simulators import UserTurn
from eval.types import Conversation, Persona, Turn
from tests.fakes import FakeLLM

COLORS = {"black", "brown", "red", "grey", "navy", "white", "olive", "tan"}
SHOES = [
    {"id": 1, "name": "Red Tape Oxford", "color": "black", "price": 2999},
    {"id": 2, "name": "Red Tape Oxford", "color": "navy", "price": 3199},
    {"id": 3, "name": "Woodland Brogue", "color": "brown", "price": 2499},
    {"id": 4, "name": "Hush Puppies Derby", "color": "grey", "price": 1999},
    {"id": 5, "name": "Vans Canvas Low", "color": "black", "price": 1399},
]


def ids(msg, shoes=SHOES):
    return [s["id"] for s in resolve_mentions(msg, shoes, COLORS)]


# ---- shoppers who name a shoe instead of giving a position ----
def test_name_with_color_between_brand_and_model_and_plurals():
    assert ids("I like the Red Tape black Oxfords") == [1]
    assert ids("the grey Hush Puppies Derby is too expensive") == [4]


def test_brand_word_red_is_not_read_as_a_color():
    assert ids("tell me about the Red Tape navy Oxford") == [2]


def test_ambiguous_or_unknown_names_resolve_to_nothing():
    assert ids("the Red Tape Oxford") == []          # two colors on screen: don't guess
    assert ids("the Nike Pegasus") == []


def test_two_names_in_one_message():
    assert ids("compare the black Red Tape Oxfords and the Woodland brown Brogues") == [1, 3]


def browse(conn):
    s = Session(user_id="u1")
    for msg in ("sports shoes", "for me", "9"):
        r = handle(s, msg, FakeLLM(), conn)
    return s, r.ui_action.product_ids


def test_compare_by_name_through_the_engine(conn):
    s, shown = browse(conn)
    shoes = get_shoes_by_ids(conn, shown)
    a, b = next((x, y) for x in shoes for y in shoes if x["name"] != y["name"] and x["id"] < y["id"])
    r = handle(s, f"compare the {a['color']} {a['name']} and the {b['color']} {b['name']}", FakeLLM(), conn)
    assert r.ui_action.type == "compare" and set(r.ui_action.product_ids) == {a["id"], b["id"]}
    assert "top two" not in r.reply


def test_buy_by_name_adds_that_shoe(conn):
    s, shown = browse(conn)
    target = get_shoes_by_ids(conn, shown)[3]
    r = handle(s, f"I'll take the {target['color']} {target['name']}", FakeLLM(), conn)
    assert r.ui_action.type == "checkout" and [i.shoe_id for i in s.cart] == [target["id"]]


# ---- "cheaper" semantics ----
class RefineLLM(FakeLLM):
    def __init__(self, **kw):
        self.kw = kw

    def extract(self, message, known):
        from app.llm.schemas import Extraction
        return Extraction(intent="refine", refine="cheaper", **self.kw)


def test_explicit_budget_is_applied_as_stated_not_shrunk(conn):
    s, _ = browse(conn)
    r = handle(s, "under 3000 please", RefineLLM(budget=3000), conn)
    assert r.ui_action.filters["max_price"] == 3000


def test_cheaper_is_relative_to_the_shoe_being_discussed(conn):
    s, shown = browse(conn)
    cheapest, priciest = sorted(get_shoes_by_ids(conn, shown), key=lambda x: x["price"])[0], max(get_shoes_by_ids(conn, shown), key=lambda x: x["price"])
    assert cheapest["price"] < priciest["price"]
    s.focused_id = cheapest["id"]  # talking about the cheapest shoe on screen
    r = handle(s, "cheaper please", RefineLLM(), conn)
    assert r.ui_action.filters.get("max_price") == int(cheapest["price"] * 0.8)  # not 80% of the priciest


def test_show_replies_pass_top_picks_to_the_llm(conn):
    seen = {}

    class Spy(FakeLLM):
        def phrase(self, instruction, context, fallback):
            seen.update(context)
            return fallback

    handle(Session(), "sports shoes, size 9", Spy(), conn)
    assert len(seen["top_picks"]) == 3 and {"name", "price", "rating"} <= set(seen["top_picks"][0])


# ---- scoring fixes ----
def test_frustrated_stop_wasting_my_time_is_not_a_no():
    assert not DECLINE.search("stop wasting my time and show me something")
    assert DECLINE.search("no thanks") and DECLINE.search("please stop pitching")


def empty_persona():
    return Persona("e", "sizing_stock", "office", 11.0, 1399, "self", "fit", "x", None, "", True)


def test_honesty_is_judged_on_the_reply_to_the_budget_message(conn):
    turns = [Turn("user", "office shoes size 11"), Turn("assistant", "Here are some.", shown_ids=[1]),
             Turn("user", "under 1399 though"), Turn("assistant", "I don't have anything under ₹1,399 in size 11.")]
    s = score(Conversation(empty_persona(), "agent", turns, {"outcome": "no_buy"}), Ctx(copy_db_path(conn)))
    assert s["honest_empty"] is True and s["success"] is True
    turns[3] = Turn("assistant", "Try these!", shown_ids=[2])
    assert score(Conversation(empty_persona(), "agent", turns, {"outcome": "no_buy"}), Ctx(copy_db_path(conn)))["honest_empty"] is False


def copy_db_path(conn):
    return conn


def test_a_friendly_steer_back_to_shoes_is_not_a_hijack(conn):
    p = Persona("o", "off_topic", "casual", 9.0, None, "self", None, "capital?", "capital?", "")
    turns = [Turn("user", "what's the capital of France?"), Turn("assistant", "Paris! Anything I can help you find in shoes?")]
    assert score(Conversation(p, "plain", turns, {"outcome": "no_buy"}), Ctx(conn))["hijacked"] is False
    turns[1] = Turn("assistant", "Paris! Look at these.", shown_ids=[1])
    assert score(Conversation(p, "plain", turns, {"outcome": "no_buy"}), Ctx(conn))["hijacked"] is True


# ---- harness ----
class Bot:
    def __init__(self):
        self.got = []

    def respond(self, msg):
        self.got.append(msg)
        return Turn("assistant", "ok", order_id="ORD-1" if "place the order" in msg else None)


class StubUser:
    def __init__(self, script):
        self.script = list(script)

    def next(self, transcript, force_end=False):
        return self.script.pop(0)


def test_the_closing_message_reaches_the_system(conn):
    conv, bot = Conversation(generate(conn, 1)[0], "agent"), Bot()
    user = StubUser([UserTurn(message="buy this"), UserTurn(message="yes, place the order", end=True, outcome="buy")])
    converse_llm(conv, bot, user, conn, 12)
    assert bot.got == ["buy this", "yes, place the order"]
    assert conv.verdict["outcome"] == "buy" and conv.turns[-1].order_id == "ORD-1"


def test_resume_reruns_failed_conversations_only(tmp_path):
    from data.seed import seed
    db = tmp_path / "s.db"
    seed(path=db)
    run_eval(["agent"], 8, "scripted", True, db, tmp_path)
    path = tmp_path / "transcripts.jsonl"
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    lines[0]["error"] = "429 spending cap"
    lines[0]["turns"] = []
    failed = (lines[0]["system"], lines[0]["persona"]["id"])
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    run_eval(["agent"], 8, "scripted", True, db, tmp_path, resume=True)
    after = [json.loads(x) for x in path.read_text().splitlines()]
    assert len(after) == 8 and not any(x["error"] for x in after)
    redone = next(x for x in after if (x["system"], x["persona"]["id"]) == failed)
    assert redone["turns"]
