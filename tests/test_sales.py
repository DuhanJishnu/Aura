import pytest

from app.catalog.search import get_shoes_by_ids
from app.engine.engine import handle
from app.engine.state import Session
from tests.fakes import FakeLLM, HallucinatingLLM


class Chat:
    def __init__(self, conn, llm=None):
        self.conn, self.s, self.llm = conn, Session(user_id="u1"), llm or FakeLLM()

    def say(self, text, focus=None):
        return handle(self.s, text, self.llm, self.conn, focus_id=focus)


def browse(c):
    c.say("hi")
    c.say("I want sports shoes")
    c.say("for me")
    return c.say("9").ui_action.product_ids


def priciest(conn, ids):
    return max(get_shoes_by_ids(conn, ids), key=lambda s: s["price"])


def cheapest_sports_in_9(conn):
    return conn.execute(
        "SELECT s.id FROM shoes s JOIN stock k ON k.shoe_id=s.id "
        "WHERE s.use_type='sports' AND k.size=9 AND k.qty>0 ORDER BY s.price ASC LIMIT 1"
    ).fetchone()["id"]


# ---- objections ----
def test_price_objection_gives_cheaper_in_size_alternatives_without_pushing(conn):
    c = Chat(conn)
    top = priciest(conn, browse(c))
    r = c.say("that's too expensive", focus=top["id"])
    assert r.policy["action"] == "objection" and r.ui_action.type == "show_products"
    ids = r.ui_action.product_ids
    assert ids[0] == top["id"] and len(ids) > 1
    for alt in get_shoes_by_ids(conn, ids[1:]):
        assert alt["price"] < top["price"] and 9.0 in alt["sizes_in_stock"] and alt["use_type"] == "sports"
    assert "buy" not in r.reply.lower() and not c.s.awaiting_confirm


def test_price_objection_about_whole_list_lowers_price_range(conn):
    c = Chat(conn)
    top = priciest(conn, browse(c))
    r = c.say("too expensive")
    assert r.ui_action.filters["max_price"] == int(top["price"] * 0.8)


def test_price_objection_on_cheapest_is_honest(conn):
    c = Chat(conn)
    c.say("sports shoes, size 9")
    r = c.say("too expensive", focus=cheapest_sports_in_9(conn))
    assert r.ui_action.type == "focus_product" and not r.ui_action.product_ids
    assert "lowest priced" in r.reply or "cheapest" in r.reply


def test_price_objection_ignores_invented_numbers(conn):
    c = Chat(conn, HallucinatingLLM())
    top = priciest(conn, browse(c))
    r = c.say("too expensive", focus=top["id"])
    assert "99,999" not in r.reply and f"₹{top['price']:,}" in r.reply


def test_fit_objection_admits_missing_data_and_lists_sizes(conn):
    c = Chat(conn)
    pid = browse(c)[0]
    r = c.say("will it fit? I'm unsure about my size", focus=pid)
    assert "don't have fit" in r.reply and "in stock in sizes" in r.reply
    assert r.ui_action.type == "focus_product"


def test_quality_objection_admits_no_durability_data(conn):
    c = Chat(conn)
    pid = browse(c)[0]
    r = c.say("will it last?", focus=pid)
    assert "durability" in r.reply


def test_quality_objection_fallback_when_llm_invents(conn):
    c = Chat(conn, HallucinatingLLM())
    pid = browse(c)[0]
    r = c.say("will it last?", focus=pid)
    assert "99,999" not in r.reply and "durability" in r.reply


# ---- compare ----
def test_compare_named_positions(conn):
    c = Chat(conn)
    ids = browse(c)
    r = c.say("compare the first and third")
    assert r.ui_action.type == "compare" and r.ui_action.product_ids == [ids[0], ids[2]]
    shoes = get_shoes_by_ids(conn, r.ui_action.product_ids)
    assert all(s["name"] in r.reply for s in shoes)


def test_compare_defaults_to_top_two_and_says_so(conn):
    c = Chat(conn)
    ids = browse(c)
    r = c.say("compare these")
    assert r.ui_action.product_ids == ids[:2] and "top two" in r.reply


def test_compare_needs_options_first(conn):
    r = Chat(conn).say("compare the first and second")
    assert r.ui_action.type == "none" and "Show me a few options" in r.reply


def test_compare_strips_hallucinations(conn):
    c = Chat(conn, HallucinatingLLM())
    browse(c)
    r = c.say("compare the first and second")
    assert "99,999" not in r.reply and "far better" not in r.reply and r.ui_action.type == "compare"


# ---- browsing / rejecting ----
def test_browsing_is_relaxed_and_asks_nothing(conn):
    c = Chat(conn)
    r = c.say("I'm bored")
    assert r.policy["action"] == "discover" and r.ui_action.type == "show_products"
    uses = {s["use_type"] for s in get_shoes_by_ids(conn, r.ui_action.product_ids)}
    assert uses == {"sports", "office", "casual"}
    assert "?" not in r.reply and c.s.slots.use is None and c.s.slots.size is None
    assert c.say("tell me about the second one").ui_action.type == "focus_product"


def test_reject_item_drops_it_without_pitching(conn):
    c = Chat(conn)
    ids = browse(c)
    r = c.say("not this one", focus=ids[0])
    assert ids[0] in c.s.rejected and ids[0] not in c.s.shortlist and "?" not in r.reply
    assert ids[0] not in c.say("show more options").ui_action.product_ids


# ---- a "no" is always respected ----
@pytest.mark.parametrize("setup", ["midflow", "after_objection", "awaiting_confirm", "after_browse"])
def test_no_is_always_respected(conn, setup):
    c = Chat(conn)
    if setup == "midflow":
        c.say("sports shoes")
    elif setup == "after_objection":
        c.say("too expensive", focus=browse(c)[0])
    elif setup == "awaiting_confirm":
        browse(c)
        c.say("show me the first one")
        c.say("buy this")
        assert c.s.awaiting_confirm
    else:
        c.say("I'm just looking")
    cart_before = len(c.s.cart)
    assert c.say("no thanks").policy["rule"] == "no_means_no" and not c.s.awaiting_confirm
    for msg in ["ok", "thanks", "hi", "yes", "hmm", "cool"]:
        r = c.say(msg)
        assert r.policy["rule"] == "passive_after_no", msg
        assert "?" not in r.reply and r.ui_action.type == "none"
    assert len(c.s.cart) == cart_before and not c.s.awaiting_confirm
    assert c.say("sports shoes, size 9").ui_action.type == "show_products"  # re-engaging works


def test_no_inside_an_objection_wins(conn):
    c = Chat(conn)
    browse(c)
    r = c.say("too expensive, no thanks")
    assert r.policy["rule"] == "no_means_no" and r.ui_action.type == "none" and "?" not in r.reply


def test_off_topic_after_no_is_answered_not_pitched(conn):
    c = Chat(conn)
    c.say("sports shoes")
    c.say("no thanks")
    r = c.say("what's the weather like?")
    assert r.policy["action"] == "answer" and r.ui_action.type == "none"
