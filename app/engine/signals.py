"""Deterministic backstops for things a lighter model sometimes mislabels. They only add information the
shopper plainly stated (an exact budget, a fit question, "I'll take it"); they never override a clearer LLM label."""
import re

_BUDGET = re.compile(
    r"(?:under|below|less than|within|up ?to|upto|max(?:imum)?(?: of)?|budget(?: is| of| max)?|not more than|no more than)"
    r"\s*(?:rs\.?|₹|inr)?\s*(\d[\d,]*)", re.I)
_FIT = re.compile(r"\b(?:run|runs|running)\s+(?:small|large|big|tight|narrow|wide)\b|\btrue to size\b|\bwill (?:it|they) fit\b|"
                  r"\bdo(?:es)? (?:it|they|these|those) fit\b|\bsize (?:up|down)\b|\btoo (?:tight|loose|snug)\b|\bsizing\b", re.I)
_QUALITY = re.compile(r"\bwill (?:it|they) last\b|\bdurab|\bwell[- ]made\b|\bfall apart\b|\bwear out\b|\blooks? cheap\b|\bcheaply made\b", re.I)
_TAKE = re.compile(r"\b(?:i'?ll|i will|i'?m going to|i'?d like to|i want to|let'?s)\s+(?:take|buy|get|order|go with)\b|"
                   r"\b(?:take|buy|get) (?:it|them|this|that|those)\b|\bprocess (?:it|that|my order|the order)\b", re.I)
_DECLINE = re.compile(r"\b(?:no,? thanks?|no thank you|not interested|never ?mind)\b", re.I)
_REQUEST_CUE = re.compile(r"\b(?:but|instead|actually|however|though|show me|i want|i need|looking for|can you|could you)\b", re.I)
_JUST_LOOKING = re.compile(r"\bjust (?:browsing|looking|checking)\b", re.I)
_OPEN_CUE = re.compile(r"\b(?:show me|surprise me|what do you have|recommend|suggest|ideas?|bore(?:d|dom)|anything good)\b", re.I)


def is_just_looking(message: str) -> bool:
    """"Just browsing, thanks" is the classic shop brush-off: no pitch, no products. It becomes an invitation only when the
    shopper also asks for one ("just looking, surprise me", "I'm bored")."""
    return bool(_JUST_LOOKING.search(message)) and not _OPEN_CUE.search(message) and not _REQUEST_CUE.search(message)


def explicit_decline(message: str) -> bool:
    """A plain "no thanks" / "not interested" is a no, however the rest of the sentence reads ("no thanks, just
    browsing"). A sentence that also makes a new request ("no thanks, but show me sports shoes") is left to the LLM."""
    return bool(_DECLINE.search(message)) and not _REQUEST_CUE.search(message)
_CATEGORY_WORDS = {
    "apparel": r"t-?shirts?|tees?|shirts?|jackets?|hoodies?|sweatshirts?|jeans|trousers|pants|chinos|shorts|blazers?|kurtas?|sweaters?|polos?|clothes|clothing|apparel|outfits?",
    "accessories": r"bags?|backpacks?|belts?|watch(?:es)?|caps?|hats?|wallets?|sunglasses|scarves|scarf|accessor(?:y|ies)|ties",
    "shoes": r"shoes?|sneakers?|loafers?|sandals?|boots?|footwear|trainers?",
}
_CATEGORY_RE = {k: re.compile(rf"\b(?:{v})\b", re.I) for k, v in _CATEGORY_WORDS.items()}


def detect_category(message: str) -> str | None:
    """"a casual shirt" -> apparel, "a laptop bag" -> accessories, "sneakers" -> shoes. Ambiguous or none -> None."""
    hits = [k for k, rx in _CATEGORY_RE.items() if rx.search(message)]
    return hits[0] if len(hits) == 1 else None


_OCCASIONS = re.compile(
    r"\b(party|partying|wedding|interview|date|date night|birthday|festival|event|gala|night out|clubbing|dinner|vacation|trip|celebration|reception)\b",
    re.I,
)


def detect_occasion(message: str) -> str | None:
    m = _OCCASIONS.search(message)
    return m.group(1).lower() if m else None


_SPECIFIC_ITEMS = re.compile(
    r"\b(t-?shirts?|tees?|polo(?: shirt)?s?|shirts?|chinos|trousers|pants|jeans|shorts|blazers?|hoodies?|jackets?|"
    r"sweatshirts?|sneakers?|oxfords?|derby|derbies|loafers?|brogues?|boots?|sandals?|backpacks?|"
    r"gym bags?|laptop bags?|wallets?|belts?|watch(?:es)?|sunglasses|caps?|ties?)\b",
    re.I,
)


def detect_item_type(message: str) -> str | None:
    m = _SPECIFIC_ITEMS.search(message)
    return m.group(1).lower() if m else None


def is_broad_category(message: str, category: str | None = None) -> bool:
    """True if user explicitly asked for generic clothes/clothing/apparel or clicked broad category chips."""
    clean = message.strip().lower()
    if clean in {
        "shoes", "looking for shoes", "i'm looking for shoes",
        "accessories", "looking for accessories", "i'm looking for accessories",
        "clothes", "looking for clothes", "i'm looking for clothes",
    }:
        return True
    if re.search(r"\b(clothes|clothing|apparel)\b", message, re.I) and not detect_item_type(message):
        return True
    return False


_SEMANTIC_TERMS = re.compile(
    r"\b(monsoon|rainy?|waterproof|water-resistant|light(?:weight)?|breathable|cushion(?:ed|ing)?|"
    r"comfort(?:able)?|summer|winter|interview|workout|gym|walking|travel|wrinkle-free|durable|sturdy|grip)\b",
    re.I,
)


def detect_semantic_query(message: str) -> str | None:
    matches = _SEMANTIC_TERMS.findall(message)
    if matches:
        return " ".join(dict.fromkeys(m.lower() for m in matches))
    return None


def explicit_budget(message: str) -> int | None:
    """"under ₹899", "max 2,000", "my budget of 1500": an exact ceiling (numbers under 300 are sizes, not prices)."""
    m = _BUDGET.search(message)
    if not m:
        return None
    value = int(m.group(1).replace(",", "") or 0)
    return value if value >= 300 else None


def is_fit_question(message: str) -> bool:
    return bool(_FIT.search(message))


def is_quality_question(message: str) -> bool:
    return bool(_QUALITY.search(message))


def is_take(message: str) -> bool:
    return bool(_TAKE.search(message))
