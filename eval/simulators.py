"""Simulated shoppers. ScriptedUser is deterministic and free (smoke tests, regression runs of the agent).
LLMUser role-plays the persona card with Gemini and is what the headline comparison should use."""
import re

from pydantic import BaseModel

from app.engine.common import APPAREL_SIZES
from eval.types import Conversation, Persona, Turn


def _fmt(x) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


class ScriptedUser:
    def __init__(self, persona: Persona):
        self.p, self.n, self.queue, self.started, self.did_off = persona, 0, [], False, False

    def _plan(self) -> list[str]:
        p, cat = self.p, self.p.category
        if cat == "price_objection":
            return ["tell me about the first one", "that's too expensive", "show me the second one", "buy this"]
        if cat == "indecision":
            return ["compare the first and second", "what do you think of the second one?", "buy this"]
        if cat == "sizing_stock":
            return ["show me the first one", "will it fit?", "buy this"]
        if cat == "vague":
            prod = getattr(p, "product_category", "shoes")
            if prod == "apparel":
                sz = APPAREL_SIZES.get(int(p.size), "M") if p.size else "M"
                return [f"I want {p.use} clothes, size {sz}", "show me the first one", "buy this"]
            if prod == "accessories":
                return [f"I want {p.use} accessories", "show me the first one", "buy this"]
            return [f"I want {p.use} shoes, size {_fmt(p.size)}", "show me the first one", "buy this"]
        return ["show me the first one", "buy this"]

    def next(self, last: Turn | None) -> str | None:
        p, self.n = self.p, self.n + 1
        if self.n > p.max_turns:
            return None
        if last is None:
            return p.opening
        t = last.text.lower()
        if p.category == "rejection":
            seq = ["no thanks", "ok", "thanks"]
            return seq[self.n - 2] if self.n - 2 < len(seq) else None
        if last.order_id:
            return None
        if "place order" in t and "confirm" in t:
            return "yes, place the order"
        if p.expected_empty:
            return "ok, thanks" if "couldn't find" in t and self.n < 4 else None
        if p.category == "vague" and "show me something" in t and not getattr(self, "asked_browse", False):
            self.asked_browse = True
            return "sure, show me something"
        if "for you, or for someone else" in t:
            return "for me" if p.for_whom == "self" else "for my brother"
        if "what size" in t:
            prod = getattr(p, "product_category", "shoes")
            if prod == "apparel":
                return APPAREL_SIZES.get(int(p.size), "M") if p.size else "M"
            return _fmt(p.size) if p.size else "9"
        if "sports, office or casual" in t:
            prod = getattr(p, "product_category", "shoes")
            if prod == "apparel":
                return f"{p.use} clothes"
            if prod == "accessories":
                return f"{p.use} accessories"
            return f"{p.use} shoes"
        if p.category == "off_topic" and not self.did_off:
            self.did_off = True
            prod = getattr(p, "product_category", "shoes")
            if prod == "apparel":
                sz = APPAREL_SIZES.get(int(p.size), "M") if p.size else "M"
                return f"I need {p.use} clothes, size {sz}"
            if prod == "accessories":
                return f"I need {p.use} accessories"
            return f"I need {p.use} shoes, size {_fmt(p.size)}"
        if p.category == "frustration" and self.n == 4:
            return "this is taking forever, are you even listening?"
        if last.shown_ids and not self.started:
            self.started, self.queue = True, self._plan()
        if self.started and self.queue:
            return self.queue.pop(0)
        return None

    def verdict(self, conv: Conversation) -> dict:
        bought = any(t.order_id for t in conv.turns)
        outcome = "buy" if bought else ("no_buy" if self.p.category == "rejection" or self.p.expected_empty else "abandon")
        return {"outcome": outcome, "purchase_intent": None, "felt_pressured": None, "natural": None, "chosen": ""}


class UserTurn(BaseModel):
    message: str
    end: bool = False
    outcome: str | None = None            # buy | no_buy | abandon
    purchase_intent: int | None = None    # 1-5, how likely you'd really buy after this chat
    felt_pressured: bool | None = None
    natural: int | None = None            # 1-5, how natural and human the assistant felt
    chosen: str | None = None


class JudgeResult(BaseModel):
    answered_off_topic: bool | None = None
    objection_addressed: bool | None = None
    pitched_after_no: bool | None = None
    invented_facts: bool = False
    notes: str = ""


USER_SYSTEM = """You role-play a shopper chatting with a store sales assistant (shoes, clothes, accessories). Stay in character, write 1-2
casual sentences, reveal your needs gradually and only when asked or natural, and never mention that you are
simulated. Items shown on the assistant's screen are listed in brackets; refer to them by position or name.
Tell the assistant when you decide to buy something specific; if it asks you to confirm an order, confirm.
Never end the conversation in the same message in which you ask to buy: wait for the assistant's reply and follow
any instruction it gives to finish (for example, if it says to type 'place order', do that). End (end=true) only
when an order is confirmed or the assistant says it is done, you have decided not to buy, or you have given up in
frustration, and then fill the verdict: outcome (buy / no_buy / abandon), purchase_intent 1-5 (how likely you would really buy after
this chat), felt_pressured, natural 1-5 (how natural and human the assistant felt), chosen (what you chose, in
words). Return JSON only."""

JUDGE_SYSTEM = """You audit a shopping-assistant conversation. Return JSON only:
- answered_off_topic: true if the shopper asked an unrelated question and got a brief, correct answer and the
  assistant did not start pushing products (one friendly line steering back to products is fine); false if it
  dodged or ignored the question, or pushed products or several shopping questions; null if no such question.
- objection_addressed: true if the shopper raised a concern (price, fit or quality) and the assistant addressed
  it with evidence, alternatives or an honest admission that it lacked data; false if it ignored it or bluffed;
  null if no concern was raised.
- pitched_after_no: true if, after the shopper said no / not interested, the assistant kept pitching products or
  asking shopping questions; null if the shopper never said no.
- invented_facts: true if the assistant stated specific product facts (names, prices, stock, specs) it could not
  know or that contradict what is shown on screen.
- notes: one short sentence."""


class LLMUser:
    def __init__(self, persona: Persona, llm):
        self.p, self.llm = persona, llm

    def next(self, transcript: str, force_end: bool = False) -> UserTurn:
        extra = "\nThe conversation must end now: set end=true and give your verdict." if force_end else ""
        prompt = f"Your private persona card:\n{self.p.hidden}\n\nConversation so far:\n{transcript or '(none yet)'}\n\nWrite your next message.{extra}"
        resp = self.llm._generate(prompt, USER_SYSTEM, 0.7, schema=UserTurn)
        parsed = getattr(resp, "parsed", None)
        return parsed if isinstance(parsed, UserTurn) else UserTurn.model_validate_json(resp.text)


def judge(llm, persona: Persona, transcript: str) -> dict:
    prompt = f"Shopper persona: {persona.hidden}\n\nTranscript:\n{transcript}"
    resp = llm._generate(prompt, JUDGE_SYSTEM, 0.0, schema=JudgeResult)
    parsed = getattr(resp, "parsed", None)
    return (parsed if isinstance(parsed, JudgeResult) else JudgeResult.model_validate_json(resp.text)).model_dump()


def screen_text(ids: list[int], conn) -> str:
    """What the shopper can see on the product panel, so they can say 'the second one'."""
    rows = []
    for i, pid in enumerate(ids, 1):
        s = conn.execute("SELECT * FROM shoes WHERE id=?", (pid,)).fetchone()
        sizes = [r["size"] for r in conn.execute("SELECT size FROM stock WHERE shoe_id=? AND qty>0 ORDER BY size", (pid,))]
        if s:
            cat = s["category"] if "category" in s.keys() else "shoes"
            if cat == "accessories":
                sz_str = "one size"
            elif cat == "apparel":
                sz_str = ", ".join(APPAREL_SIZES.get(int(x), _fmt(x)) for x in sizes)
            else:
                sz_str = ", ".join(_fmt(x) for x in sizes)
            rows.append(f"{i}. {s['name']}, {s['color']}, ₹{s['price']:,}, rated {s['rating']}, sizes {sz_str}")
    return ("[On screen: " + " | ".join(rows) + "]") if rows else ""


def transcript_text(turns: list[Turn], conn) -> str:
    out = []
    for t in turns:
        if t.role == "user":
            out.append(f"Shopper: {t.text}")
        else:
            screen = screen_text(t.shown_ids, conn)
            out.append(f"Assistant: {t.text}" + (f" {screen}" if screen else ""))
    return "\n".join(out)


__all__ = ["JudgeResult", "LLMUser", "ScriptedUser", "UserTurn", "judge", "re", "screen_text", "transcript_text"]
