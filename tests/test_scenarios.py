"""The 8 demo scenarios from the README, end to end through the engine."""
from app.catalog.search import get_shoes_by_ids
from app.engine import cart
from app.engine.engine import handle
from app.engine.state import Session
from app.profile import store
from tests.fakes import FakeLLM, HallucinatingLLM


class Chat:
    def __init__(self, conn, session=None, llm=None):
        self.conn, self.s, self.llm = conn, session or Session(user_id="u1"), llm or FakeLLM()

    def say(self, text, focus=None):
        return handle(self.s, text, self.llm, self.conn, focus_id=focus)


def browse(c):
    c.say("hi")
    c.say("I want sports shoes")
    c.say("for me")
    return c.say("9")


def test_1_happy_path_hi_to_confirmed_order(conn):
    c = Chat(conn)
    r = browse(c)
    assert r.ui_action.type == "show_products" and len(r.ui_action.product_ids) >= 2
    pid = r.ui_action.product_ids[1]
    r = c.say("tell me about the second one")
    assert r.ui_action.type == "focus_product" and r.ui_action.product_id == pid
    shoe = get_shoes_by_ids(conn, [pid])[0]
    r = c.say("what do you think of it?")
    assert f"₹{shoe['price']:,}" in r.reply
    r = c.say("buy this")
    assert r.ui_action.type == "checkout" and c.s.awaiting_confirm
    r = c.say("yes, place the order")
    assert r.ui_action.order_id and "mock" in r.reply
    assert cart.get_order(conn, r.ui_action.order_id)["items"][0]["shoe_id"] == pid
    assert store.get_size(conn, "u1") == 9.0


def test_2_size_up_front(conn):
    r = Chat(conn).say("sports shoes, size 9")
    assert r.ui_action.type == "show_products" and r.slots.for_whom == "self"


def test_3_shopping_for_someone_else_keeps_profile(conn):
    store.save_size(conn, "u1", 8.0)
    c = Chat(conn, Session(user_id="u1", profile_size=8.0))
    r = c.say("casual shoes for my brother")
    assert "size" in r.reply and r.ui_action.type == "none"
    r = c.say("10")
    c.say("show me the first one")
    c.say("buy this")
    r = c.say("yes")
    assert r.ui_action.order_id
    assert store.get_size(conn, "u1") == 8.0 and c.s.profile_size == 8.0


def test_4_change_of_mind_keeps_size(conn):
    c = Chat(conn)
    c.say("sports shoes, size 9")
    r = c.say("actually office")
    assert r.ui_action.filters["use"] == "office" and r.ui_action.filters["size"] == 9.0


def test_5_off_topic_does_not_hijack(conn):
    c = Chat(conn)
    c.say("sports shoes")
    r = c.say("what's the weather like?")
    assert r.ui_action.type == "none" and c.s.slots.use == "sports"


def test_6_no_thanks_backs_off_and_cancels_confirmation(conn):
    c = Chat(conn)
    c.say("sports shoes, size 9")
    c.say("show me the first one")
    c.say("buy this")
    assert c.s.awaiting_confirm
    r = c.say("no thanks")
    assert not c.s.awaiting_confirm and "?" not in r.reply and r.ui_action.type == "none"
    assert c.say("yes").ui_action.order_id is None  # a stray "yes" no longer places an order


def test_7_out_of_stock_is_honest(conn):
    c = Chat(conn)
    pid = browse(c).ui_action.product_ids[0]
    conn.execute("UPDATE stock SET qty=0 WHERE shoe_id=? AND size=9", (pid,))
    r = c.say("buy this", focus=pid)
    assert "isn't available in size 9" in r.reply and not c.s.awaiting_confirm and not c.s.cart


def test_8_price_objection_and_refinement(conn):
    c = Chat(conn)
    first = browse(c).ui_action.product_ids
    top = max(p["price"] for p in get_shoes_by_ids(conn, first))
    r = c.say("show me something cheaper")
    assert r.ui_action.filters["max_price"] == int(top * 0.8)
    cheaper = r.ui_action.product_ids
    assert all(p["price"] <= int(top * 0.8) for p in get_shoes_by_ids(conn, cheaper))
    more = c.say("show more options").ui_action.product_ids
    assert more and not set(more) & set(cheaper)
    colors = {p["color"] for p in get_shoes_by_ids(conn, more)}
    other = c.say("any other colors?").ui_action.product_ids
    assert not colors & {p["color"] for p in get_shoes_by_ids(conn, other)}


def test_size_asked_when_buying_without_one(conn):
    c = Chat(conn)
    c.say("sports shoes")
    c.say("for me")
    r = c.say("show me the first one")  # no results yet, so nothing to focus
    assert "Which shoe" in r.reply
    pid = conn.execute("SELECT id FROM shoes WHERE use_type='sports' LIMIT 1").fetchone()["id"]
    r = c.say("buy this", focus=pid)
    assert "size" in r.reply and c.s.pending == (pid, True)


def test_grounding_strips_hallucinated_opinion(conn):
    c = Chat(conn, llm=HallucinatingLLM())
    pid = browse(c).ui_action.product_ids[0]
    shoe = get_shoes_by_ids(conn, [pid])[0]
    r = c.say("what do you think of it?", focus=pid)
    assert "99,999" not in r.reply and f"₹{shoe['price']:,}" in r.reply
    assert not any(b in r.reply for b in ("Nike would", "Clarks would"))
