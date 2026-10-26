"""The three systems under comparison, behind one interface: respond(message) -> assistant Turn.

A  plain     a good prompt, no catalog access, no tools          (the "just use an LLM" baseline)
B  rag       LLM + catalog retrieval + running memory of needs   (no decision policy, no validator)
C  agent     this project: rule-table decisions + grounded retrieval + validator + cart"""
import json
import re
import time

from pydantic import BaseModel

from app.catalog.search import search_shoes
from app.engine.engine import handle
from app.engine.state import Session
from eval.types import Turn

PLAIN_SYSTEM = """You are a friendly, honest sales assistant for shoppers in India (selling shoes, clothes and accessories). Talk like a helpful
friend, not a form: ask one question at a time, find out what they are for (sports, office or casual), who
they're for and the size, then recommend. Give honest opinions including trade-offs. Handle concerns about price,
fit or quality with evidence or honest uncertainty. If the shopper says no or isn't interested, back off politely
and don't keep pitching. Answer off-topic questions briefly. You cannot see live inventory or exact prices, so
never invent specific prices or stock levels. Keep replies to 1-3 sentences."""

RAG_SYSTEM = """You are a friendly, honest sales assistant for shoppers in India (selling shoes, clothes and accessories). Use ONLY the products
listed under 'Catalog results' for any product, price, rating or stock claim, and cite each product you recommend
as [#id]. Ask one question at a time when you need the use (sports, office, casual) or size. Give honest opinions
including trade-offs. If the shopper says no, back off politely. You cannot place orders: when the shopper decides,
confirm what they chose. Keep replies to 1-3 sentences. Never invent products or prices."""

NEEDS_SYSTEM = "Extract the shopper's needs from the conversation as JSON. Use null for anything not stated."


class Needs(BaseModel):
    category: str | None = None   # shoes | apparel | accessories
    use: str | None = None        # sports | office | casual
    size: float | None = None
    budget: int | None = None
    color: str | None = None


class _Base:
    name = "base"

    def __init__(self, conn, llm, conv_id: str):
        self.conn, self.llm, self.conv_id = conn, llm, conv_id

    def _usage(self) -> tuple[int, int, int]:
        u = getattr(self.llm, "usage", None) or {}
        return u.get("in", 0), u.get("out", 0), u.get("thought", 0)

    def _timed(self, fn) -> Turn:
        i0, o0, h0 = self._usage()
        t0 = time.perf_counter()
        turn = fn()
        turn.latency = time.perf_counter() - t0
        i1, o1, h1 = self._usage()
        turn.tokens_in, turn.tokens_out, turn.tokens_thought = i1 - i0, o1 - o0, h1 - h0
        return turn

    def respond(self, message: str) -> Turn:
        return self._timed(lambda: self._respond(message))


class AgentSystem(_Base):
    name = "agent"

    def __init__(self, conn, llm, conv_id):
        super().__init__(conn, llm, conv_id)
        self.session = Session(user_id=conv_id)

    def _respond(self, message: str) -> Turn:
        r = handle(self.session, message, self.llm, self.conn)
        ui = r.ui_action
        shown = list(ui.product_ids) or ([ui.product_id] if ui.product_id else [])
        ceiling = ui.filters.get("max_price")
        return Turn("assistant", r.reply, shown, ui.type, (r.policy or {}).get("rule"), ui.order_id,
                    amounts=[int(ceiling)] if ceiling else [])


class PlainSystem(_Base):
    name = "plain"

    def __init__(self, conn, llm, conv_id):
        super().__init__(conn, llm, conv_id)
        self.history: list[str] = []

    def _respond(self, message: str) -> Turn:
        self.history.append(f"Shopper: {message}")
        prompt = "Conversation so far:\n" + "\n".join(self.history) + "\nReply as the assistant."
        text = (self.llm._generate(prompt, PLAIN_SYSTEM, 0.7).text or "").strip()
        self.history.append(f"Assistant: {text}")
        return Turn("assistant", text)


class RagSystem(_Base):
    name = "rag"

    def __init__(self, conn, llm, conv_id):
        super().__init__(conn, llm, conv_id)
        self.history: list[str] = []
        self.memory = Needs()

    def _needs(self) -> Needs:
        prompt = "Conversation:\n" + "\n".join(self.history)
        resp = self.llm._generate(prompt, NEEDS_SYSTEM, 0.0, schema=Needs)
        parsed = getattr(resp, "parsed", None)
        return parsed if isinstance(parsed, Needs) else Needs.model_validate_json(resp.text)

    def _retrieve(self) -> list[dict]:
        m = self.memory
        cat = m.category or "shoes"
        if m.use in ("sports", "office", "casual"):
            return search_shoes(self.conn, use=m.use, size=m.size, max_price=m.budget, color=m.color, category=cat, limit=5)
        rows = []
        for use in ("sports", "office", "casual"):
            rows += search_shoes(self.conn, use=use, category=cat, limit=2)
        return rows

    def _respond(self, message: str) -> Turn:
        self.history.append(f"Shopper: {message}")
        try:
            new = self._needs()
            for k in ("category", "use", "size", "budget", "color"):
                if getattr(new, k) is not None:
                    setattr(self.memory, k, getattr(new, k))
        except Exception:
            pass  # memory update is best-effort, like retrieval
        rows = self._retrieve()
        catalog = [{"id": r["id"], "name": r["name"], "price": r["price"], "color": r["color"],
                    "use": r["use_type"], "rating": r["rating"]} for r in rows]
        prompt = (f"Known needs: {json.dumps(self.memory.model_dump())}\nCatalog results: {json.dumps(catalog)}\n"
                  "Conversation so far:\n" + "\n".join(self.history) + "\nReply as the assistant.")
        text = (self.llm._generate(prompt, RAG_SYSTEM, 0.7).text or "").strip()
        valid = {r["id"] for r in rows}
        cited = [int(i) for i in dict.fromkeys(re.findall(r"\[#(\d+)\]", text)) if int(i) in valid]
        text = re.sub(r"\s*\[#\d+\]", "", text).strip()
        self.history.append(f"Assistant: {text}")
        return Turn("assistant", text, cited, "cited" if cited else "")


SYSTEMS = {"agent": AgentSystem, "plain": PlainSystem, "rag": RagSystem}
