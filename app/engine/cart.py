import sqlite3
import uuid
from datetime import UTC, datetime

from app.catalog.search import get_shoe
from app.engine.state import CartItem, Session
from app.profile.store import save_size


def add_item(session: Session, conn: sqlite3.Connection, shoe_id: int, size: float, for_whom: str = "self") -> str:
    shoe = get_shoe(conn, shoe_id)
    if not shoe:
        return "unknown"
    if size not in shoe["sizes_in_stock"]:
        return "out_of_stock"
    if not any(i.shoe_id == shoe_id and i.size == size for i in session.cart):
        session.cart.append(CartItem(shoe_id, size, for_whom, shoe.get("category") or "shoes"))
    return "ok"


def remove_item(session: Session, shoe_id: int, size: float | None = None) -> bool:
    before = len(session.cart)
    session.cart = [i for i in session.cart if not (i.shoe_id == shoe_id and (size is None or i.size == size))]
    return len(session.cart) < before


def view(session: Session, conn: sqlite3.Connection) -> dict:
    items = []
    for i in session.cart:
        shoe = get_shoe(conn, i.shoe_id)
        if shoe:
            items.append({"shoe_id": i.shoe_id, "name": shoe["name"], "price": shoe["price"], "size": i.size,
                          "category": shoe.get("category") or "shoes"})
    return {"items": items, "total": sum(i["price"] for i in items)}


def checkout(session: Session, conn: sqlite3.Connection) -> dict:
    """Mock checkout: re-checks stock, decrements it, records the order, saves own size."""
    if not session.cart:
        return {"error": "empty"}
    snapshot = view(session, conn)
    sold_out = []
    for it, line in zip(session.cart, snapshot["items"], strict=False):
        row = conn.execute("SELECT qty FROM stock WHERE shoe_id=? AND size=?", (it.shoe_id, it.size)).fetchone()
        if not row or row["qty"] < 1:
            sold_out.append(line["name"])
    if sold_out:
        return {"error": "out_of_stock", "items": sold_out}

    order_id = "ORD-" + uuid.uuid4().hex[:8].upper()
    conn.execute(
        "INSERT INTO orders (id, user_id, total, created_at) VALUES (?,?,?,?)",
        (order_id, session.user_id or None, snapshot["total"], datetime.now(UTC).isoformat()),
    )
    for line in snapshot["items"]:
        conn.execute("INSERT INTO order_items VALUES (?,?,?,?,?)",
                     (order_id, line["shoe_id"], line["size"], line["price"], line["name"]))
        conn.execute("UPDATE stock SET qty = qty - 1 WHERE shoe_id=? AND size=?", (line["shoe_id"], line["size"]))

    saved_size = None
    own = [i for i in session.cart if i.for_whom == "self" and i.category == "shoes"]  # only a shoe size is a profile size
    if own:
        saved_size = own[-1].size
        session.profile_size = saved_size
        if session.user_id:
            save_size(conn, session.user_id, saved_size)
    conn.commit()
    session.cart = []
    session.awaiting_confirm = False
    return {"order_id": order_id, "items": snapshot["items"], "total": snapshot["total"], "saved_size": saved_size}


def get_order(conn: sqlite3.Connection, order_id: str) -> dict | None:
    o = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not o:
        return None
    items = [dict(r) for r in conn.execute(
        "SELECT oi.*, COALESCE(s.category, 'shoes') AS category FROM order_items oi LEFT JOIN shoes s ON s.id = oi.shoe_id "
        "WHERE oi.order_id=?", (order_id,))]
    return {"order_id": o["id"], "total": o["total"], "created_at": o["created_at"], "items": items}
