"""Grounding checks: every product, price, rating, brand, color or size claim in a reply must
match the database. Ungrounded sentences are flagged so the engine can regenerate or strip them.

Limits: this catches factual claims about catalog fields. It cannot verify free-form claims
(e.g. "waterproof"), so prompts also tell the model to say when the data doesn't cover something."""
import re
from dataclasses import dataclass, field

_CUR = re.compile(r"₹\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:rupees|inr)\b", re.I)
_RATING = re.compile(
    r"\b(\d(?:\.\d)?)\s*(?:/\s*5\b|stars?\b|out of 5\b)|(?:★|\brated?\b|\brating(?: of)?\b)\s*(\d(?:\.\d)?)", re.I
)
_SIZE = re.compile(r"\bsize\s*(\d{1,2}(?:\.5)?)\b", re.I)
_NEG = re.compile(r"\b(not|no|none|neither|unavailable|sold out|without|out of stock)\b|n't", re.I)


@dataclass
class Facts:
    products: list = field(default_factory=list)
    brands: set = field(default_factory=set)   # every brand in the catalog
    colors: set = field(default_factory=set)   # every color in the catalog
    extra_amounts: set = field(default_factory=set)
    extra_ratings: set = field(default_factory=set)
    extra_colors: set = field(default_factory=set)
    check_sizes: bool = False


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\bRs\.?\s*", "₹", text, flags=re.I)
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def check_sentence(sentence: str, f: Facts) -> list[str]:
    problems = []
    prices = {int(p["price"]) for p in f.products} | {int(a) for a in f.extra_amounts}
    for m in _CUR.finditer(sentence):
        try:
            amount = int(round(float((m.group(1) or m.group(2)).replace(",", ""))))
        except ValueError:
            continue
        if amount not in prices:
            problems.append(f"price ₹{amount:,} is not in the data")

    ok_brands = {p["brand"].lower() for p in f.products}
    text = sentence
    for b in f.brands:
        pat = re.compile(rf"\b{re.escape(b)}\b", re.I)
        if pat.search(text):
            if b.lower() not in ok_brands:
                problems.append(f"brand {b} is not in the data")
            text = pat.sub(" ", text)  # so "Red Tape" is not read as the color red

    ok_colors = {p["color"].lower() for p in f.products} | {c.lower() for c in f.extra_colors}
    for c in f.colors:
        if re.search(rf"\b{re.escape(c)}\b", text, re.I) and c.lower() not in ok_colors:
            problems.append(f"color {c} is not in the data")

    ratings = {float(p["rating"]) for p in f.products} | {float(r) for r in f.extra_ratings}
    for m in _RATING.finditer(sentence):
        val = float(m.group(1) or m.group(2))
        if not any(abs(val - r) < 0.05 for r in ratings):
            problems.append(f"rating {val} is not in the data")

    if f.check_sizes and not _NEG.search(sentence):
        stock = {float(s) for p in f.products for s in p.get("sizes_in_stock", [])}
        for m in _SIZE.finditer(sentence):
            if float(m.group(1)) not in stock:
                problems.append(f"size {m.group(1)} is not shown as in stock")
    return problems


def validate(text: str, f: Facts) -> list[str]:
    return [p for s in _sentences(text) for p in check_sentence(s, f)]


def strip_ungrounded(text: str, f: Facts) -> str:
    return " ".join(s for s in _sentences(text) if not check_sentence(s, f))
