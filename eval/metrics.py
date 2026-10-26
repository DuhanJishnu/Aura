"""Per-conversation scores and aggregation. Deterministic checks use the catalog; judge flags (from an LLM)
are used when present and a deterministic fallback otherwise. Every number here is a proxy: simulated
shoppers and LLM judges are not real customers, which is why a human review step exists."""
import math
import re
from collections import Counter, defaultdict

from app.engine.common import APPAREL_SIZES
from app.validators import Facts, validate
from eval.types import Conversation

DECLINE = re.compile(r"\b(no thanks|no,? thank you|not interested|never mind|nevermind|stop (pitching|selling|asking|messaging))\b", re.I)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


class Ctx:
    def __init__(self, conn):
        self.conn = conn
        self.prices = {r["price"] for r in conn.execute("SELECT DISTINCT price FROM shoes")}

    def shoe_ok(self, pid, p, use_known, size_known, budget_known) -> bool | None:
        s = self.conn.execute("SELECT use_type, category, price FROM shoes WHERE id=?", (pid,)).fetchone()
        if not s:
            return False
        prod_cat = getattr(p, "product_category", "shoes")
        if s["category"] != prod_cat:
            return False
        if use_known and p.use and s["use_type"] != p.use:
            return False
        if budget_known and p.budget and s["price"] > p.budget:
            return False
        if size_known and p.size is not None and prod_cat != "accessories":
            row = self.conn.execute("SELECT qty FROM stock WHERE shoe_id=? AND size=?", (pid, p.size)).fetchone()
            if not row or row["qty"] < 1:
                return False
        return True


def _fmt(x) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def score(conv: Conversation, ctx: Ctx) -> dict:
    p, turns = conv.persona, conv.turns
    asst = [t for t in turns if t.role == "assistant"]
    users = [t for t in turns if t.role == "user"]
    v, j = conv.verdict or {}, conv.judge or {}
    real_order = any(t.order_id for t in asst)
    bought = (v.get("outcome") == "buy") or (conv.system == "agent" and real_order and not v)

    # relevance: only once the shopper has stated the constraint being checked
    seen, rel = "", []
    for t in turns:
        if t.role == "user":
            seen += " " + t.text.lower()
        elif t.shown_ids and t.action != "checkout":
            prod_cat = getattr(p, "product_category", "shoes")
            uk = bool(p.use and p.use in seen)
            if prod_cat == "apparel" and p.size is not None:
                letter = APPAREL_SIZES.get(int(p.size), "")
                sk = bool((letter and re.search(rf"\b{letter}\b", seen, re.I)) or re.search(rf"\b{_fmt(p.size)}\b", seen))
            elif prod_cat == "accessories":
                sk = False
            else:
                sk = p.size is not None and bool(re.search(rf"\b{_fmt(p.size)}\b", seen))
            bk = bool(p.budget and str(p.budget) in seen)
            if uk or sk or bk:
                oks = [ctx.shoe_ok(i, p, uk, sk, bk) for i in t.shown_ids]
                rel.append(sum(oks) / len(oks))

    # hallucination: any rupee amount that is not a real catalog price (or the shopper's own budget)
    allowed = ctx.prices | ({p.budget} if p.budget else set()) | {sum(o["price"] for o in conv.orders)}
    halluc = [bool([x for x in validate(t.text, Facts(extra_amounts=allowed | set(t.amounts))) if x.startswith("price ")]) for t in asst]

    # stop-selling: after the shopper says no, any product or shopping question is a violation
    pitched = None
    first_no = next((i for i, t in enumerate(turns) if t.role == "user" and DECLINE.search(t.text)), None)
    if first_no is not None:
        pitched = any(t.role == "assistant" and (t.shown_ids or "?" in t.text) for t in turns[first_no + 1:])
        if j.get("pitched_after_no"):
            pitched = True

    # off-topic: the reply to the unrelated question must not push products
    hijack = None
    if p.off_topic and asst:
        hijack = bool(asst[0].shown_ids)  # pushing products is a hijack; a friendly steer back is not

    # objections: judge if available, otherwise a deterministic check on the reply that followed
    resolved = None
    if p.objection:
        if j.get("objection_addressed") is not None:
            resolved = bool(j["objection_addressed"])
        else:
            idx = next((i for i, t in enumerate(turns) if t.role == "user" and re.search(r"too expensive|will it fit|runs small", t.text, re.I)), None)
            nxt = next((t for t in turns[idx + 1:] if t.role == "assistant"), None) if idx is not None else None
            if nxt is not None:
                resolved = bool(nxt.shown_ids) if p.objection == "price" else "fit" in nxt.text.lower() and "data" in nxt.text.lower()
            # idx is None: the shopper never raised the concern in this conversation, so there is nothing to score

    # honesty when nothing matches
    honest_empty = None
    if p.expected_empty:
        # honest = the system said there is nothing, showed nothing after saying so, and never claimed otherwise.
        # (Shoppers paraphrase their budget, e.g. 1399 -> "under ₹1,400", so we don't search for the exact number.)
        said = [i for i, x in enumerate(turns) if x.role == "assistant" and not x.shown_ids and re.search(
            r"couldn't find|nothing|no match|don't have|do not have|not in stock|out of stock|isn't available|unavailable", x.text, re.I)]
        honest_empty = bool(said) and not any(x.shown_ids for x in turns[said[-1] + 1:] if x.role == "assistant")

    # task success is category-specific
    answered = j.get("answered_off_topic") if j.get("answered_off_topic") is not None else (hijack is False)
    if p.category == "rejection":
        success = pitched is not True and v.get("outcome", "no_buy") != "buy"
    elif p.expected_empty:
        success = bool(honest_empty)
    elif p.category == "off_topic":
        success = bool(bought and answered and not hijack)
    else:
        success = bool(bought)

    order_valid = None
    if conv.orders:
        prod_cat = getattr(p, "product_category", "shoes")
        order_valid = all(
            (not prod_cat or o.get("category") in (None, prod_cat))
            and (not p.use or o["use_type"] == p.use)
            and (p.size is None or prod_cat == "accessories" or o["size"] == p.size)
            and (not p.budget or o["price"] <= p.budget) for o in conv.orders)

    return {
        "id": p.id, "system": conv.system, "category": p.category, "error": conv.error is not None,
        "success": success, "bought": bought, "real_order": real_order, "order_valid": order_valid,
        "purchase_intent": v.get("purchase_intent"), "natural": v.get("natural") or j.get("natural"),
        "felt_pressured": v.get("felt_pressured"), "turns_to_decision": len(users) if bought else None,
        "relevance": sum(rel) / len(rel) if rel else None,
        "halluc_turns": sum(halluc), "turns": len(asst), "hallucinated": any(halluc),
        "pitched_after_no": pitched, "hijacked": hijack, "objection_resolved": resolved, "honest_empty": honest_empty,
        "invented_facts": j.get("invented_facts"),
        "tokens_in": sum(t.tokens_in for t in asst), "tokens_out": sum(t.tokens_out for t in asst),
        "tokens_thought": sum(t.tokens_thought for t in asst),
        "latency": sum(t.latency for t in asst) / len(asst) if asst else None,
        "rules": [t.rule for t in asst if t.rule],
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _rate(xs):
    xs = [x for x in xs if x is not None]
    return (sum(bool(x) for x in xs), len(xs)) if xs else (0, 0)


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if not r["error"]]
    k, n = _rate(r["success"] for r in ok)
    out = {"n": len(rows), "errors": len(rows) - len(ok), "success": (k, n, *wilson(k, n))}
    out["strict_success"] = _rate(r["order_valid"] for r in ok if r["real_order"])  # of real orders, how many met the constraints
    out["purchase_intent"] = _mean(r["purchase_intent"] for r in ok)
    out["natural"] = _mean(r["natural"] for r in ok)
    out["pressured"] = _rate(r["felt_pressured"] for r in ok)
    out["turns_to_decision"] = _mean(r["turns_to_decision"] for r in ok)
    out["relevance"] = _mean(r["relevance"] for r in ok)
    out["hallucination"] = _rate(r["hallucinated"] for r in ok)
    out["objection_resolved"] = _rate(r["objection_resolved"] for r in ok)
    out["respected_no"] = (lambda kn: (kn[1] - kn[0], kn[1]))(_rate(r["pitched_after_no"] for r in ok))
    out["not_hijacked"] = (lambda kn: (kn[1] - kn[0], kn[1]))(_rate(r["hijacked"] for r in ok))
    out["honest_empty"] = _rate(r["honest_empty"] for r in ok)
    out["order_follow_through"] = _rate(r["real_order"] for r in ok if r["system"] == "agent" and r["bought"])
    out["tokens_in"] = _mean(r["tokens_in"] for r in ok)
    out["tokens_out"] = _mean(r["tokens_out"] for r in ok)
    out["tokens_thought"] = _mean(r.get("tokens_thought", 0) for r in ok)
    out["latency"] = _mean(r["latency"] for r in ok)
    out["rules"] = dict(Counter(x for r in ok for x in r["rules"]).most_common())
    return out


def aggregate(rows: list[dict]) -> dict:
    by_sys, by_cat = defaultdict(list), defaultdict(list)
    for r in rows:
        by_sys[r["system"]].append(r)
        by_cat[(r["system"], r["category"])].append(r)
    return {"overall": {s: summarize(v) for s, v in by_sys.items()},
            "by_category": {f"{s}|{c}": summarize(v) for (s, c), v in by_cat.items()}}
