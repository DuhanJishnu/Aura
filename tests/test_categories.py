"""Apparel and accessories run through the same engine as shoes."""
import sqlite3

from app.catalog.db import init_db
from app.catalog.search import get_shoe, get_shoes_by_ids, search_shoes
from app.engine.engine import handle
from app.engine.signals import detect_category
from app.engine.state import Session
from app.profile import store
from tests.fakes import FakeLLM, HallucinatingLLM


def run(conn, s, *msgs, llm=None):
    r = None
    for m in msgs:
        r = handle(s, m, llm or FakeLLM(), conn)
    return r


def cats(conn, ids):
    return {x["category"] for x in get_shoes_by_ids(conn, ids)}


# ---- catalog ----
def test_catalog_has_three_categories_and_the_shoes_are_unchanged(conn):
    counts = dict(conn.execute("SELECT category, COUNT(*) FROM shoes GROUP BY category").fetchall())
    assert counts == {"shoes": 300, "apparel": 90, "accessories": 60}
    derby = get_shoe(conn, 179)
    assert (derby["name"], derby["price"], derby["category"]) == ("Hush Puppies Derby", 1999, "shoes")  # ids and data stable
    apparel_sizes = {r[0] for r in conn.execute("SELECT DISTINCT size FROM stock s JOIN shoes h ON h.id=s.shoe_id WHERE h.category='apparel'")}
    assert apparel_sizes == {1.0, 2.0, 3.0, 4.0, 5.0, 6.0}
    assert {r[0] for r in conn.execute("SELECT DISTINCT size FROM stock s JOIN shoes h ON h.id=s.shoe_id WHERE h.category='accessories'")} == {0.0}


def test_search_defaults_to_shoes_and_filters_by_category(conn):
    assert {r["category"] for r in search_shoes(conn, limit=50)} == {"shoes"}
    assert {r["category"] for r in search_shoes(conn, category="apparel", limit=50)} == {"apparel"}
    assert {r["category"] for r in search_shoes(conn, category=None, limit=400)} == {"shoes", "apparel", "accessories"}


def test_an_old_catalog_without_the_category_column_is_migrated():
    old = sqlite3.connect(":memory:")
    old.executescript("CREATE TABLE shoes (id INTEGER PRIMARY KEY, name TEXT NOT NULL, brand TEXT NOT NULL, price INTEGER NOT NULL,"
                      " use_type TEXT NOT NULL, color TEXT NOT NULL, rating REAL NOT NULL DEFAULT 4.0, image TEXT, description TEXT NOT NULL);"
                      "INSERT INTO shoes VALUES (1,'Nike Runner','Nike',3999,'sports','black',4.5,'x','d');")
    init_db(old)
    assert old.execute("SELECT category FROM shoes WHERE id=1").fetchone()[0] == "shoes"


def test_category_words():
    assert detect_category("I need a casual shirt") == "apparel" and detect_category("running shorts") == "apparel"
    assert detect_category("a leather belt and a watch") == "accessories"   # two words from one category are fine...
    assert detect_category("a laptop bag") == "accessories" and detect_category("some sneakers") == "shoes"
    assert detect_category("a shirt and some shoes") is None                # ...but two categories are ambiguous
    assert detect_category("something nice for the office") is None


# ---- apparel ----
def test_apparel_flow_uses_letter_sizes_and_ignores_the_saved_shoe_size(conn):
    s = Session(user_id="u", profile_size=9.0)
    r = run(conn, s, "I need a casual shirt", "for me")
    assert s.slots.category == "apparel" and s.slots.size is None            # the shoe size 9 was not applied
    assert "XS, S, M, L, XL or XXL" in r.reply and r.ui_action.type == "none"
    r = run(conn, s, "M")                                                    # fast path: a bare letter once we are in apparel
    assert r.policy["fast"] is True and s.slots.size == 3.0
    ids = r.ui_action.product_ids
    assert ids and cats(conn, ids) == {"apparel"} and r.ui_action.filters["category"] == "apparel"
    assert all(3.0 in x["sizes_in_stock"] for x in get_shoes_by_ids(conn, ids))


def test_apparel_purchase_reads_in_letters_and_never_saves_a_shoe_size(conn):
    s = Session(user_id="u")
    run(conn, s, "a casual shirt in medium")
    r = run(conn, s, "show me the first one", "buy this")
    assert "in size M " in r.reply and "size 3" not in r.reply
    r = run(conn, s, "yes, place the order")
    assert r.ui_action.order_id and "saved shoe size" not in r.reply
    assert store.get_size(conn, "u") is None and s.profile_size is None


def test_switching_category_resets_the_size(conn):
    s = Session(user_id="u")
    run(conn, s, "sports shoes, size 9")
    assert s.slots.size == 9.0
    r = run(conn, s, "actually I want a sports jacket")
    assert s.slots.category == "apparel" and s.slots.size is None and "XS, S, M" in r.reply


def test_cart_add_across_categories_asks_for_the_right_size_then_finishes(conn):
    s = Session(user_id="u")
    run(conn, s, "sports shoes, size 9")
    jacket = conn.execute("SELECT s.id FROM shoes s JOIN stock k ON k.shoe_id=s.id WHERE s.category='apparel' AND k.size=3 AND k.qty>0 LIMIT 1").fetchone()[0]
    s.shortlist, s.focused_id = [jacket], jacket
    r = run(conn, s, "buy this")
    assert "XS, S, M" in r.reply and s.pending == (jacket, True) and s.slots.category == "apparel"
    r = run(conn, s, "M")
    assert s.cart and s.cart[0].size == 3.0 and s.cart[0].category == "apparel" and "in size M" in r.reply


# ---- accessories ----
def test_accessories_need_no_size_and_check_out_as_one_size(conn):
    s = Session(user_id="u")
    r = run(conn, s, "a casual watch")
    assert s.slots.category == "accessories" and r.ui_action.type == "show_products"      # no size question
    assert cats(conn, r.ui_action.product_ids) == {"accessories"}
    r = run(conn, s, "show me the first one", "buy this")
    assert " in size" not in r.reply and s.cart[0].size == 0.0
    r = run(conn, s, "yes")
    assert r.ui_action.order_id and store.get_size(conn, "u") is None


def test_wording_for_other_categories_does_not_say_shoe(conn):
    s = Session()
    run(conn, s, "a casual shirt in medium")
    r = run(conn, s, "what do you think of the first one?", llm=HallucinatingLLM())
    assert "shoe" not in r.reply.lower() and "made for" in r.reply
    r = run(conn, Session(user_id="u"), "no thanks", llm=FakeLLM())
    assert "shoes" in r.reply or "later" in r.reply
