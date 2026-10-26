from app.engine import cart
from app.engine.state import Session
from app.profile import store


def in_stock(conn, size=9.0):
    return conn.execute("SELECT shoe_id FROM stock WHERE size=? AND qty>0 LIMIT 1", (size,)).fetchone()["shoe_id"]


def qty(conn, shoe_id, size=9.0):
    return conn.execute("SELECT qty FROM stock WHERE shoe_id=? AND size=?", (shoe_id, size)).fetchone()["qty"]


def test_add_view_remove(conn):
    s, pid = Session(), in_stock(conn)
    assert cart.add_item(s, conn, pid, 9.0) == "ok"
    assert cart.add_item(s, conn, pid, 9.0) == "ok" and len(s.cart) == 1  # no duplicates
    assert cart.view(s, conn)["total"] > 0
    assert cart.remove_item(s, pid) and cart.view(s, conn)["items"] == []


def test_out_of_stock_and_unknown(conn):
    pid = conn.execute("SELECT shoe_id FROM stock WHERE size=9 AND qty=0 LIMIT 1").fetchone()["shoe_id"]
    assert cart.add_item(Session(), conn, pid, 9.0) == "out_of_stock"
    assert cart.add_item(Session(), conn, 99999, 9.0) == "unknown"


def test_checkout_decrements_stock_records_order_and_saves_own_size(conn):
    s, pid = Session(user_id="u1"), in_stock(conn)
    before = qty(conn, pid)
    cart.add_item(s, conn, pid, 9.0, "self")
    order = cart.checkout(s, conn)
    assert qty(conn, pid) == before - 1 and s.cart == []
    assert cart.get_order(conn, order["order_id"])["total"] == order["total"]
    assert store.get_size(conn, "u1") == 9.0 and s.profile_size == 9.0


def test_gift_purchase_does_not_touch_profile(conn):
    store.save_size(conn, "u2", 8.0)
    s, pid = Session(user_id="u2", profile_size=8.0), in_stock(conn, 10.0)
    cart.add_item(s, conn, pid, 10.0, "other")
    assert cart.checkout(s, conn)["saved_size"] is None
    assert store.get_size(conn, "u2") == 8.0 and s.profile_size == 8.0


def test_checkout_blocks_if_sold_out_meanwhile(conn):
    s, pid = Session(), in_stock(conn)
    cart.add_item(s, conn, pid, 9.0)
    conn.execute("UPDATE stock SET qty=0 WHERE shoe_id=? AND size=9", (pid,))
    assert cart.checkout(s, conn)["error"] == "out_of_stock"
    assert len(s.cart) == 1


def test_empty_checkout(conn):
    assert cart.checkout(Session(), conn) == {"error": "empty"}
