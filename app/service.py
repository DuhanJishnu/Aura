"""FastAPI <-> Google ADK service bridge (chat, SSE streaming, Gemini Live BIDI voice, and consent-first vision)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, Protocol

from fastapi import WebSocket, WebSocketDisconnect
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types

from app import config
from stylist_agent.agent import build_stylist_agent, create_runner
from stylist_agent.db import SqliteSessionService, get_db
from stylist_agent.media import purge_user_media
from stylist_agent.memory import (
    PreferenceStore,
    apply_look_swipe,
    apply_swipe,
    infer_season,
    summarize_dna_for_prompt,
)
from stylist_agent.prompts import COMPLEXION_SYSTEM, OUTFIT_CHECK_SYSTEM
from stylist_agent.schemas import (
    ChatRequest,
    ChatResponse,
    ComplexionEstimate,
    FashionItem,
    OutfitCheckResult,
    OutfitLook,
    StyleDNA,
    SwipeResponse,
    UIAction,
)
from stylist_agent.tools import get_store

log = logging.getLogger("shopper.service")


def _estimate_cost_usd(in_tok: int, out_tok: int) -> float:
    # Approximate Flash pricing ($0.15 / 1M input, $0.60 / 1M output)
    return round((in_tok * 0.15 + out_tok * 0.60) / 1_000_000.0, 6)


class VisionBackend(Protocol):
    def analyze_complexion(self, image: bytes, mime_type: str) -> ComplexionEstimate: ...
    def analyze_outfit(self, image: bytes, mime_type: str, note: str = "") -> OutfitCheckResult: ...
    def transcribe_audio(self, audio: bytes, mime_type: str) -> str: ...


class GeminiVisionBackend:
    """Stateless Gemini Vision & Audio helper with model fallback (media never touches disk)."""

    def __init__(self, model: str | None = None):
        self.model = model or config.GEMINI_MODEL
        self._client = None

    def _client_inst(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
        return self._client

    def _models(self) -> list[str]:
        return list(dict.fromkeys([self.model, config.GEMINI_MODEL_FALLBACK]))

    def analyze_complexion(self, image: bytes, mime_type: str) -> ComplexionEstimate:
        part = types.Part.from_bytes(data=image, mime_type=mime_type)
        last_exc: Exception | None = None
        for model_name in self._models():
            try:
                resp = self._client_inst().models.generate_content(
                    model=model_name,
                    contents=[part, "Estimate skin tone, undertone, and seasonal color palette."],
                    config=types.GenerateContentConfig(
                        system_instruction=COMPLEXION_SYSTEM,
                        temperature=0.0,
                        response_mime_type="application/json",
                        response_schema=ComplexionEstimate,
                    ),
                )
                parsed = getattr(resp, "parsed", None)
                return (
                    parsed
                    if isinstance(parsed, ComplexionEstimate)
                    else ComplexionEstimate.model_validate_json(resp.text)
                )
            except Exception as exc:
                last_exc = exc
        raise last_exc or RuntimeError("Complexion analysis failed")

    def analyze_outfit(self, image: bytes, mime_type: str, note: str = "") -> OutfitCheckResult:
        part = types.Part.from_bytes(data=image, mime_type=mime_type)
        prompt = "Give an honest, supportive best-friend outfit check and styling elevation tips."
        if note:
            prompt += f" User note: {note}"
        last_exc: Exception | None = None
        for model_name in self._models():
            try:
                resp = self._client_inst().models.generate_content(
                    model=model_name,
                    contents=[part, prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=OUTFIT_CHECK_SYSTEM,
                        temperature=0.4,
                        response_mime_type="application/json",
                        response_schema=OutfitCheckResult,
                    ),
                )
                parsed = getattr(resp, "parsed", None)
                return (
                    parsed
                    if isinstance(parsed, OutfitCheckResult)
                    else OutfitCheckResult.model_validate_json(resp.text)
                )
            except Exception as exc:
                last_exc = exc
        raise last_exc or RuntimeError("Outfit check analysis failed")

    def transcribe_audio(self, audio: bytes, mime_type: str) -> str:
        part = types.Part.from_bytes(data=audio, mime_type=mime_type)
        last_exc: Exception | None = None
        for model_name in self._models():
            try:
                resp = self._client_inst().models.generate_content(
                    model=model_name,
                    contents=[
                        part,
                        "Transcribe the user's spoken words accurately as plain text. If silent or unintelligible, return empty string.",
                    ],
                    config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=200),
                )
                return (resp.text or "").strip()
            except Exception as exc:
                last_exc = exc
        raise last_exc or RuntimeError("Audio transcription failed")


class StylistService:
    """Coordinates ADK Runner, persistent SessionService, MemoryService, and SQLite PreferenceStore."""

    def __init__(
        self,
        runner: Runner | None = None,
        session_service: BaseSessionService | None = None,
        memory_service: InMemoryMemoryService | None = None,
        store: PreferenceStore | None = None,
        vision: VisionBackend | None = None,
    ):
        if runner is None:
            runner, ss, ms = create_runner(
                session_service=session_service or SqliteSessionService(),
                memory_service=memory_service,
            )
            self.runner = runner
            self.session_service = ss
            self.memory_service = ms
        else:
            self.runner = runner
            self.session_service = session_service or runner.session_service
            self.memory_service = memory_service or InMemoryMemoryService()

        self.store = store or get_store()
        self.vision: VisionBackend = vision or GeminiVisionBackend()
        self._locks: dict[str, asyncio.Lock] = {}
        # Transient consent & pending photo estimate flags (never stores raw image bytes)
        self._photo_state: dict[str, dict[str, Any]] = {}

    def _lock_for(self, session_id: str) -> asyncio.Lock:
        lock = self._locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock
        return lock

    def photo_state(self, session_id: str) -> dict[str, Any]:
        return self._photo_state.setdefault(session_id, {"consent": False, "pending_estimate": None})

    async def ensure_session(self, user_id: str, session_id: str, client_dna: StyleDNA | None = None) -> StyleDNA:
        """Authoritative server StyleDNA check; only bootstraps empty profiles if client_dna is provided."""
        if client_dna is not None:
            dna = self.store.sync_from_client(user_id, client_dna)
        else:
            dna = self.store.get(user_id)

        existing = await self.session_service.get_session(
            app_name=config.APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        initial_state = {
            "user_id": user_id,
            "style_dna": dna.model_dump(),
            "style_dna_summary": summarize_dna_for_prompt(dna),
            "ui_action": UIAction().model_dump(),
        }
        if existing is None:
            await self.session_service.create_session(
                app_name=config.APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state=initial_state,
            )
        else:
            existing.state["user_id"] = user_id
            existing.state["style_dna"] = dna.model_dump()
            existing.state["style_dna_summary"] = summarize_dna_for_prompt(dna)
        return dna

    async def forget_all_user_data(self, user_id: str, session_id: str = "") -> StyleDNA:
        """Cascading forget across SQLite profile/swipes/media, ADK sessions, and transient photo flags."""
        fresh = self.store.forget(user_id)
        purge_user_media(user_id)
        if hasattr(self.session_service, "delete_user_sessions"):
            try:
                await self.session_service.delete_user_sessions(user_id)  # type: ignore[attr-defined]
            except Exception:
                pass
        if session_id:
            self._photo_state.pop(session_id, None)
        return fresh

    def process_swipe(
        self,
        *,
        user_id: str,
        action: str,
        look: OutfitLook | None = None,
        item: FashionItem | None = None,
        idempotency_key: str | None = None,
    ) -> SwipeResponse:
        """Unified, idempotent swipe & undo handler for both items and complete looks."""
        db = get_db()
        if idempotency_key:
            cached = db.get_idempotent_swipe(user_id, idempotency_key)
            if cached is not None:
                try:
                    return SwipeResponse.model_validate(cached)
                except Exception:
                    pass

        dna = self.store.get(user_id)
        if action == "undo":
            reaction = apply_look_swipe(dna, look or OutfitLook(id="undo", title="Undo", occasion="", vibe="", color_story="", proportion_tip=""), "undo")
        elif look is not None:
            norm_action = "save" if action == "like" else ("skip" if action == "dislike" else ("buy_intent" if action == "super_like" else action))
            reaction = apply_look_swipe(dna, look, norm_action)
        elif item is not None:
            norm_dir = (
                "like"
                if action in ("like", "save")
                else ("super_like" if action in ("super_like", "buy_intent") else "dislike")
            )
            reaction = apply_swipe(dna, item, norm_dir)
        else:
            raise ValueError("Provide either `look` or `item` to record a swipe event.")

        saved = self.store.save(dna)
        liked = sum(1 for s in saved.swipe_history if s.direction in ("like", "super_like"))
        passed = sum(1 for s in saved.swipe_history if s.direction == "dislike")
        resp = SwipeResponse(
            style_dna=saved,
            reaction=reaction,
            stats={
                "liked": liked,
                "passed": passed,
                "closet": len(saved.saved_closet),
                "wishlist": len(saved.saved_outfits),
            },
        )
        if idempotency_key:
            db.record_idempotent_swipe(user_id, idempotency_key, action, resp.model_dump())
        return resp

    async def _build_user_message(self, req: ChatRequest, user_id: str, session_id: str) -> types.Content:
        text = req.message.strip()
        if req.focus_item_id:
            session = await self.session_service.get_session(
                app_name=config.APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
            cards = (session.state.get("current_cards") if session else None) or []
            focused = next((c for c in cards if c.get("id") == req.focus_item_id), None)
            if focused:
                text = f"[Focused item: {focused.get('name')} by {focused.get('brand')}, {focused.get('color')}, {focused.get('price_text')}]\n{text}"
        return types.Content(role="user", parts=[types.Part.from_text(text=text)])

    async def _read_turn_outputs(self, user_id: str, session_id: str) -> tuple[UIAction, StyleDNA]:
        session = await self.session_service.get_session(
            app_name=config.APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        raw_ui = (session.state.get("ui_action") if session else None) or {}
        try:
            ui = UIAction.model_validate(raw_ui)
        except Exception:
            ui = UIAction()
        dna = self.store.get(user_id)
        return ui, dna

    def _record_turn_telemetry(
        self,
        *,
        request_id: str,
        user_id: str,
        session_id: str,
        duration_ms: float,
        tools_used: list[str],
        in_tokens: int,
        out_tokens: int,
    ) -> dict[str, Any]:
        cost = _estimate_cost_usd(in_tokens, out_tokens)
        try:
            get_db().record_telemetry(
                request_id=request_id,
                user_id=user_id,
                session_id=session_id,
                event_type="chat_turn",
                name="adk_runner",
                duration_ms=duration_ms,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                estimated_cost_usd=cost,
                meta={"tools_used": tools_used},
            )
        except Exception:
            pass
        return {
            "request_id": request_id,
            "duration_ms": round(duration_ms, 1),
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "estimated_cost_usd": cost,
        }

    async def chat(self, req: ChatRequest, request_id: str | None = None) -> ChatResponse:
        rid = request_id or uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        async with self._lock_for(req.session_id):
            await self.ensure_session(req.user_id, req.session_id, req.style_dna)
            msg = await self._build_user_message(req, req.user_id, req.session_id)

            final_text_parts: list[str] = []
            tools_used: list[str] = []
            in_tok = 0
            out_tok = 0

            async for event in self.runner.run_async(
                user_id=req.user_id,
                session_id=req.session_id,
                new_message=msg,
            ):
                usage = getattr(event, "usage_metadata", None)
                if usage:
                    in_tok += int(getattr(usage, "prompt_token_count", 0) or 0)
                    out_tok += int(getattr(usage, "candidates_token_count", 0) or 0)
                for fc in event.get_function_calls() if hasattr(event, "get_function_calls") else []:
                    if getattr(fc, "name", None):
                        tools_used.append(fc.name)
                if event.content and event.content.parts and event.is_final_response():
                    for part in event.content.parts:
                        if part.text:
                            final_text_parts.append(part.text)

            ui, dna = await self._read_turn_outputs(req.user_id, req.session_id)
            session = await self.session_service.get_session(
                app_name=config.APP_NAME, user_id=req.user_id, session_id=req.session_id
            )
            if session is not None and hasattr(self.memory_service, "add_session_to_memory"):
                try:
                    await self.memory_service.add_session_to_memory(session)
                except Exception:
                    pass

            dedup_tools = list(dict.fromkeys(tools_used))
            telemetry = self._record_turn_telemetry(
                request_id=rid,
                user_id=req.user_id,
                session_id=req.session_id,
                duration_ms=(time.perf_counter() - t0) * 1000,
                tools_used=dedup_tools,
                in_tokens=in_tok,
                out_tokens=out_tok,
            )
            reply = "".join(final_text_parts).strip() or "I'm here! Tell me what vibe or piece we're styling today."
            return ChatResponse(
                reply=reply,
                ui_action=ui,
                style_dna=dna,
                tools_used=dedup_tools,
                telemetry=telemetry,
            )

    async def stream_chat(self, req: ChatRequest, request_id: str | None = None) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Yields SSE tuples: ('status', ...), ('ui', ...), ('text', ...), ('done', ...)."""
        rid = request_id or uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        async with self._lock_for(req.session_id):
            await self.ensure_session(req.user_id, req.session_id, req.style_dna)
            msg = await self._build_user_message(req, req.user_id, req.session_id)
            yield ("status", {"state": "thinking", "request_id": rid})

            ui_sent = False
            tools_used: list[str] = []
            final_text_parts: list[str] = []
            in_tok = 0
            out_tok = 0

            async for event in self.runner.run_async(
                user_id=req.user_id,
                session_id=req.session_id,
                new_message=msg,
            ):
                usage = getattr(event, "usage_metadata", None)
                if usage:
                    in_tok += int(getattr(usage, "prompt_token_count", 0) or 0)
                    out_tok += int(getattr(usage, "candidates_token_count", 0) or 0)
                for fc in event.get_function_calls() if hasattr(event, "get_function_calls") else []:
                    if getattr(fc, "name", None):
                        tools_used.append(fc.name)

                if not ui_sent and hasattr(event, "get_function_responses") and event.get_function_responses():
                    ui, dna = await self._read_turn_outputs(req.user_id, req.session_id)
                    if ui.type != "none":
                        ui_sent = True
                        yield ("ui", {"ui_action": ui.model_dump(), "style_dna": dna.model_dump()})

                if event.content and event.content.parts and event.is_final_response():
                    for part in event.content.parts:
                        if part.text:
                            final_text_parts.append(part.text)

            ui, dna = await self._read_turn_outputs(req.user_id, req.session_id)
            if not ui_sent and ui.type != "none":
                yield ("ui", {"ui_action": ui.model_dump(), "style_dna": dna.model_dump()})

            reply = "".join(final_text_parts).strip() or "I'm here! Tell me what vibe or piece we're styling today."
            words = reply.split(" ")
            for i in range(0, len(words), 4):
                piece = " ".join(words[i : i + 4]) + (" " if i + 4 < len(words) else "")
                yield ("text", {"delta": piece})

            dedup_tools = list(dict.fromkeys(tools_used))
            telemetry = self._record_turn_telemetry(
                request_id=rid,
                user_id=req.user_id,
                session_id=req.session_id,
                duration_ms=(time.perf_counter() - t0) * 1000,
                tools_used=dedup_tools,
                in_tokens=in_tok,
                out_tokens=out_tok,
            )
            resp = ChatResponse(
                reply=reply,
                ui_action=ui,
                style_dna=dna,
                tools_used=dedup_tools,
                telemetry=telemetry,
            )
            yield ("done", resp.model_dump())

    async def run_live_ws(self, websocket: WebSocket, user_id: str, session_id: str) -> None:
        """Full-duplex Gemini Live BIDI voice + UI session with duration cap, fallback model, and UI confirm gates."""
        await websocket.accept()
        await self.ensure_session(user_id, session_id)

        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=config.GEMINI_LIVE_VOICE)
                )
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
        live_queue = LiveRequestQueue()
        started_at = time.monotonic()

        async def upstream() -> None:
            try:
                while True:
                    if time.monotonic() - started_at > config.LIVE_WS_MAX_SECONDS:
                        await websocket.send_json({"type": "error", "message": "Live voice session reached its time limit. Reconnecting or tap Live again anytime."})
                        await websocket.close(code=1000)
                        break
                    packet = await websocket.receive()
                    if packet.get("type") == "websocket.disconnect":
                        break
                    if packet.get("bytes") is not None:
                        live_queue.send_realtime(
                            types.Blob(data=packet["bytes"], mime_type="audio/pcm;rate=16000")
                        )
                    elif packet.get("text") is not None:
                        try:
                            payload = json.loads(packet["text"])
                        except Exception:
                            payload = {"type": "text", "text": packet["text"]}
                        ptype = payload.get("type")
                        if ptype == "ping":
                            await websocket.send_json({"type": "pong"})
                        elif ptype == "text" and payload.get("text"):
                            live_queue.send_content(
                                types.Content(
                                    role="user",
                                    parts=[types.Part.from_text(text=str(payload["text"]))],
                                )
                            )
            except WebSocketDisconnect:
                pass
            except Exception as exc:
                log.debug("Live WS upstream ended: %s", exc)
            finally:
                live_queue.close()

        async def downstream() -> None:
            last_ui_sig = ""
            for model_name in dict.fromkeys([config.GEMINI_LIVE_MODEL, config.GEMINI_LIVE_MODEL_FALLBACK]):
                try:
                    live_agent = build_stylist_agent(model=model_name)
                    live_runner, _, _ = create_runner(
                        agent=live_agent,
                        session_service=self.session_service,
                        memory_service=self.memory_service,
                    )
                    async for event in live_runner.run_live(
                        user_id=user_id,
                        session_id=session_id,
                        live_request_queue=live_queue,
                        run_config=run_config,
                    ):
                        if time.monotonic() - started_at > config.LIVE_WS_MAX_SECONDS:
                            break
                        if getattr(event, "interrupted", False):
                            await websocket.send_json({"type": "interrupted"})
                        if getattr(event, "input_transcription", None) and event.input_transcription.text:
                            await websocket.send_json(
                                {"type": "input_transcript", "text": event.input_transcription.text}
                            )
                        if getattr(event, "output_transcription", None) and event.output_transcription.text:
                            await websocket.send_json(
                                {"type": "output_transcript", "text": event.output_transcription.text}
                            )
                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                inline = getattr(part, "inline_data", None)
                                if inline and getattr(inline, "data", None) and str(inline.mime_type or "").startswith("audio/"):
                                    await websocket.send_bytes(inline.data)
                        ui, dna = await self._read_turn_outputs(user_id, session_id)
                        sig = ui.model_dump_json()
                        if ui.type != "none" and sig != last_ui_sig:
                            last_ui_sig = sig
                            await websocket.send_json(
                                {"type": "ui", "ui_action": ui.model_dump(), "style_dna": dna.model_dump()}
                            )
                        if getattr(event, "turn_complete", False):
                            await websocket.send_json({"type": "turn_complete"})
                    return
                except WebSocketDisconnect:
                    return
                except Exception as exc:
                    log.warning("Gemini Live session error on %s: %s", model_name, exc)
                    continue
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Gemini Live voice encountered an error. You can switch to standard Mic/Chat anytime.",
                    }
                )
            except Exception:
                pass

        await asyncio.gather(upstream(), downstream(), return_exceptions=True)

    def confirm_complexion(
        self,
        user_id: str,
        session_id: str,
        skin_tone: str,
        undertone: str,
        color_season: str | None = None,
    ) -> tuple[str, StyleDNA]:
        from stylist_agent.memory import UNDERTONE_PALETTES, _upsert_fact

        dna = self.store.get(user_id)
        dna.skin_tone = skin_tone
        dna.undertone = undertone
        dna.color_season = color_season or infer_season(skin_tone, undertone)
        _upsert_fact(dna, "skin_tone", skin_tone, "confirmed", singleton=True)
        _upsert_fact(dna, "undertone", undertone, "confirmed", singleton=True)
        if dna.color_season:
            _upsert_fact(dna, "color_season", dna.color_season, "confirmed", singleton=True)
        saved = self.store.save(dna)
        self.photo_state(session_id)["pending_estimate"] = None
        best = ", ".join(UNDERTONE_PALETTES.get(undertone, {}).get("best", [])[:5])
        msg = (
            f"Saved your {skin_tone} / {undertone} undertone ({dna.color_season} palette)! "
            f"Colors like {best} will naturally make your complexion glow — I'll prioritize them in your Swipe Deck and outfits."
        )
        return msg, saved


# Helper to construct FashionItem safely from tests
def make_item(**kwargs: Any) -> FashionItem:
    return FashionItem(**kwargs)
