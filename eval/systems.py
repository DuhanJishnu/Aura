"""Evaluation systems: Plain baseline vs Google ADK AI Stylist (live or offline)."""
from __future__ import annotations

from typing import Protocol

from app import config
from app.service import StylistService
from stylist_agent.memory import PreferenceStore, apply_swipe
from stylist_agent.offline import OfflineStylistService
from stylist_agent.schemas import ChatRequest, ChatResponse, FashionItem, StyleDNA


class EvalSystem(Protocol):
    name: str

    async def setup_swipes(self, likes: list[dict], dislikes: list[dict]) -> None: ...
    async def turn(self, message: str) -> ChatResponse: ...


class AdkStylistEvalSystem:
    def __init__(self, user_id: str, offline: bool = False):
        self.name = "adk_stylist_offline" if offline else "adk_stylist"
        self.user_id = user_id
        self.session_id = f"eval_{user_id}"
        self.store = PreferenceStore(persist=False)
        self.service: StylistService = (
            OfflineStylistService(store=self.store) if offline else StylistService(store=self.store)
        )

    async def setup_swipes(self, likes: list[dict], dislikes: list[dict]) -> None:
        dna = self.store.get(self.user_id)
        for raw in likes:
            apply_swipe(dna, FashionItem.model_validate(raw), "like")
        for raw in dislikes:
            apply_swipe(dna, FashionItem.model_validate(raw), "dislike")
        self.store.save(dna)

    async def turn(self, message: str) -> ChatResponse:
        return await self.service.chat(
            ChatRequest(session_id=self.session_id, user_id=self.user_id, message=message)
        )


class PlainPromptBaseline:
    """No-tools, no-search, no-swipe-memory baseline for comparing against ADK Stylist."""

    name = "plain_baseline"

    def __init__(self, user_id: str, offline: bool = False):
        self.user_id = user_id
        self.offline = offline
        self.history: list[str] = []

    async def setup_swipes(self, likes: list[dict], dislikes: list[dict]) -> None:
        return None  # plain prompt has no swipe memory

    async def turn(self, message: str) -> ChatResponse:
        self.history.append(f"User: {message}")
        if self.offline:
            reply = "Here is a general response to your question."
        else:
            from google import genai

            client = genai.Client(api_key=config.GEMINI_API_KEY)
            resp = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents="\n".join(self.history),
            )
            reply = (resp.text or "").strip()
        self.history.append(f"Assistant: {reply}")
        return ChatResponse(reply=reply, style_dna=StyleDNA(user_id=self.user_id))
