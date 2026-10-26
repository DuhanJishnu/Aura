"""Salesperson behaviours: objections, comparing, browsing, rejecting.

Facts always come from the database. LLM wording goes through the grounding validator; anything
the data cannot support (fit, durability) is answered honestly with "I don't have that"."""
from app.catalog.search import category_stats, get_shoe, get_shoes_by_ids, search_shoes
from app.engine.common import (
    FALLBACKS,
    _facts,
    _n,
    _resp,
    _say,
    _target,
    grounded,
    plural_of,
    size_label,
)
from app.engine.state import Session
from app.llm.client import LLM
from app.llm.schemas import Extraction

SHOE_FIELDS = ("name", "brand", "price", "use_type", "color", "rating", "description", "sizes_in_stock")


def _data(shoe: dict) -> dict:
    return {k: shoe[k] for k in SHOE_FIELDS if k in shoe}


# ---------- reject a specific shoe ----------
def reject_item(session: Session, ex: Extraction, conn):
    pid = _target(session, ex)
    if pid is None:
        return _resp(session, "No problem. Just tell me what you'd rather see.")
    if pid not in session.rejected:
        session.rejected.append(pid)
    session.shortlist = [i for i in session.shortlist if i != pid]
    session.focused_id = None
    if session.shortlist:
        return _resp(session, "Got it, I'll leave that one out.", type="show_products", product_ids=list(session.shortlist))
    return _resp(session, "Got it, I'll leave that one out.")


# ---------- browsing ----------
def discover(session: Session, llm: LLM, conn):
    rows = []
    favoured = {"sporty": "sports", "classic": "office", "casual": "casual"}.get(session.profile.value("style"))
    for use in ("sports", "office", "casual"):
        rows += search_shoes(conn, use=use, exclude_ids=session.rejected, limit=3 if use == favoured else 2,
                             category=session.slots.category or "shoes")
    ids = [r["id"] for r in rows]
    session.shortlist, session.shown, session.focused_id = ids, list(ids), None
    text = _say(llm, conn, session, "discover", {"count": len(ids)}, rows)
    return _resp(session, text, type="show_products", product_ids=ids)


# ---------- comparing ----------
def compare_points(shoes: list[dict], size: float | None = None) -> list[str]:
    pts = []
    by_price = sorted(shoes, key=lambda x: x["price"])
    cheap = by_price[0]
    cat = shoes[0].get("category") or "shoes"
    for o in by_price[1:]:
        if o["price"] == cheap["price"]:
            pts.append(f"The {cheap['name']} and the {o['name']} cost the same, ₹{_n(cheap['price'])}.")
        else:
            more = round((o["price"] / cheap["price"] - 1) * 100)
            pts.append(f"The {cheap['name']} is cheaper at ₹{_n(cheap['price'])}; the {o['name']} costs "
                       f"₹{_n(o['price'])}, {more}% more.")
    best = max(shoes, key=lambda x: x["rating"])
    if len({x["rating"] for x in shoes}) == 1:
        pts.append(f"They are rated the same, {best['rating']}.")
    else:
        rest = ", ".join(f"the {x['name']} {x['rating']}" for x in shoes if x is not best)
        pts.append(f"The {best['name']} is rated highest at {best['rating']}; {rest}.")
    if size is not None:
        have = [x for x in shoes if size in x["sizes_in_stock"]]
        if len(have) == len(shoes):
            pts.append(f"All of them are in stock in size {size_label(cat, size)}.")
        elif not have:
            pts.append(f"None of them are in stock in size {size_label(cat, size)}.")
        else:
            pts.append(f"In size {size_label(cat, size)}, only the {' and the '.join(x['name'] for x in have)} "
                       "is in stock." if len(have) == 1 else
                       f"In size {size_label(cat, size)}, only the {' and the '.join(x['name'] for x in have)} are in stock.")
    if len({x["use_type"] for x in shoes}) > 1:
        pts.append("They are for different uses: " + "; ".join(f"the {x['name']} is for {x['use_type']} use" for x in shoes) + ".")
    if len({x["color"] for x in shoes}) > 1:
        pts.append("Colors: " + ", ".join(f"the {x['name']} is {x['color']}" for x in shoes) + ".")
    if cheap is best and len({x["rating"] for x in shoes}) > 1 and len({x["price"] for x in shoes}) > 1:
        pts.append(f"The {cheap['name']} is both cheaper and rated higher, so on these numbers it is the better value.")
    elif cheap is not best and cheap["price"] != best["price"]:
        pts.append(f"Neither wins outright: the {cheap['name']} costs less and the {best['name']} is rated higher, "
                   "so it comes down to which matters more to you.")
    return pts


def compare(session: Session, ex: Extraction, message: str, llm: LLM, conn):
    positions = [i for i in dict.fromkeys(ex.compare_indices) if 1 <= i <= len(session.shortlist)][:3]
    ids = [session.shortlist[i - 1] for i in positions]
    note = ""
    if len(ids) < 2:
        if len(session.shortlist) < 2:
            return _resp(session, FALLBACKS["ask_compare"])
        ids, note = session.shortlist[:2], "You didn't say which, so I compared the top two. "
    shoes = get_shoes_by_ids(conn, ids)
    points = compare_points(shoes, session.slots.size)
    data = {"shoes": [_data(s) for s in shoes], "tradeoffs": points}
    facts = _facts(conn, session, shoes, check_sizes=True)
    text = grounded(lambda avoid: llm.compare(data, avoid), facts, " ".join(points))
    return _resp(session, note + text, type="compare", product_ids=ids)


# ---------- objections ----------
def objection(session: Session, ex: Extraction, message: str, llm: LLM, conn):
    pid = _target(session, ex)
    shoe = get_shoe(conn, pid) if pid else None
    if not shoe:
        return _resp(session, _say(llm, conn, session, "ask_which"))
    kind = ex.objection or "price"
    if kind == "fit":
        return _fit(session, shoe)
    return _price_or_quality(session, kind, shoe, message, llm, conn, ceiling=ex.budget)


def _fit(session: Session, shoe: dict):
    cat = shoe.get("category") or "shoes"
    size, sizes = (session.slots.size if (session.slots.category or "shoes") == cat else None), shoe["sizes_in_stock"]
    parts = [f"I don't have fit or reviewer data for the {shoe['name']}, so I can't say whether it runs small or large."]
    if sizes:
        parts.append(f"It is in stock in sizes {', '.join(size_label(cat, x) for x in sizes)}.")
        if size is not None and size in sizes:
            near = [x for x in sizes if x != size and abs(x - size) <= 1]
            if near:
                parts.append(f"Your size, {size_label(cat, size)}, is available, and so is {' and '.join(size_label(cat, x) for x in near)} if you want to try a neighbouring size.")
    else:
        parts.append("It is out of stock in every size right now.")
    parts.append("The brand's size chart, or something you already own to compare against, will tell you more than I can.")
    return _resp(session, " ".join(parts), type="focus_product", product_id=shoe["id"])


def _price_or_quality(session, kind, shoe, message, llm, conn, ceiling=None):
    s = session.slots
    st = category_stats(conn, shoe["use_type"], shoe.get("category") or "shoes")
    alts = []
    if kind == "price":
        alts = search_shoes(conn, use=shoe["use_type"], size=s.size, max_price=min(shoe["price"] - 1, ceiling) if ceiling else shoe["price"] - 1,
                            exclude_ids=[shoe["id"], *session.rejected], category=shoe.get("category") or "shoes", limit=3)
    pct = round((shoe["price"] / st["avg_price"] - 1) * 100) if st["avg_price"] else 0
    diff = round(shoe["rating"] - st["avg_rating"], 1)
    data = _data(shoe) | {
        "context": {"price_vs_average_for_this_use_pct": pct, "average_rating_for_this_use": round(st["avg_rating"], 1),
                    "rating_vs_average_for_this_use": diff},
        "alternatives": [_data(a) | {"cheaper_by_pct": round((1 - a["price"] / shoe["price"]) * 100)} for a in alts],
    }
    facts = _facts(conn, session, [shoe, *alts], extra_amounts={round(st["avg_price"])},
                   extra_ratings={round(st["avg_rating"], 1)})
    fallback = _price_fallback(shoe, alts, pct, s.size) if kind == "price" else _quality_fallback(shoe, st, diff)
    text = grounded(lambda avoid: llm.objection(kind, data, message, avoid), facts, fallback)
    if alts:
        ids = [shoe["id"], *[a["id"] for a in alts]]
        session.shortlist, session.shown, session.focused_id = ids, list(ids), None
        return _resp(session, text, type="show_products", product_ids=ids)
    return _resp(session, text, type="focus_product", product_id=shoe["id"])


def _price_fallback(shoe, alts, pct, size) -> str:
    price, use = f"₹{_n(shoe['price'])}", shoe["use_type"]
    if pct > 0:
        text = f"Fair point. At {price} the {shoe['name']} is {pct}% above the average price for {use} {plural_of(shoe)}."
    elif pct < 0:
        text = f"I hear you, though at {price} the {shoe['name']} is actually {abs(pct)}% below the average price for {use} {plural_of(shoe)}."
    else:
        text = f"I hear you. At {price} the {shoe['name']} is right around the average price for {use} {plural_of(shoe)}."
    if alts:
        a = alts[0]
        text += f" If you'd rather spend less, the {a['name']} is ₹{_n(a['price'])} and rated {a['rating']}. I've put a few cheaper options on screen."
    else:
        text += f" It is also among the cheapest {use} options I have{' in your size' if size is not None else ''}, so I have nothing cheaper to suggest."
    return text


def _quality_fallback(shoe, st, diff) -> str:
    if diff > 0:
        rel = f"{diff} above"
    elif diff < 0:
        rel = f"{abs(diff)} below"
    else:
        rel = "in line with"
    return (f"Reasonable question. All I have on the {shoe['name']} is this description: {shoe['description']} "
            f"It is rated {shoe['rating']}, {rel} the {shoe['use_type']} average of {round(st['avg_rating'], 1)}. "
            "I don't have durability or material details, so I can't promise how long it will last.")
