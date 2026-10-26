"""Understand unambiguous messages without an LLM call (an LLM round trip costs seconds).

Deliberately conservative: anything that is not an exact, simple pattern returns None and goes to the LLM,
so this can only make easy cases faster, never change a hard one."""
import re

from app.llm.schemas import Extraction

_GREETING = re.compile(r"^\W*(hi+|hello|hey+|good (morning|afternoon|evening))\W*$", re.I)
_DECLINE = re.compile(r"\b(no,? thanks?|no thank you|not interested|never ?mind)\b", re.I)
_YES = re.compile(r"^\W*(yes|yeah|yep|yup|sure|ok(ay)?|go ahead|confirm(ed)?|place (the |my )?order|"
                  r"yes,? (please|go ahead|place (the |my )?order)|that'?s right|looks good)\W*$", re.I)
_SIZE = re.compile(r"^\W*(?:uk\s*)?(?:size\s*)?(\d{1,2}(?:\.5)?)\W*$", re.I)
_LETTER = re.compile(r"^\W*(?:size\s*)?(xxl|xl|xs|s|m|l|small|medium|large|extra large)\W*$", re.I)
_LETTERS = {"xs": 1, "s": 2, "small": 2, "m": 3, "medium": 3, "l": 4, "large": 4, "xl": 5, "extra large": 5, "xxl": 6}
_USE = re.compile(r"^\W*(sports?|office|casual)(\s+shoes)?\W*$", re.I)
_SELF = re.compile(r"^\W*(for me|for myself|myself|me)\W*$", re.I)
_OTHER = re.compile(r"^\W*(for someone else|someone else|a gift|for a gift)\W*$", re.I)
_FORGET = re.compile(r"\b(forget|delete|erase|clear) (my )?(profile|data)\b", re.I)
_ORD = r"(first|second|third|fourth|fifth|sixth)"
_NUM = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}
_FOCUS = re.compile(rf"^\W*(?:show|tell) me (?:more )?(?:about )?the {_ORD} one\W*$", re.I)
_OPINION = re.compile(rf"^\W*what do you think (?:of|about) (?:it|this|that|the {_ORD} one)\W*$", re.I)
_COMPARE = re.compile(rf"^\W*compare (?:the )?{_ORD} (?:one )?and (?:the )?{_ORD}(?: one)?\W*$", re.I)
_BUY = re.compile(r"^\W*(?:(?:buy|take|get) (?:this|it|that)(?: one)?|i'?ll take (?:it|this|that)(?: one)?)\W*$", re.I)
_CHECKOUT = re.compile(r"^\W*(?:place (?:the |my )?order|check ?out)\W*$", re.I)
_CHEAPER = re.compile(r"^\W*(?:show me |any |got )?(?:something |anything )?cheaper(?: ones?| options?)?\W*$", re.I)
_MORE = re.compile(r"^\W*(?:show )?(?:me )?more(?: options| shoes)?\W*$", re.I)
_COLORS = re.compile(r"^\W*(?:any |show me )?(?:other|different) colou?rs\W*$", re.I)
_SHOW = re.compile(r"\bwhat do you (know|have) (about|on) me\b", re.I)


def fastpath(message: str, known: dict) -> Extraction | None:
    m = message.strip()
    if not m or len(m) > 60:
        return None
    if _FORGET.search(m):
        return Extraction(intent="profile_forget")
    if _SHOW.search(m):
        return Extraction(intent="profile_show")
    if _DECLINE.search(m) and len(m.split()) <= 6:
        return Extraction(intent="decline")  # an explicit no beats everything else in the message
    if _CHECKOUT.match(m) and known.get("items_in_cart"):
        return Extraction(intent="checkout")
    if _BUY.match(m):
        return Extraction(intent="buy")
    if (o := _FOCUS.match(m)):
        return Extraction(intent="focus", product_index=_NUM[o.group(1).lower()])
    if (o := _OPINION.match(m)):
        return Extraction(intent="opinion", product_index=_NUM[o.group(1).lower()] if o.group(1) else None)
    if (o := _COMPARE.match(m)):
        return Extraction(intent="compare", compare_indices=[_NUM[o.group(1).lower()], _NUM[o.group(2).lower()]])
    if _CHEAPER.match(m):
        return Extraction(intent="refine", refine="cheaper")
    if _MORE.match(m):
        return Extraction(intent="refine", refine="show_more")
    if _COLORS.match(m):
        return Extraction(intent="refine", refine="other_colors")
    waiting = (known.get("awaiting_order_confirmation") or known.get("awaiting_photo_consent")
               or known.get("pending_complexion_estimate"))
    if waiting and _YES.match(m):
        return Extraction(intent="confirm")
    if _GREETING.match(m):
        return Extraction(intent="greeting")
    slots = known.get("slots", {})
    category = slots.get("category")
    if category == "apparel" and slots.get("size") is None and (lt := _LETTER.match(m)):
        return Extraction(intent="shopping", size=float(_LETTERS[lt.group(1).lower()]))
    if (s := _SIZE.match(m)) and category in (None, "shoes") and slots.get("size") is None and 4 <= float(s.group(1)) <= 14:
        return Extraction(intent="shopping", size=float(s.group(1)))
    if u := _USE.match(m):
        word = u.group(1).lower()
        return Extraction(intent="shopping", use="sports" if word.startswith("sport") else word)
    if _SELF.match(m):
        return Extraction(intent="shopping", for_whom="self")
    if _OTHER.match(m):
        return Extraction(intent="shopping", for_whom="other")
    return None
