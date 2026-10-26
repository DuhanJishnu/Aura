import base64
import binascii
import json
import logging
import os
import queue
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.catalog.db import DB_PATH, connect, init_db
from app.catalog.search import get_shoe, get_shoes_by_ids, search_shoes
from app.engine import cart, profile_flow
from app.engine.engine import handle
from app.engine.state import get_session
from app.llm.client import LLM, GeminiLLM
from app.schemas import (
    AnalyzeReq,
    CartAdd,
    CartRemove,
    ChatRequest,
    ChatResponse,
    CheckoutReq,
    ConfirmComplexionReq,
    SessionReq,
)

log = logging.getLogger("shopper")

# Anyone with the URL can spend your Gemini quota: cap requests per client per minute (0 turns it off).
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
_hits: dict[str, list[float]] = {}


def rate_limit(request: Request) -> None:
    if RATE_LIMIT <= 0:
        return
    if os.getenv("TRUST_PROXY") == "1":  # behind a load balancer the real client is in X-Forwarded-For
        who = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    else:
        who = ""
    who = who or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    recent = [x for x in _hits.get(who, []) if now - x < 60]
    if len(recent) >= RATE_LIMIT:
        raise HTTPException(429, "Too many requests. Please slow down a little.")
    recent.append(now)
    _hits[who] = recent
    if len(_hits) > 10_000:  # keep the table small
        for k in [k for k, v in _hits.items() if not v or now - v[-1] >= 60]:
            _hits.pop(k, None)


@asynccontextmanager
async def lifespan(_app):
    if os.getenv("AUTO_SEED") == "1" and not DB_PATH.exists():  # first start in a fresh container
        from data.seed import seed
        seed()
    yield


app = FastAPI(title="Shopper", lifespan=lifespan)
_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        if not os.getenv("GEMINI_API_KEY"):
            raise HTTPException(503, "Set GEMINI_API_KEY (see .env.example).")
        _llm = GeminiLLM()
    return _llm


def get_conn():
    if not DB_PATH.exists():
        raise HTTPException(503, "Catalog missing. Run: python -m data.seed")
    conn = connect()
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/ready")
def ready():
    """Deploy check: the process is up, the catalog exists and an LLM key is configured."""
    return {"catalog": DB_PATH.exists(), "llm_key": bool(os.getenv("GEMINI_API_KEY"))}


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit)])
def chat(req: ChatRequest, llm: LLM = Depends(get_llm), conn=Depends(get_conn)) -> ChatResponse:  # noqa: B008
    session = get_session(req.session_id, req.user_id, conn)
    with session.lock:  # one turn at a time per conversation
        return handle(session, req.message, llm, conn, focus_id=req.focus_product_id)


@contextmanager
def _open_conn():
    conn = connect()
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


def get_conn_factory():
    if not DB_PATH.exists():
        raise HTTPException(503, "Catalog missing. Run: python -m data.seed")
    return _open_conn


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _pieces(text: str, words: int = 4):
    parts = text.split(" ")
    for i in range(0, len(parts), words):
        yield " ".join(parts[i:i + words]) + (" " if i + words < len(parts) else "")


@app.post("/chat/stream", dependencies=[Depends(rate_limit)])
def chat_stream(req: ChatRequest, llm: LLM = Depends(get_llm), open_conn=Depends(get_conn_factory)):  # noqa: B008
    """Server-sent events: `status`, then `ui` (the product panel, as soon as it is known), `text` pieces of the
    reply, and `done` with the full response. The reply is validated before it is sent, so text is never streamed raw
    from the model: the speed-up is that the products appear before the sentence is finished."""
    events: queue.Queue = queue.Queue()

    def work():
        try:
            with open_conn() as conn:
                session = get_session(req.session_id, req.user_id, conn)
                with session.lock:
                    events.put(("status", {"state": "thinking"}))
                    resp = handle(session, req.message, llm, conn, focus_id=req.focus_product_id,
                                  on_ui=lambda ui, slots: events.put(("ui", {"ui_action": ui, "slots": slots})))
                for piece in _pieces(resp.reply):
                    events.put(("text", {"delta": piece}))
                events.put(("done", resp.model_dump()))
        except Exception:
            log.exception("chat stream failed")
            events.put(("error", {"message": "Something went wrong. Please try again."}))
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield _sse(*item)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/products")
def products(
    use: str | None = None,
    size: float | None = None,
    max_price: int | None = None,
    color: str | None = None,
    ids: str | None = None,
    category: str = "shoes",
    limit: int = 6,
    conn=Depends(get_conn),  # noqa: B008
):
    if ids:
        try:
            wanted = [int(i) for i in ids.split(",") if i][:24]
        except ValueError:
            raise HTTPException(400, "ids must be comma-separated integers") from None
        return {"products": get_shoes_by_ids(conn, wanted)}
    return {"products": search_shoes(conn, use=use, size=size, max_price=max_price, color=color, category=category,
                                      limit=min(max(limit, 1), 24))}


@app.get("/products/{product_id}")
def product(product_id: int, conn=Depends(get_conn)):  # noqa: B008
    shoe = get_shoe(conn, product_id)
    if not shoe:
        raise HTTPException(404, "Product not found")
    return shoe


@app.get("/cart")
def get_cart(session_id: str, conn=Depends(get_conn)):  # noqa: B008
    return cart.view(get_session(session_id), conn)


@app.post("/cart/add")
def cart_add(req: CartAdd, conn=Depends(get_conn)):  # noqa: B008
    session = get_session(req.session_id, req.user_id, conn)
    status = cart.add_item(session, conn, req.product_id, req.size, session.slots.for_whom or "self")
    if status == "unknown":
        raise HTTPException(404, "Product not found")
    if status == "out_of_stock":
        raise HTTPException(409, "That size is out of stock.")
    return cart.view(session, conn)


@app.post("/cart/remove")
def cart_remove(req: CartRemove, conn=Depends(get_conn)):  # noqa: B008
    session = get_session(req.session_id)
    cart.remove_item(session, req.product_id, req.size)
    return cart.view(session, conn)


@app.post("/checkout")
def checkout(req: CheckoutReq, conn=Depends(get_conn)):  # noqa: B008
    session = get_session(req.session_id, req.user_id, conn)
    result = cart.checkout(session, conn)
    if result.get("error") == "empty":
        raise HTTPException(400, "Your cart is empty.")
    if result.get("error"):
        raise HTTPException(409, f"Out of stock in that size: {', '.join(result['items'])}")
    return result


@app.get("/orders/{order_id}")
def order(order_id: str, conn=Depends(get_conn)):  # noqa: B008
    found = cart.get_order(conn, order_id)
    if not found:
        raise HTTPException(404, "Order not found")
    return found


@app.get("/profile")
def get_profile(session_id: str, user_id: str | None = None, conn=Depends(get_conn)):  # noqa: B008
    return profile_flow.view(get_session(session_id, user_id, conn))


@app.post("/profile/forget")
def forget_profile(req: SessionReq, conn=Depends(get_conn)):  # noqa: B008
    session = get_session(req.session_id, req.user_id, conn)
    return {"message": profile_flow.forget(session, conn).reply, "profile": profile_flow.view(session)}


@app.post("/complexion/consent")
def complexion_consent(req: SessionReq, conn=Depends(get_conn)):  # noqa: B008
    session = get_session(req.session_id, req.user_id, conn)
    session.consent, session.complexion = True, "awaiting_photo"
    return {"ok": True}


ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


@app.post("/complexion/analyze", dependencies=[Depends(rate_limit)])
def complexion_analyze(req: AnalyzeReq, llm: LLM = Depends(get_llm), conn=Depends(get_conn)):  # noqa: B008
    session = get_session(req.session_id, req.user_id, conn)
    if not session.consent:
        raise HTTPException(403, "Photo analysis needs your consent first.")
    session.consent = False  # consent covers exactly one photo
    if req.mime_type not in ALLOWED_IMAGES:
        raise HTTPException(400, "Please upload a JPEG, PNG or WebP image.")
    if len(req.image_base64) > MAX_IMAGE_BYTES * 4 // 3 + 16:
        raise HTTPException(413, "That image is too large (5 MB max).")
    try:
        data = base64.b64decode(req.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "That doesn't look like a valid image.") from None
    try:
        estimate = llm.analyze_complexion(data, req.mime_type)
    except Exception:
        raise HTTPException(502, "I couldn't analyse that photo. You can also just tell me your undertone.") from None
    finally:
        del data  # the photo is never written anywhere and not kept in the session
    session.pending_complexion = estimate.model_dump()
    return {"estimate": session.pending_complexion}


@app.post("/complexion/confirm")
def complexion_confirm(req: ConfirmComplexionReq, conn=Depends(get_conn)):  # noqa: B008
    session = get_session(req.session_id, req.user_id, conn)
    if session.pending_complexion is None:
        raise HTTPException(409, "There is no estimate to confirm. Upload a photo first, or just tell me your undertone.")
    message = profile_flow.apply_confirmed(session, conn, req.skin_tone, req.undertone)
    return {"message": message, "profile": profile_flow.view(session)}


@app.post("/complexion/cancel")
def complexion_cancel(req: SessionReq, conn=Depends(get_conn)):  # noqa: B008
    session = get_session(req.session_id, req.user_id, conn)
    session.pending_complexion, session.complexion, session.consent = None, None, False
    return {"ok": True}


# Mounted last so API routes win. Serves the chat + product panel UI at "/".
FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
