from __future__ import annotations

import base64
import binascii
import json
import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import config
from app.service import StylistService
from stylist_agent.db import get_db
from stylist_agent.media import get_media, verify_media_token
from stylist_agent.memory import item_key
from stylist_agent.schemas import (
    AnalyzeReq,
    ChatRequest,
    ChatResponse,
    ConfirmComplexionReq,
    LookSearchRequest,
    LookSwipeRequest,
    OutfitLook,
    PreferencesUpdateReq,
    ProfileSyncReq,
    SessionReq,
    StyleDNA,
    SwipeRequest,
    SwipeResponse,
    TranscribeReq,
)
from stylist_agent.tools import search_looks_deck, stream_looks_deck

log = logging.getLogger("shopper.api")

_hits: dict[str, list[float]] = {}
_service: StylistService | None = None


def get_service() -> StylistService:
    global _service
    if _service is None:
        _service = StylistService()
    return _service


def set_service(service: StylistService | None) -> None:
    """Allow tests and offline demo scripts to inject a custom StylistService."""
    global _service
    _service = service


def require_api_key() -> None:
    if _service is None and not config.GEMINI_API_KEY:
        raise HTTPException(503, "Set GEMINI_API_KEY (see .env.example).")
    if _service is not None and not config.GEMINI_API_KEY and getattr(_service, "requires_key", True):
        if not getattr(_service, "offline_mode", False):
            raise HTTPException(503, "Set GEMINI_API_KEY (see .env.example).")


def _extract_token(request: Request) -> str | None:
    hdr = request.headers.get("x-aura-token")
    if hdr:
        return hdr.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def verify_user_scope(request: Request, user_id: str) -> None:
    """Enforce per-user ownership token whenever a user_id is claimed or strict auth is enabled."""
    token = _extract_token(request)
    if not get_db().verify_user_token(user_id or "default", token, strict=config.STRICT_AUTH):
        raise HTTPException(403, "Invalid or missing user session token for this profile.")


def rate_limit(request: Request, user_id: str | None = None) -> None:
    limit = config.RATE_LIMIT_PER_MIN
    if limit <= 0:
        return
    if config.TRUST_PROXY:
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    else:
        ip = ""
    ip = ip or (request.client.host if request.client else "unknown")
    who = f"{ip}:{user_id}" if user_id else ip
    now = time.monotonic()
    recent = [x for x in _hits.get(who, []) if now - x < 60]
    if len(recent) >= limit:
        raise HTTPException(429, "Too many requests. Please slow down a little.")
    recent.append(now)
    _hits[who] = recent
    if len(_hits) > 10_000:
        for k in [k for k, v in _hits.items() if not v or now - v[-1] >= 60]:
            _hits.pop(k, None)


app = FastAPI(title="Shopper AI Stylist (Google ADK)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = rid
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Response-Time-Ms"] = f"{(time.perf_counter() - t0) * 1000:.1f}"
    return response


class AuthSessionReq(BaseModel):
    user_id: str = Field(default="default", min_length=1, max_length=120)


@app.post("/auth/session", dependencies=[Depends(rate_limit)])
def auth_session(req: AuthSessionReq, request: Request):
    """Issue a fresh session token bound to user_id (or verify existing token if already claimed)."""
    uid = req.user_id or "default"
    existing_token = _extract_token(request)
    if existing_token and get_db().verify_user_token(uid, existing_token, strict=False):
        return {"user_id": uid, "token": existing_token}
    # Only issue when unbound, OR rotate when existing token already verified
    if not get_db().verify_user_token(uid, existing_token, strict=False):
        raise HTTPException(403, "User ID is already bound to another session token.")
    token = get_db().issue_session_token(uid)
    return {"user_id": uid, "token": token}


@app.get("/")
def root():
    return {"name": "shopper-adk-stylist", "status": "running", "architecture": "google-adk"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/media/{media_id}")
def media(media_id: str, sig: str | None = Query(default=None), exp: str | None = Query(default=None)):
    if not verify_media_token(media_id, sig, exp):
        raise HTTPException(403, "Media URL signature invalid or expired")
    item = get_media(media_id)
    if item is None:
        raise HTTPException(404, "Image expired or not found")
    data, mime_type = item
    return Response(content=data, media_type=mime_type, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/ready")
def ready():
    svc = _service
    offline = bool(svc and getattr(svc, "offline_mode", False))
    return {
        "adk": True,
        "database": "sqlite",
        "llm_key": bool(config.GEMINI_API_KEY) or offline,
        "live_model": config.GEMINI_LIVE_MODEL,
        "fallback_model": config.GEMINI_MODEL_FALLBACK,
    }


@app.get("/metrics")
def metrics(request: Request):
    verify_user_scope(request, "default")
    return get_db().telemetry_summary()


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit), Depends(require_api_key)])
async def chat(req: ChatRequest, request: Request, svc: StylistService = Depends(get_service)) -> ChatResponse:  # noqa: B008
    verify_user_scope(request, req.user_id)
    rid = getattr(request.state, "request_id", None)
    return await svc.chat(req, request_id=rid)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat/stream", dependencies=[Depends(rate_limit), Depends(require_api_key)])
async def chat_stream(req: ChatRequest, request: Request, svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, req.user_id)
    rid = getattr(request.state, "request_id", None)

    async def generate():
        try:
            async for ev, payload in svc.stream_chat(req, request_id=rid):
                yield _sse(ev, payload)
        except Exception:
            log.exception("chat stream failed")
            yield _sse("error", {"message": "Something went wrong styling that request. Please try again."})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.websocket("/ws/live/{user_id}/{session_id}")
async def ws_live(websocket: WebSocket, user_id: str, session_id: str):
    token = websocket.query_params.get("token") or websocket.headers.get("x-aura-token")
    if not get_db().verify_user_token(user_id or "default", token, strict=config.STRICT_AUTH):
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Unauthorized live session token."})
        await websocket.close(code=1008)
        return
    if not config.GEMINI_API_KEY:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "GEMINI_API_KEY is not configured for Live voice."})
        await websocket.close(code=1008)
        return
    svc = get_service()
    await svc.run_live_ws(websocket, user_id=user_id, session_id=session_id)


@app.post("/swipe", response_model=SwipeResponse, dependencies=[Depends(rate_limit)])
def swipe(req: SwipeRequest, request: Request, svc: StylistService = Depends(get_service)) -> SwipeResponse:  # noqa: B008
    """Backwards-compatible alias delegating to unified idempotent swipe processor."""
    verify_user_scope(request, req.user_id)
    return svc.process_swipe(
        user_id=req.user_id,
        action=req.direction,
        item=req.item,
        idempotency_key=req.idempotency_key,
    )


@app.post("/swipes", response_model=SwipeResponse, dependencies=[Depends(rate_limit)])
def record_swipe_event(req: LookSwipeRequest, request: Request, svc: StylistService = Depends(get_service)) -> SwipeResponse:  # noqa: B008
    verify_user_scope(request, req.user_id)
    try:
        return svc.process_swipe(
            user_id=req.user_id,
            action=req.action,
            look=req.look,
            item=req.item,
            idempotency_key=req.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.get("/profile", response_model=StyleDNA, dependencies=[Depends(rate_limit)])
def get_profile(request: Request, user_id: str = "default", svc: StylistService = Depends(get_service)) -> StyleDNA:  # noqa: B008
    verify_user_scope(request, user_id)
    return svc.store.get(user_id)


@app.post("/profile/sync", response_model=StyleDNA, dependencies=[Depends(rate_limit)])
def sync_profile(req: ProfileSyncReq, request: Request, svc: StylistService = Depends(get_service)) -> StyleDNA:  # noqa: B008
    verify_user_scope(request, req.user_id)
    return svc.store.sync_from_client(req.user_id, req.style_dna)


@app.post("/profile/forget", dependencies=[Depends(rate_limit)])
async def forget_profile(req: SessionReq, request: Request, svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, req.user_id)
    fresh = await svc.forget_all_user_data(req.user_id, req.session_id)
    return {
        "message": "Done — I've cleared your Style DNA, saved closet, swipes, session memory, and complexion notes.",
        "style_dna": fresh,
    }


@app.delete("/closet/{item_id}", response_model=StyleDNA, dependencies=[Depends(rate_limit)])
def remove_from_closet(
    item_id: str,
    request: Request,
    user_id: str = "default",
    svc: StylistService = Depends(get_service),  # noqa: B008
) -> StyleDNA:
    verify_user_scope(request, user_id)
    dna = svc.store.get(user_id)
    dna.saved_closet = [i for i in dna.saved_closet if i.id != item_id and item_key(i) != item_id]
    return svc.store.save(dna)


@app.post("/outfit/save", response_model=StyleDNA, dependencies=[Depends(rate_limit)])
def save_outfit(outfit: OutfitLook, request: Request, user_id: str = "default", svc: StylistService = Depends(get_service)) -> StyleDNA:  # noqa: B008
    verify_user_scope(request, user_id)
    return svc.store.save_outfit(user_id, outfit)


@app.post("/looks/search", dependencies=[Depends(rate_limit), Depends(require_api_key)])
async def looks_search(req: LookSearchRequest, request: Request, svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, req.user_id)
    dna = await svc.ensure_session(req.user_id, req.session_id, req.style_dna)
    looks = await search_looks_deck(
        occasion=req.occasion,
        dna=dna,
        vibe=req.vibe,
        anchor_item=req.anchor_item,
        max_budget_inr=req.budget_inr,
        exclude_look_ids=req.exclude_look_ids,
    )
    return {"looks": [lk.model_dump() for lk in looks], "style_dna": dna.model_dump()}


@app.post("/looks/search/stream", dependencies=[Depends(rate_limit), Depends(require_api_key)])
async def looks_search_stream(req: LookSearchRequest, request: Request, svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, req.user_id)
    dna = await svc.ensure_session(req.user_id, req.session_id, req.style_dna)

    async def generate():
        streamed: list[dict] = []
        try:
            yield _sse("status", {"state": "searching"})
            async for lk in stream_looks_deck(
                occasion=req.occasion,
                dna=dna,
                vibe=req.vibe,
                anchor_item=req.anchor_item,
                max_budget_inr=req.budget_inr,
                exclude_look_ids=req.exclude_look_ids,
            ):
                dumped = lk.model_dump()
                streamed.append(dumped)
                yield _sse("look", {"look": dumped})
            yield _sse("done", {"looks": streamed, "style_dna": dna.model_dump()})
        except Exception:
            log.exception("looks search stream failed")
            yield _sse("error", {"message": "Could not load fresh looks right now."})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/wishlist", dependencies=[Depends(rate_limit)])
def get_wishlist(request: Request, user_id: str = "default", svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, user_id)
    dna = svc.store.get(user_id)
    return {"wishlist": [lk.model_dump() for lk in dna.saved_outfits], "style_dna": dna.model_dump()}


@app.delete("/wishlist/{look_id}", response_model=StyleDNA, dependencies=[Depends(rate_limit)])
def remove_from_wishlist(look_id: str, request: Request, user_id: str = "default", svc: StylistService = Depends(get_service)) -> StyleDNA:  # noqa: B008
    verify_user_scope(request, user_id)
    return svc.store.remove_outfit(user_id, look_id)


@app.get("/preferences", response_model=StyleDNA, dependencies=[Depends(rate_limit)])
def get_preferences(request: Request, user_id: str = "default", svc: StylistService = Depends(get_service)) -> StyleDNA:  # noqa: B008
    verify_user_scope(request, user_id)
    return svc.store.get(user_id)


@app.put("/preferences", response_model=StyleDNA, dependencies=[Depends(rate_limit)])
def update_preferences(req: PreferencesUpdateReq, request: Request, svc: StylistService = Depends(get_service)) -> StyleDNA:  # noqa: B008
    verify_user_scope(request, req.user_id)
    dna = svc.store.get(req.user_id)
    if req.tutorial_seen is not None:
        dna.tutorial_seen = req.tutorial_seen
    if req.fit_preference is not None:
        dna.fit_preference = req.fit_preference
    if req.budget_max is not None:
        dna.budget_max = req.budget_max
    if req.sizes is not None:
        dna.sizes.update(req.sizes)
    if req.liked_colors is not None:
        dna.liked_colors = list(dict.fromkeys([c.strip().lower() for c in req.liked_colors if c.strip()]))
    return svc.store.save(dna)


# ---------- Consent-first Photo Studio (photos are NEVER stored) ----------

ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _decode_image(req: AnalyzeReq) -> bytes:
    if req.mime_type not in ALLOWED_IMAGES:
        raise HTTPException(400, "Please upload a JPEG, PNG or WebP image.")
    if len(req.image_base64) > MAX_IMAGE_BYTES * 4 // 3 + 16:
        raise HTTPException(413, "That image is too large (5 MB max).")
    try:
        return base64.b64decode(req.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "That doesn't look like a valid image.") from None


@app.post("/complexion/consent", dependencies=[Depends(rate_limit)])
def complexion_consent(req: SessionReq, request: Request, svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, req.user_id)
    ps = svc.photo_state(req.session_id)
    ps["consent"] = True
    return {"ok": True, "retention_policy": "zero_retention_ram_only"}


@app.post("/complexion/analyze", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def complexion_analyze(req: AnalyzeReq, request: Request, svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, req.user_id)
    ps = svc.photo_state(req.session_id)
    if not ps.get("consent"):
        raise HTTPException(403, "Photo analysis needs your consent first.")
    ps["consent"] = False
    data = _decode_image(req)
    try:
        estimate = svc.vision.analyze_complexion(data, req.mime_type)
    except Exception:
        raise HTTPException(502, "I couldn't analyse that photo. You can also just tell me your undertone.") from None
    finally:
        del data
    ps["pending_estimate"] = estimate.model_dump()
    return {"estimate": ps["pending_estimate"], "retention_policy": "zero_retention_discarded"}


@app.post("/complexion/confirm", dependencies=[Depends(rate_limit)])
def complexion_confirm(req: ConfirmComplexionReq, request: Request, svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, req.user_id)
    ps = svc.photo_state(req.session_id)
    if ps.get("pending_estimate") is None:
        raise HTTPException(409, "There is no estimate to confirm. Upload a photo first, or tell me your undertone.")
    message, dna = svc.confirm_complexion(
        user_id=req.user_id,
        session_id=req.session_id,
        skin_tone=req.skin_tone,
        undertone=req.undertone,
        color_season=req.color_season,
    )
    return {"message": message, "style_dna": dna}


@app.post("/complexion/cancel", dependencies=[Depends(rate_limit)])
def complexion_cancel(req: SessionReq, request: Request, svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, req.user_id)
    ps = svc.photo_state(req.session_id)
    ps["consent"] = False
    ps["pending_estimate"] = None
    return {"ok": True}


@app.post("/outfit-check/analyze", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def outfit_check_analyze(req: AnalyzeReq, request: Request, svc: StylistService = Depends(get_service)):  # noqa: B008
    verify_user_scope(request, req.user_id)
    ps = svc.photo_state(req.session_id)
    if not ps.get("consent"):
        raise HTTPException(403, "Photo analysis needs your consent first.")
    ps["consent"] = False
    data = _decode_image(req)
    try:
        result = svc.vision.analyze_outfit(data, req.mime_type, req.note)
    except Exception:
        raise HTTPException(502, "I couldn't analyse that outfit photo right now. Describe your outfit in chat instead!") from None
    finally:
        del data
    return {"result": result, "retention_policy": "zero_retention_discarded"}


ALLOWED_AUDIO = {"audio/webm", "audio/mp4", "audio/ogg", "audio/wav", "audio/mpeg"}


@app.post("/voice/transcribe", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def voice_transcribe(req: TranscribeReq, svc: StylistService = Depends(get_service)):  # noqa: B008
    base_mime = req.mime_type.split(";")[0].strip().lower()
    if base_mime not in ALLOWED_AUDIO:
        raise HTTPException(400, "Unsupported audio format.")
    if len(req.audio_base64) > MAX_IMAGE_BYTES * 4 // 3 + 16:
        raise HTTPException(413, "Audio clip is too large (5 MB max).")
    try:
        data = base64.b64decode(req.audio_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "Invalid audio encoding.") from None
    try:
        text = svc.vision.transcribe_audio(data, base_mime)
    except Exception:
        raise HTTPException(502, "Could not transcribe voice note right now.") from None
    finally:
        del data
    return {"text": text}
