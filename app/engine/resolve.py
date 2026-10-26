"""Resolve "the black Vans Canvas Low" style references to shoes that are on screen.

Deterministic on purpose: positions ("the second one") come from the LLM, names are matched here so
a shopper who names a shoe is understood even when the LLM gives no position. Ambiguous names return
nothing, so the engine asks instead of guessing."""
import re


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}  # "Oxfords" == "Oxford"


def resolve_mentions(message: str, shoes: list[dict], colors: set[str], prefer_id: int | None = None) -> list[dict]:
    msg = _tokens(message)
    colors = {c.lower() for c in colors}
    found = []
    for shoe in shoes:
        name = _tokens(shoe["name"])
        if not name <= msg:
            continue
        # a color word that is not part of the shoe's own name ("Red" in "Red Tape") must match its color
        said = {c for c in colors if c in msg and c not in name}
        if said and shoe["color"].lower() not in said:
            continue
        found.append(shoe)
    # The same model in several colors is on screen: use a price the shopper quoted ("at ₹1,999"), else the shoe
    # the assistant itself just recommended, else give up and let the engine ask.
    numbers = _numbers(message)
    groups: dict[str, list[dict]] = {}
    for shoe in found:
        groups.setdefault(shoe["name"], []).append(shoe)
    resolved = []
    for group in groups.values():
        if len(group) > 1:
            by_price = [s for s in group if s["price"] in numbers]
            preferred = [s for s in group if s["id"] == prefer_id]
            if len(by_price) == 1:
                group = by_price
            elif len(preferred) == 1:
                group = preferred
            else:
                return []
        resolved.append(group[0])
    return resolved


def _numbers(text: str) -> set[int]:
    return {int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", text) if x.replace(",", "").isdigit()}


def resolve_by_price(message: str, shoes: list[dict]) -> list[dict]:
    """"That ₹1,999 one is too pricey": a quoted price that matches exactly one shoe on screen."""
    numbers = _numbers(message)
    hits = [s for s in shoes if s["price"] in numbers]
    return hits if len(hits) == 1 else []
