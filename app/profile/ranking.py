"""Turn a profile into a re-ranking of search results, and explain it in soft, honest language.

The palettes are a general styling heuristic, not a fact about anyone. They only nudge ranking
(nothing is hidden) and the wording is always "tends to complement", never "won't suit you"."""
from app.profile.model import STRONG, Profile

PALETTES = {
    "warm": {
        "best": ["brown", "tan", "olive", "red"], "ok": ["black", "navy", "grey", "white"],
        "reason": "earthy shades like brown, tan, olive and red tend to complement warm undertones",
    },
    "cool": {
        "best": ["navy", "grey", "black", "white"], "ok": ["red"],
        "reason": "cooler shades like navy, grey, black and white tend to complement cool undertones",
    },
    "neutral": {
        "best": ["navy", "grey", "olive", "brown", "black"], "ok": ["white", "tan", "red"],
        "reason": "navy, grey, olive, brown and black tend to work well with neutral undertones",
    },
}


def palette_note(undertone: str) -> str:
    reason = PALETTES[undertone]["reason"]
    return f"{reason[0].upper()}{reason[1:]}. That's a general styling guide, not a rule, so tell me if it doesn't feel right."


def color_score(profile: Profile, color: str) -> float:
    score = 0.0
    undertone = profile.value("undertone")
    if undertone in PALETTES:
        pal = PALETTES[undertone]
        score += 2 if color in pal["best"] else 1 if color in pal["ok"] else 0
    for f in profile.values("liked_color"):
        if f.value == color:
            score += 1.5 if f.status in STRONG else 0.5  # guesses count for less
    if any(f.value == color for f in profile.values("rejected_color")):
        score -= 5
    return score


def score(shoe: dict, profile: Profile) -> float:
    s = color_score(profile, shoe["color"])
    lo, hi = profile.value("budget_min"), profile.value("budget_max")
    if (lo or hi) and int(lo or 0) <= shoe["price"] <= int(hi or 10**9):
        s += 0.5
    return s


def rerank(rows: list[dict], profile: Profile, limit: int) -> list[dict]:
    """Stable: shoes with equal scores keep the search order (rating first)."""
    order = sorted(range(len(rows)), key=lambda i: (-score(rows[i], profile), i))
    return [rows[i] for i in order][:limit]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def explain(shown: list[dict], profile: Profile) -> str:
    parts = []
    undertone = profile.value("undertone")
    if undertone in PALETTES:
        present = list(dict.fromkeys(r["color"] for r in shown if r["color"] in PALETTES[undertone]["best"]))
        if present:
            parts.append(f"I've moved {_join(present)} pairs up because {PALETTES[undertone]['reason']}.")
    liked = [f for f in profile.values("liked_color") if any(r["color"] == f.value for r in shown)]
    if liked:
        names = _join([f.value for f in liked])
        guess = all(f.status not in STRONG for f in liked)
        parts.append(f"You seem to like {names}, so I've favoured it." if guess else f"You like {names}, so I've favoured it.")
    rejected = [f.value for f in profile.values("rejected_color")]
    if rejected:
        parts.append(f"I've pushed {_join(rejected)} down since you'd rather avoid it.")
    return " ".join(parts)
