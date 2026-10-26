"""Python decides what happens next; the LLM only understands and words things.

Money actions (cart, checkout, order confirmation) use fixed templates built from database values,
never free-form LLM text. Opinions and chit-chat go through the grounding validator."""
import sqlite3

from app import config
from app.catalog.search import (
    all_colors,
    category_stats,
    get_shoe,
    get_shoes_by_ids,
    search_shoes,
)
from app.engine import cart, profile_flow, sales
from app.engine.common import (
    EMPTY,
    FALLBACKS,
    _facts,
    _n,
    _resp,
    _say,
    _sz,
    _target,
    noun,
    plural_of,
    size_for,
    size_label,
)
from app.engine.resolve import resolve_by_price, resolve_mentions
from app.engine.signals import (
    detect_category,
    detect_item_type,
    detect_occasion,
    detect_semantic_query,
    explicit_budget,
    explicit_decline,
    is_broad_category,
    is_fit_question,
    is_just_looking,
    is_quality_question,
    is_take,
)
from app.engine.state import Session
from app.llm.client import LLM
from app.llm.fastpath import fastpath
from app.llm.schemas import Extraction
from app.policy.rules import Action, Situation, decide
from app.profile.ranking import explain, rerank
from app.schemas import ChatResponse, UIAction
from app.validators import strip_ungrounded, validate


def _known(session: Session) -> dict:
    return {
        "slots": session.slots.model_dump(exclude_none=True),
        "shortlist_size": len(session.shortlist),
        "has_focused_product": session.focused_id is not None,
        "awaiting_order_confirmation": session.awaiting_confirm,
        "items_in_cart": len(session.cart),
        "awaiting_photo_consent": session.complexion == "awaiting_consent",
        "pending_complexion_estimate": session.pending_complexion is not None,
    }


def _merge(session: Session, ex: Extraction) -> None:
    s = session.slots
    if ex.use is not None and ex.use != s.use:
        session.shown, session.avoid_colors = [], []
    if ex.color is not None:
        session.avoid_colors = []
    if ex.category and s.category and ex.category != s.category:
        s.size = None  # a shoe size says nothing about a shirt
        session.shown, session.avoid_colors = [], []
    for name in ("use", "for_whom", "size", "budget", "color", "query"):
        value = getattr(ex, name)
        if value is not None:
            setattr(s, name, value)
    s.category = ex.category or s.category or "shoes"
    if ex.size is not None and s.for_whom is None:  # a size with no stated recipient means "for me"
        s.for_whom = "self"


def _apply_profile_size(session: Session) -> None:
    s = session.slots
    if s.size is None and s.for_whom != "other" and session.profile_size is not None and (s.category or "shoes") == "shoes":
        s.size, s.for_whom = session.profile_size, "self"


def _next_missing(session: Session) -> str | None:
    s = session.slots
    if s.use is None:
        return "ask_use"
    if s.category == "accessories":
        return None  # accessories are one size
    if s.size is None:
        return "ask_for_whom" if s.for_whom is None else "ask_size"
    return None


# ---------- present results ----------
def _present(session: Session, llm: LLM, conn, kind: str = "show", exclude_shown: bool = False,
             snapshot: tuple | None = None) -> ChatResponse:
    s = session.slots
    filters = {"use": s.use, "size": s.size, "max_price": s.budget, "color": s.color, "query": s.query}
    exclude = list(session.rejected) + (list(session.shown) if exclude_shown else [])
    boost = session.profile.has_signals()
    rows = search_shoes(conn, exclude_ids=exclude, exclude_colors=session.avoid_colors,
                        limit=30 if boost else 6, category=s.category or "shoes", **filters)
    if boost:
        rows = rerank(rows, session.profile, 6)
    if not rows:
        if snapshot is not None:  # refinement found nothing: undo it and keep what's on screen
            s.budget, session.avoid_colors = snapshot
            return _resp(session, EMPTY[kind].format(noun=noun(session)))
        session.shortlist = []
        return _resp(session, _say(llm, conn, session, "no_results", {"filters": filters}))
    ids = [r["id"] for r in rows]
    session.shortlist = ids
    session.top_pick_id = ids[0]
    session.shown = (session.shown + ids) if exclude_shown else list(ids)
    ui = {"type": "show_products", "product_ids": ids,
          "filters": {**{k: v for k, v in filters.items() if v}, **({"category": s.category} if s.category not in (None, "shoes") else {})}}
    if session.on_ui:  # the grid can appear while the sentence is still being worded
        session.on_ui(UIAction(**ui).model_dump(), s.model_dump())
    return _resp(session, _present_text(llm, conn, session, kind, rows), **ui)


def _present_text(llm: LLM, conn, session: Session, kind: str, rows: list[dict]) -> str:
    top = [{k: r[k] for k in ("name", "color", "price", "rating", "use_type")} for r in rows[:3]]
    text = _say(llm, conn, session, kind, {"count": len(rows), "top_picks": top}, rows)
    note = explain(rows, session.profile) if session.profile.has_signals() else ""
    return f"{text} {note}".strip()


def _refine(session: Session, ex: Extraction, llm: LLM, conn) -> ChatResponse | None:
    s = session.slots
    if not session.shortlist or s.use is None or s.size is None:
        return None
    if ex.budget is not None:
        return None  # the shopper gave an exact budget: apply it as stated, don't shrink it further
    snapshot = (s.budget, list(session.avoid_colors))
    shown = get_shoes_by_ids(conn, session.shortlist)
    if ex.refine == "cheaper":
        focused = next((p["price"] for p in shown if p["id"] == session.focused_id), None)
        known = [x for x in (s.budget, focused) if x]
        base = min(known) if known else max(p["price"] for p in shown)
        s.budget = int(base * 0.8)
        response = _present(session, llm, conn, "cheaper", snapshot=snapshot)
        if response.ui_action.type == "show_products":
            response.reply += f" Everything shown is ₹{_n(s.budget)} or less."  # a checkable claim, not just "cheaper"
        return response
    if ex.refine == "other_colors":
        session.avoid_colors = sorted(set(session.avoid_colors) | {p["color"] for p in shown})
        s.color = None
        return _present(session, llm, conn, "other_colors", snapshot=snapshot)
    if ex.refine == "show_more":
        return _present(session, llm, conn, "show_more", exclude_shown=True, snapshot=snapshot)
    return None


# ---------- opinion (data-only, validated) ----------
def _opinion_context(conn, session: Session, shoe: dict) -> tuple[dict, dict]:
    st = category_stats(conn, shoe["use_type"], shoe.get("category") or "shoes")
    s, ctx = session.slots, {}
    if st["count"]:
        ctx["price_vs_average_for_this_use_pct"] = round((shoe["price"] / st["avg_price"] - 1) * 100)
        ctx["rating_vs_average_for_this_use"] = round(shoe["rating"] - st["avg_rating"], 1)
        ctx["average_rating_for_this_use"] = round(st["avg_rating"], 1)
    size = size_for(shoe, s)
    if size is not None and shoe.get("category") != "accessories":
        ctx["shopper_size"] = size_label(shoe.get("category"), size)
        ctx["shopper_size_in_stock"] = size in shoe["sizes_in_stock"]
    if s.budget:
        ctx["shopper_budget"] = s.budget
    return ctx, st


def _opinion_fallback(shoe: dict, ctx: dict) -> str:
    parts = [f"The {shoe['name']} is {shoe['color']} and made for {shoe['use_type']} use, at ₹{_n(shoe['price'])}, rated {shoe['rating']}."]
    pct = ctx.get("price_vs_average_for_this_use_pct")
    if pct:
        parts.append(f"That's {abs(pct)}% {'above' if pct > 0 else 'below'} the average price for {shoe['use_type']} {plural_of(shoe)}.")
    if "shopper_size_in_stock" in ctx:
        parts.append("Your size is in stock." if ctx["shopper_size_in_stock"] else "Your size isn't in stock right now.")
    parts.append(shoe["description"])
    return " ".join(parts)


def _opinion(session: Session, message: str, ex: Extraction, llm: LLM, conn) -> ChatResponse:
    pid = _target(session, ex)
    shoe = get_shoe(conn, pid) if pid else None
    if not shoe:
        return _resp(session, _say(llm, conn, session, "ask_which"))
    ctx, st = _opinion_context(conn, session, shoe)
    data = {k: shoe[k] for k in ("name", "brand", "price", "use_type", "color", "rating", "description", "sizes_in_stock")}
    data["context"] = ctx
    facts = _facts(conn, session, [shoe], check_sizes=True, extra_amounts={round(st["avg_price"])},
                   extra_ratings={round(st["avg_rating"], 1)})
    text, problems = "", []
    for attempt in range(2):
        try:
            text = llm.opinion(data, message, avoid=problems or None)
        except Exception:
            text = ""
            break
        problems = validate(text, facts)
        if not problems:
            break
    if problems:
        text = strip_ungrounded(text, facts)
    if len(text.strip()) < 25:
        text = _opinion_fallback(shoe, ctx)
    return _resp(session, text, type="focus_product", product_id=shoe["id"])


# ---------- cart / checkout (templated) ----------
def _cart_add(session: Session, ex: Extraction, llm: LLM, conn, buy: bool) -> ChatResponse:
    _merge(session, ex)
    _apply_profile_size(session)
    pid = _target(session, ex)
    if pid is None:
        return _resp(session, _say(llm, conn, session, "ask_which"))
    return _cart_add_core(session, pid, buy, llm, conn)


def _cart_add_core(session: Session, pid: int, buy: bool, llm: LLM, conn) -> ChatResponse:
    s = session.slots
    shoe = get_shoe(conn, pid)
    if not shoe:
        return _resp(session, "I can't find that item any more. Want to look at the options again?")
    category = shoe.get("category") or "shoes"
    size = size_for(shoe, s)
    if size is None:
        if (s.category or "shoes") != category:
            s.category, s.size = category, None  # switching to what they picked: ask in that category's sizes
        session.pending = (pid, buy)
        return _resp(session, _say(llm, conn, session, "ask_for_whom" if s.for_whom is None else "ask_size"))
    in_size = "" if category == "accessories" else f" in size {size_label(category, size)}"
    status = cart.add_item(session, conn, pid, size, s.for_whom or "self")
    if status != "ok":
        sizes = shoe["sizes_in_stock"]
        if sizes and category != "accessories":
            text = (f"Sorry, the {shoe['name']} isn't available{in_size} right now. It is in stock in "
                    f"sizes {', '.join(size_label(category, x) for x in sizes)}. Want one of those, or shall I show other options?")
        else:
            text = f"Sorry, the {shoe['name']} is out of stock right now. Want me to show similar options?"
        return _resp(session, text)
    text = f"Added the {shoe['name']}{in_size} to your cart (₹{_n(shoe['price'])})."
    if buy:
        session.awaiting_confirm = True
        text += " Say “place order” or tap Place order in the cart to confirm. It's a mock checkout, so nothing is charged."
        return _resp(session, text, type="checkout")
    text += " Say “place order” when you're ready to check out."
    return _resp(session, text, type="add_to_cart", product_id=pid)


def _cart_remove(session: Session, ex: Extraction, conn) -> ChatResponse:
    pid = _target(session, ex)
    if pid is not None and cart.remove_item(session, pid):
        return _resp(session, "Removed it from your cart.")
    return _resp(session, "I couldn't find that in your cart.")


def _place_order(session: Session, conn) -> ChatResponse:
    own_ids = [i.shoe_id for i in session.cart if i.for_whom == "self"]
    result = cart.checkout(session, conn)
    if result.get("error") == "empty":
        session.awaiting_confirm = False
        return _resp(session, "Your cart is empty, so there's nothing to order yet.")
    if result.get("error"):
        session.awaiting_confirm = False
        return _resp(session, f"Sorry, {', '.join(result['items'])} just went out of stock in that size, so I didn't place the order. Want to pick another size?")
    n = len(result["items"])
    text = (f"Done! Order {result['order_id']} is confirmed: {n} item{'s' if n != 1 else ''}, total ₹{_n(result['total'])}. "
            "This was a mock checkout, so nothing was charged.")
    if result["saved_size"] is not None:
        text += f" I've saved shoe size {_sz(result['saved_size'])} for next time."
    bought = [get_shoe(conn, i) for i in own_ids]
    guessed = []
    for shoe in filter(None, bought):
        before = session.profile.values("liked_color")
        session.profile.set_color(shoe["color"], True, "inferred")
        if len(session.profile.values("liked_color")) > len(before) and shoe["color"] not in guessed:
            guessed.append(shoe["color"])
    if guessed:
        profile_flow.save(session, conn)
        text += f" I'll tentatively note that you like {', '.join(guessed)}; correct me any time."
    return _resp(session, text, type="checkout", order_id=result["order_id"])


# ---------- entry point ----------
FLOW_INTENTS = {"shopping", "greeting", "other", "confirm", "refine"}
ENGAGING = {"shopping", "opinion", "focus", "compare", "object", "browse", "refine",
            "cart_add", "buy", "cart_remove", "reject", "complexion"}
SLOT_FIELDS = ("use", "for_whom", "size", "budget", "color", "query")


def _continue_flow(session: Session, llm: LLM, conn) -> ChatResponse:
    missing = _next_missing(session)
    if missing:
        return _resp(session, _say(llm, conn, session, missing))
    return _present(session, llm, conn)


def _run(action: Action, session: Session, ex: Extraction, message: str, llm: LLM, conn) -> ChatResponse:
    if action == Action.RESPECT_NO:
        if ex.intent == "decline":
            session.declined, session.awaiting_confirm, session.pending = True, False, None
            session.complexion, session.consent, session.pending_complexion = None, False, None
            return _resp(session, _say(llm, conn, session, "decline"))
        return _resp(session, _say(llm, conn, session, "quiet"))
    if action == Action.FORGET_PROFILE:
        return profile_flow.forget(session, conn)
    if action == Action.SHOW_PROFILE:
        return profile_flow.show(session)
    if action == Action.UPDATE_PROFILE:
        return profile_flow.update(session, ex, conn)
    if action == Action.GRANT_CONSENT:
        return profile_flow.grant_consent(session)
    if action == Action.CONFIRM_COMPLEXION:
        est = session.pending_complexion
        return _resp(session, profile_flow.apply_confirmed(session, conn, est["skin_tone"], est["undertone"]))
    if action == Action.COMPLEXION_START:
        undertone = session.profile.value("undertone")
        if not undertone:
            return profile_flow.ask_consent(session)
        if session.slots.use and session.slots.size is not None:
            return _present(session, llm, conn)  # re-ranked, with the reason in the reply
        return _resp(session, profile_flow.known_note(undertone))
    if action == Action.QUIET:
        return _resp(session, _say(llm, conn, session, "quiet" if session.declined else "just_looking"))
    if action == Action.ANSWER:
        return _resp(session, llm.answer_offtopic(message))
    if action == Action.CONFIRM_ORDER:
        return _place_order(session, conn)
    if action == Action.REJECT_ITEM:
        return sales.reject_item(session, ex, conn)
    if action == Action.OPINION:
        return _opinion(session, message, ex, llm, conn)
    if action == Action.FOCUS:
        pid = _target(session, ex)
        shoe = get_shoe(conn, pid) if pid else None
        if not shoe:
            return _resp(session, _say(llm, conn, session, "ask_which"))
        return _resp(session, f"Here's the {shoe['name']}. Ask me anything about it, or say “buy this”.",
                     type="focus_product", product_id=shoe["id"])
    if action == Action.COMPARE:
        return sales.compare(session, ex, message, llm, conn)
    if action == Action.OBJECTION:
        if ex.objection in (None, "price") and session.focused_id is None and ex.product_index is None \
                and session.shortlist:
            # A general "too expensive" about what's on screen: lower the price range.
            refined = _refine(session, Extraction(intent="refine", refine="cheaper"), llm, conn)
            if refined:
                return refined
        return sales.objection(session, ex, message, llm, conn)
    if action == Action.DISCOVER:
        return sales.discover(session, llm, conn)
    if action == Action.CART_ADD:
        return _cart_add(session, ex, llm, conn, buy=ex.intent == "buy")
    if action == Action.CART_REMOVE:
        return _cart_remove(session, ex, conn)
    if action == Action.RESUME_CART:
        pid, buy = session.pending
        session.pending = None
        return _cart_add_core(session, pid, buy, llm, conn)
    if action == Action.REFINE:
        return _refine(session, ex, llm, conn) or _continue_flow(session, llm, conn)
    if action == Action.GREET:
        return _resp(session, _say(llm, conn, session, "greet"))
    if action == Action.DISCUSS_OCCASION:
        return _resp(session, _say(llm, conn, session, "discuss_occasion"))
    if action == Action.NARROW_CATEGORY:
        cat = session.slots.category or ex.category or "apparel"
        kind = f"narrow_{cat}" if f"narrow_{cat}" in FALLBACKS else "narrow_apparel"
        return _resp(session, _say(llm, conn, session, kind))
    if action == Action.CLARIFY:
        return _resp(session, _say(llm, conn, session, _next_missing(session)))
    return _present(session, llm, conn)  # RETRIEVE


NAMEABLE = {"opinion", "focus", "object", "reject", "cart_add", "buy", "cart_remove"}


def _resolve_names(session: Session, ex: Extraction, message: str, conn) -> None:
    """Turn "the grey Hush Puppies Derby" or "that ₹1,999 one" into a screen position when the LLM gave none.
    A price complaint about a named shoe is a price objection about THAT shoe, however the LLM labelled it."""
    if not session.shortlist:
        return
    shoes = get_shoes_by_ids(conn, session.shortlist)
    found = (resolve_mentions(message, shoes, all_colors(conn), prefer_id=session.top_pick_id)
             or resolve_by_price(message, shoes))
    positions = [session.shortlist.index(s["id"]) + 1 for s in found]
    if ex.intent == "compare" and not ex.compare_indices and len(positions) >= 2:
        ex.compare_indices = positions[:3]
    elif len(positions) == 1 and ex.intent == "refine" and ex.refine == "cheaper":
        ex.intent, ex.objection, ex.refine = "object", "price", None
        ex.product_index = ex.product_index or positions[0]
    elif len(positions) == 1 and ex.product_index is None and ex.intent in NAMEABLE:
        ex.product_index = positions[0]


def _label_signals(ex: Extraction, message: str) -> None:
    if ex.category is None:
        ex.category = detect_category(message)
    if ex.query is None and ex.intent in ("shopping", "browse", "refine"):
        ex.query = detect_semantic_query(message)
    if ex.occasion is None:
        ex.occasion = detect_occasion(message)
    if ex.item_type is None:
        ex.item_type = detect_item_type(message)
    """Before names are resolved: an exact budget, and plain fit/durability questions a lighter model may mislabel."""
    if ex.intent != "decline" and explicit_decline(message):
        ex.intent = "decline"  # "no thanks, just browsing" must never be read as browsing
        return
    if ex.intent in ("browse", "other", "shopping") and is_just_looking(message):
        ex.intent = "just_looking"  # "just browsing, thanks" is a brush-off, not a request to be shown things
        return
    if ex.budget is None and ex.intent not in ("decline", "off_topic"):
        ex.budget = explicit_budget(message)
    if ex.intent in ("shopping", "other", "opinion", "focus") and ex.objection is None:
        if is_fit_question(message):
            ex.intent, ex.objection = "object", "fit"
        elif is_quality_question(message):
            ex.intent, ex.objection = "object", "quality"


def _route_signals(session: Session, ex: Extraction, message: str) -> None:
    """After names are resolved: an exact budget is just a new search; "I'll take it" is a purchase."""
    if ex.budget is not None and ex.intent in ("object", "refine") and ex.objection in (None, "price") \
            and ex.product_index is None:
        ex.intent, ex.objection, ex.refine = "shopping", None, None
    if (session.shortlist and ex.intent in ("cart_add", "shopping", "other") and is_take(message)
            and (ex.product_index is not None or session.focused_id is not None)):
        ex.intent = "buy"


def _handle(session: Session, message: str, llm: LLM, conn: sqlite3.Connection,
            focus_id: int | None = None) -> ChatResponse:
    if focus_id is not None:
        session.focused_id = focus_id
    known = _known(session)
    quick = fastpath(message, known) if config.FASTPATH else None
    try:
        ex = quick or llm.extract(message, known)
    except Exception:  # a malformed or empty model response must not crash the conversation
        return ChatResponse(reply="Sorry, I didn't quite catch that. Could you say it again?", slots=session.slots,
                            policy={"action": "error", "rule": "llm_error", "fast": False})
    _label_signals(ex, message)
    _resolve_names(session, ex, message, conn)
    _route_signals(session, ex, message)
    engaged = (ex.intent in ENGAGING or any(getattr(ex, f) is not None for f in SLOT_FIELDS)
               or (ex.intent == "confirm" and session.awaiting_confirm))
    if ex.intent in FLOW_INTENTS:
        _merge(session, ex)
        _apply_profile_size(session)
    has_occasion = bool(
        (ex.occasion or detect_occasion(message))
        and not ex.item_type
        and not detect_item_type(message)
        and session.slots.size is None
        and not session.shortlist
        and not session.focused_id
    )
    has_full_slots = bool(
        (session.slots.use or ex.use)
        and (session.slots.size is not None or ex.size is not None or session.slots.category == "accessories")
    )
    needs_narrowing = bool(
        not has_occasion
        and not session.shortlist
        and not session.focused_id
        and not has_full_slots
        and is_broad_category(message)
    )
    situation = Situation(
        intent=ex.intent, refine=ex.refine, objection=ex.objection, declined=session.declined,
        engaged=engaged, awaiting_confirm=session.awaiting_confirm, has_shortlist=bool(session.shortlist),
        has_focus=session.focused_id is not None,
        awaiting_consent=session.complexion == "awaiting_consent",
        pending_complexion=session.pending_complexion is not None,
        slots_empty=not session.slots.model_dump(exclude_none=True, exclude={"category"}),
        missing_slot=_next_missing(session),
        pending_ready=bool(session.pending and session.slots.size is not None),
        has_occasion=has_occasion,
        needs_narrowing=needs_narrowing,
    )
    action, rule = decide(situation)
    response = _run(action, session, ex, message, llm, conn)
    if engaged and ex.intent != "decline":
        session.declined = False  # the user re-engaged on their own terms
    if action not in (Action.CONFIRM_ORDER, Action.CART_ADD, Action.RESUME_CART):
        session.awaiting_confirm = False  # a later, unrelated "yes" must not place an order that was offered earlier
    response.policy = {"action": action.value, "rule": rule, "fast": quick is not None}
    session.last_reply = response.reply
    return response


def handle(session: Session, message: str, llm: LLM, conn: sqlite3.Connection,
           focus_id: int | None = None, on_ui=None) -> ChatResponse:
    """One conversation turn. `on_ui(ui_action, slots)` is called as soon as the products to show are known, before the
    reply sentence has been worded, so a streaming caller can update the panel first."""
    session.on_ui = on_ui
    try:
        return _handle(session, message, llm, conn, focus_id)
    finally:
        session.on_ui = None
