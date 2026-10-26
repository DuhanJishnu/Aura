import sqlite3


def search_shoes(
    conn: sqlite3.Connection,
    use: str | None = None,
    size: float | None = None,
    max_price: int | None = None,
    color: str | None = None,
    exclude_ids: list[int] | None = None,
    exclude_colors: list[str] | None = None,
    category: str | None = "shoes",
    query: str | None = None,
    limit: int = 6,
) -> list[dict]:
    """Filter by SQL; rank by semantic relevance if query provided, else rating & budget closeness."""
    where, params = ["1=1"], []
    if category:
        where.append("s.category = ?")
        params.append(category)
    if use:
        where.append("s.use_type = ?")
        params.append(use)
    if max_price:
        where.append("s.price <= ?")
        params.append(max_price)
    if color:
        where.append("LOWER(s.color) = LOWER(?)")
        params.append(color)
    if size is not None:
        where.append(
            "EXISTS (SELECT 1 FROM stock k WHERE k.shoe_id = s.id AND k.size = ? AND k.qty > 0)"
        )
        params.append(size)
    if exclude_ids:
        where.append(f"s.id NOT IN ({','.join('?' * len(exclude_ids))})")
        params.extend(exclude_ids)

    if exclude_colors:
        where.append(f"LOWER(s.color) NOT IN ({','.join('?' * len(exclude_colors))})")
        params.extend(c.lower() for c in exclude_colors)

    order = "s.rating DESC, s.price ASC"
    if max_price:
        order = "s.rating DESC, (? - s.price) ASC"
        params.append(max_price)

    fetch_limit = max(limit * 6, 36) if query else limit
    sql = f"SELECT s.* FROM shoes s WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ?"
    params.append(fetch_limit)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    if query:
        from app.catalog.semantic import semantic_rank
        return semantic_rank(conn, rows, query, top_k=limit)

    return rows[:limit]


def get_shoe(conn: sqlite3.Connection, shoe_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM shoes WHERE id = ?", (shoe_id,)).fetchone()
    if not row:
        return None
    shoe = dict(row)
    shoe["sizes_in_stock"] = [
        r["size"]
        for r in conn.execute(
            "SELECT size FROM stock WHERE shoe_id = ? AND qty > 0 ORDER BY size", (shoe_id,)
        )
    ]
    return shoe


def get_shoes_by_ids(conn: sqlite3.Connection, ids: list[int]) -> list[dict]:
    """Shoes in the given order (unknown ids skipped), each with sizes_in_stock."""
    return [s for s in (get_shoe(conn, i) for i in ids) if s]


def category_stats(conn: sqlite3.Connection, use: str, category: str = "shoes") -> dict:
    row = conn.execute(
        "SELECT AVG(price) AS avg_price, AVG(rating) AS avg_rating, COUNT(*) AS n "
        "FROM shoes WHERE use_type = ? AND category = ?", (use, category)
    ).fetchone()
    return {"avg_price": row["avg_price"] or 0, "avg_rating": row["avg_rating"] or 0, "count": row["n"]}


def all_brands(conn: sqlite3.Connection) -> set[str]:
    return {r["brand"] for r in conn.execute("SELECT DISTINCT brand FROM shoes")}


def all_colors(conn: sqlite3.Connection) -> set[str]:
    return {r["color"] for r in conn.execute("SELECT DISTINCT color FROM shoes")}
