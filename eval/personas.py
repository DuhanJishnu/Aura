"""Deterministic, catalog-aware simulated shoppers across the eight scenario types and three product categories."""
import random
from collections import defaultdict

from app.catalog.search import search_shoes
from app.engine.common import APPAREL_SIZES
from eval.types import Persona

CATEGORIES = ["vague", "strong_preference", "price_objection", "indecision",
              "rejection", "off_topic", "sizing_stock", "frustration"]
PRODUCT_CATEGORIES = ["shoes", "apparel", "accessories"]
OFF_TOPIC = ["what's the capital of France?", "what's the weather like today?", "how many days are in a leap year?"]
VAGUE = ["I'm bored, show me something", "just looking around", "not sure what I want, surprise me"]


def _fmt(x) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def _item_desc(prod_cat: str, use: str) -> str:
    if prod_cat == "apparel":
        return f"{use} clothes"
    if prod_cat == "accessories":
        return f"{use} accessories"
    return f"{use} shoes"


def _sz_desc(prod_cat: str, size: float) -> str:
    if prod_cat == "apparel":
        return f", size {APPAREL_SIZES.get(int(size), 'M')}"
    if prod_cat == "accessories":
        return ""
    return f", size {_fmt(size)}"


def availability(conn, category: str | None = None) -> dict:
    d = defaultdict(list)
    where = "WHERE k.qty>0"
    params = []
    if category:
        where += " AND s.category=?"
        params.append(category)
    for r in conn.execute(f"SELECT s.use_type, k.size, s.price FROM shoes s JOIN stock k ON k.shoe_id=s.id {where}", params):
        d[(r[0], r[1])].append(r[2])
    return d


def generate(conn, n: int, seed: int = 7) -> list[Persona]:
    rnd = random.Random(seed)
    av_by_cat = {c: availability(conn, c) for c in PRODUCT_CATEGORIES}

    pools = {
        "shoes": {
            "rich": sorted(k for k, v in av_by_cat["shoes"].items() if len(v) >= 6 and 7 <= k[1] <= 11),
            "scarce": sorted(k for k, v in av_by_cat["shoes"].items() if 1 <= len(v) <= 3),
        },
        "apparel": {
            "rich": sorted(k for k, v in av_by_cat["apparel"].items() if len(v) >= 4 and 1 <= k[1] <= 6),
            "scarce": sorted(k for k, v in av_by_cat["apparel"].items() if 1 <= len(v) <= 2),
        },
        "accessories": {
            "rich": sorted(k for k, v in av_by_cat["accessories"].items() if len(v) >= 3),
            "scarce": sorted(k for k, v in av_by_cat["accessories"].items() if 1 <= len(v) <= 2),
        },
    }

    personas = []
    for i in range(n):
        cat = CATEGORIES[i % len(CATEGORIES)]
        if cat == "sizing_stock":
            prod_cat = "apparel" if (i // len(CATEGORIES)) % 2 == 1 else "shoes"
        else:
            prod_cat = PRODUCT_CATEGORIES[i % len(PRODUCT_CATEGORIES)]

        rich = pools[prod_cat]["rich"]
        scarce = pools[prod_cat]["scarce"]
        pool = scarce if cat == "sizing_stock" and scarce else rich
        use, size = rnd.choice(pool)

        if cat == "price_objection":  # the top-rated item must have cheaper alternatives
            for use, size in rnd.sample(rich, len(rich)):
                sz_filter = None if prod_cat == "accessories" else size
                matches = search_shoes(conn, use=use, size=sz_filter, category=prod_cat, limit=1)
                if matches:
                    top = matches[0]
                    if sum(1 for x in av_by_cat[prod_cat][(use, size)] if x <= top["price"] * 0.9) >= 2:
                        break

        prices = sorted(av_by_cat[prod_cat][(use, size)])
        budget = round(prices[int(len(prices) * 0.6)], -2) if rnd.random() < 0.5 and cat in ("strong_preference", "frustration", "indecision") else None
        whom = "other" if rnd.random() < 0.15 else "self"
        who = " for my brother" if whom == "other" else ""
        desc = _item_desc(prod_cat, use)
        sz_desc = _sz_desc(prod_cat, size)
        sz_name = APPAREL_SIZES.get(int(size), "M") if prod_cat == "apparel" else _fmt(size)
        need = f"{desc}{who}{sz_desc}" + (f", under {budget}" if budget else "")
        opening, off, objection, empty = f"I need {need}", None, None, False

        if prod_cat == "accessories":
            hidden = f"You want {desc}" + (f" and won't pay more than ₹{budget}" if budget else "") + "."
        else:
            hidden = f"You want {desc} in size {sz_name}" + (f" and won't pay more than ₹{budget}" if budget else "") + "."

        if whom == "other":
            hidden += " They are a gift for your brother; the size is his." if prod_cat != "accessories" else " It is a gift for your brother."

        if cat == "vague":
            opening = rnd.choice(VAGUE)
            if prod_cat == "accessories":
                hidden = f"You start vague and bored. If asked what you want, you want {desc}. You buy if something fits."
            else:
                hidden = f"You start vague and bored. If asked what you want, you want {desc}, size {sz_name}. You buy if something fits."
        elif cat == "price_objection":
            objection = "price"
            item_noun = "item" if prod_cat != "shoes" else "shoe"
            hidden += f" You find the first {item_noun} the assistant recommends too expensive and say so. You buy only something clearly cheaper that still fits your needs."
        elif cat == "indecision":
            hidden += " You are undecided between options. You want a comparison or an honest opinion before choosing, then you choose one."
        elif cat == "rejection":
            opening = rnd.choice(["hi", "just checking this out"])
            use = size = budget = None
            hidden = "You are not interested in buying today. After the assistant's first reply say 'no thanks' politely. If it keeps pitching, get annoyed. Never change your mind."
        elif cat == "off_topic":
            off = rnd.choice(OFF_TOPIC)
            opening = off
            hidden += f" You begin by asking an unrelated question ('{off}') and expect a brief answer without being pushed. Then you shop normally and buy."
        elif cat == "sizing_stock":
            objection = "fit"
            empty = rnd.random() < 0.5
            noun_word = "clothes" if prod_cat == "apparel" else "shoes"
            if empty:
                budget = max(prices[0] - 200, 100)
                opening = f"I need {desc}{sz_desc}, under {budget}"
                hidden = f"You want {desc}{sz_desc} under ₹{budget}. If nothing matches, you want an honest answer, not a hard sell."
            else:
                hidden += f" Your size is hard to find. You worry whether the {noun_word} run small and ask. You buy if it is in stock in your size."
        elif cat == "frustration":
            noun_word = "shoes" if prod_cat == "shoes" else ("clothes" if prod_cat == "apparel" else "shopping")
            opening = f"ugh, {noun_word}. {need}"
            hidden += " You are impatient and a bit rude. If the assistant asks too many questions or repeats itself, say so. You still buy if helped quickly."

        personas.append(Persona(f"p{i:03d}", cat, use, size, budget, whom, objection, opening, off, hidden, empty, product_category=prod_cat))
    return personas
