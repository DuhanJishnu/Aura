"""Helpers shared by the engine and the salesperson behaviours."""
from app import config
from app.catalog.search import all_brands, all_colors
from app.engine.state import Session
from app.llm.client import LLM
from app.llm.schemas import Extraction
from app.schemas import ChatResponse, UIAction
from app.validators import Facts, strip_ungrounded, validate

FALLBACKS = {
    "greet": "Hi! I can help with shoes, clothes and accessories. What are you after, and what will you mostly use it for: sports, office or casual?",
    "ask_use": "What will you mostly use it for: sports, office or casual?",
    "ask_for_whom": "Are these for you, or for someone else?",
    "ask_size": "What size are you looking for?",
    "show": "Here are some options that match. Tap any to take a closer look.",
    "cheaper": "I've lowered the price range. Here are some cheaper options.",
    "other_colors": "Here are some options in other colors.",
    "show_more": "Here are some more to look at.",
    "no_results": "I couldn't find anything in stock that matches all of that. Want to loosen the budget or try another color?",
    "decline": "No problem at all. I'm here if you want to look at {noun} later.",
    "ask_which": "Which {item} do you mean? Tap one on the right, or tell me its position, like “the second one”.",
}
INSTRUCTIONS = {
    "greet": "Greet the user warmly and ask what they'll use it for (sports, office or casual).",
    "ask_use": "Ask what they will mostly use it for: sports, office or casual.",
    "ask_for_whom": "Ask whether it is for the user or for someone else.",
    "ask_size": "Ask what size they need.",
    "show": "Tell the user you've put matching items on the screen and invite them to tap one for details. Mention the top pick by its exact name with its price and one honest reason (its rating or price); you may name one more. Use only items listed in top_picks. One or two sentences, ask no question.",
    "cheaper": "Say you've lowered the price range and put cheaper options on screen. Mention the top pick by its exact name with its price and one honest reason (its rating or price); you may name one more. Use only items listed in top_picks. One or two sentences, ask no question.",
    "other_colors": "Say you've put options in other colors on screen. Mention the top pick by its exact name with its price and one honest reason (its rating or price); you may name one more. Use only items listed in top_picks. One or two sentences, ask no question.",
    "show_more": "Say you've added more options on screen. Mention the top pick by its exact name with its price and one honest reason (its rating or price); you may name one more. Use only items listed in top_picks. One or two sentences, ask no question.",
    "no_results": "Say nothing in stock matches all the filters and offer to loosen budget or color. Ask only one question.",
    "decline": "The user said no. Back off politely, do not pitch or ask questions, leave the door open.",
    "ask_which": "Ask which item they mean and tell them they can tap one or say its position.",
}
EMPTY = {
    "cheaper": "I don't have anything cheaper that matches. Want to try a different type or color instead?",
    "other_colors": "That's all the colors I have for those filters. Want to see more {noun} in the same colors?",
    "show_more": "That's everything I have for those filters. Want to loosen the budget or try another type?",
}


def _resp(session: Session, text: str, **ui) -> ChatResponse:
    return ChatResponse(reply=text, slots=session.slots, ui_action=UIAction(**ui) if ui else UIAction())


def _n(x: float) -> str:
    return f"{x:,.0f}"


NOUNS = {"shoes": ("shoes", "shoe"), "apparel": ("clothes", "item"), "accessories": ("accessories", "accessory")}
APPAREL_SIZES = {1: "XS", 2: "S", 3: "M", 4: "L", 5: "XL", 6: "XXL"}
SIZE_ASK = {"shoes": "What size are you looking for?", "apparel": "What size do you wear: XS, S, M, L, XL or XXL?"}


def noun(session) -> str:
    return NOUNS.get(session.slots.category or "shoes", NOUNS["shoes"])[0]


def item(session) -> str:
    return NOUNS.get(session.slots.category or "shoes", NOUNS["shoes"])[1]


def plural_of(shoe: dict) -> str:
    return NOUNS.get(shoe.get("category") or "shoes", NOUNS["shoes"])[0]


def size_label(category: str | None, x: float) -> str:
    """9 -> "9" for shoes, 3 -> "M" for apparel, 0 -> "one size" for accessories."""
    if category == "accessories":
        return "one size"
    if category == "apparel":
        return APPAREL_SIZES.get(int(x), _sz(x))
    return _sz(x)


def size_for(shoe: dict, slots) -> float | None:
    """The size to use for this product from what the shopper told us, or None if we must ask (a shoe size says
    nothing about a shirt)."""
    category = shoe.get("category") or "shoes"
    if category == "accessories":
        return 0.0
    return slots.size if (slots.category or "shoes") == category else None


def _sz(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def _facts(conn, session: Session, products=(), **kw) -> Facts:
    s = session.slots
    amounts = {s.budget} if s.budget else set()
    amounts |= set(kw.pop("extra_amounts", ()))
    return Facts(products=list(products), brands=all_brands(conn), colors=all_colors(conn),
                 extra_amounts=amounts, extra_colors={s.color} if s.color else set(), **kw)


# Replies that carry no data are fixed text unless PHRASE_ALL=1: an LLM round trip costs seconds and adds nothing.
TEMPLATE_ONLY = {"just_looking", "greet", "ask_use", "ask_for_whom", "ask_size", "ask_which", "decline", "quiet", "no_results"}


def _say(llm: LLM, conn, session: Session, kind: str, context: dict | None = None, products=()) -> str:
    fallback = SIZE_ASK.get(session.slots.category or "shoes", SIZE_ASK["shoes"]) if kind == "ask_size" else FALLBACKS[kind]
    fallback = fallback.format(noun=noun(session), item=item(session))
    if kind in TEMPLATE_ONLY and not config.PHRASE_ALL:
        if fallback == session.last_reply and kind in ALTERNATES:
            return ALTERNATES[kind]  # never say the exact same sentence twice in a row
        return fallback
    try:
        text = llm.phrase(INSTRUCTIONS[kind], context or {}, fallback)
    except Exception:
        text = fallback
    facts = _facts(conn, session, products)
    if validate(text, facts):
        text = strip_ungrounded(text, facts)
    return text.strip() or fallback


def _target(session: Session, ex: Extraction) -> int | None:
    if ex.product_index and 1 <= ex.product_index <= len(session.shortlist):
        session.focused_id = session.shortlist[ex.product_index - 1]
    return session.focused_id



ALTERNATES = {
    "decline": "Sure, no worries. Take care!",
    "quiet": "Of course. Just say the word if you need anything.",
    "just_looking": "Take your time. I'm here if you need anything.",
    "no_results": "Still nothing in stock that fits that. Want to loosen the budget, try another color, or look at a different type?",
}
FALLBACKS.update({
    "just_looking": "Sure, take your time. I'm here if you'd like a hand, or say “show me something” and I'll put a few popular picks on screen.",
    "quiet": "Sure thing. I'm here whenever you'd like to look at {noun}.",
    "discover": "No rush. Here are a few of the best-rated picks across sports, office and casual, just to browse. Tap anything that catches your eye.",
    "ask_compare": "Show me a few options first, then tell me which ones to compare, like “compare the first and third”.",
})
INSTRUCTIONS.update({
    "just_looking": "Say you are happy for them to look around and offer to show picks if they ask. No question, no products.",
    "quiet": "The user earlier said no and is making small talk. Reply in one short, friendly sentence. Do not ask any question, do not mention products, do not offer anything.",
    "discover": "Be relaxed: say there's no rush and you've put a few popular picks on screen just to browse. Do not name items. Ask no questions and do not push.",
})


def grounded(generate, facts: Facts, fallback: str, min_len: int = 25) -> str:
    """Generate -> validate -> one regenerate -> strip bad sentences -> data-built fallback."""
    text, problems = "", []
    for _ in range(2):
        try:
            text = generate(problems or None)
        except Exception:
            text = ""
            break
        problems = validate(text, facts)
        if not problems:
            break
    if problems:
        text = strip_ungrounded(text, facts)
    return text.strip() if len(text.strip()) >= min_len else fallback
