"""Google ADK root agent definition for the AI Fashion Stylist.

Follows official Google ADK package layout (`stylist_agent/agent.py` exposing `root_agent`)
so `adk web`, `adk run`, `adk eval`, and the FastAPI server all share the exact same agent graph.
"""
from __future__ import annotations

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.adk.tools import FunctionTool

from app import config
from stylist_agent.db import SqliteSessionService
from stylist_agent.memory import summarize_dna_for_prompt
from stylist_agent.prompts import STYLIST_ORCHESTRATOR_INSTRUCTION
from stylist_agent.tools import (
    compare_fashion_items,
    curate_outfit,
    forget_style_profile,
    get_store,
    get_style_profile_and_closet,
    record_style_preference,
    search_fashion_online,
    set_shopping_boundary,
    trigger_photo_stylist,
)


def _sync_style_state(callback_context: CallbackContext) -> None:
    """Ensure session state always reflects the user's latest Style DNA and swipe history."""
    state = callback_context.state
    user_id = str(state.get("user_id") or getattr(callback_context, "user_id", None) or "default")
    state["user_id"] = user_id
    dna = get_store().get(user_id)
    state["style_dna"] = dna.model_dump()
    state["style_dna_summary"] = summarize_dna_for_prompt(dna)
    # Reset per-turn ui_action before the agent runs tools
    state["ui_action"] = {"type": "none", "items": [], "outfit": None, "focus_item": None, "photo_mode": None}


def build_stylist_agent(model: str | None = None) -> Agent:
    """Construct the ADK root stylist agent with trimmed, sharp toolset."""
    instruction = STYLIST_ORCHESTRATOR_INSTRUCTION.replace("{style_dna_summary}", "{style_dna_summary?}")
    return Agent(
        name="aura_stylist",
        model=model or config.GEMINI_MODEL,
        description=(
            "Aura: an expert AI personal fashion stylist and supportive friend who searches real buyable "
            "items online, curates head-to-toe outfits, learns from Tinder-style swipes, and gently "
            "circles casual conversations back to fashion."
        ),
        instruction=instruction,
        before_agent_callback=_sync_style_state,
        tools=[
            FunctionTool(func=search_fashion_online),
            FunctionTool(func=curate_outfit),
            FunctionTool(func=record_style_preference),
            FunctionTool(func=get_style_profile_and_closet),
            FunctionTool(func=compare_fashion_items),
            FunctionTool(func=trigger_photo_stylist),
            FunctionTool(func=forget_style_profile),
            FunctionTool(func=set_shopping_boundary),
        ],
    )


root_agent = build_stylist_agent()


def create_runner(
    agent: Agent | None = None,
    session_service: BaseSessionService | None = None,
    memory_service: InMemoryMemoryService | None = None,
    app_name: str = config.APP_NAME,
) -> tuple[Runner, BaseSessionService, InMemoryMemoryService]:
    """Create a configured ADK Runner backed by SQLite sessions by default."""
    ss = session_service or SqliteSessionService()
    ms = memory_service or InMemoryMemoryService()
    runner = Runner(
        agent=agent or root_agent,
        app_name=app_name,
        session_service=ss,
        memory_service=ms,
    )
    return runner, ss, ms
