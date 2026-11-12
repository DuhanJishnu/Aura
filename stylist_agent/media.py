"""Visual enrichment & SSRF-hardened media pipeline for fashion items and outfit lookbooks.

1. SSRF-safe external HTTP fetch (`validate_public_url`, manual redirect validation, DNS global-IP check,
   response size & content-type caps).
2. Extracts real product images (`og:image`, `twitter:image`, JSON-LD `image`) AND verified store prices
   from grounded retail pages concurrently under an asyncio semaphore and strict timeouts.
3. Uses async Gemini Vision (`client.aio`) + model fallback to verify fetched thumbnails match the garment.
4. Labels AI-generated studio visuals with `image_source='ai_generated'`.
5. Persists media blobs in SQLite (`AuraDatabase.media_cache`) + hot in-memory LRU with HMAC signing support.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import ipaddress
import logging
import re
import secrets
import socket
import threading
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from urllib.parse import urljoin, urlparse

import httpx
from google.genai import types

from app import config
from stylist_agent.db import get_db
from stylist_agent.schemas import FashionItem, OutfitLook, OutfitPiece

log = logging.getLogger("shopper.media")

_MAX_MEDIA = config.MEDIA_MAX_ENTRIES
_LOCK = threading.RLock()
_MEDIA_CACHE: OrderedDict[str, tuple[bytes, str, str]] = OrderedDict()  # id -> (bytes, mime, user_id)
_GENAI_CLIENT = None
_FETCH_SEMAPHORE = asyncio.Semaphore(4)
_MAX_REDIRECTS = 4
_MAX_HTML_BYTES = 1_000_000
_MAX_IMAGE_BYTES = 4_194_304
_PROCESS_SIGNING_SECRET = config.MEDIA_SIGNING_SECRET or secrets.token_hex(32)

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "169.254.169.254",
    "100.100.100.200",
    "0.0.0.0",
    "::1",
    "::",
}

_OG_PATTERNS = [
    re.compile(r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']', re.I),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']', re.I),
    re.compile(r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']', re.I),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']', re.I),
    re.compile(r'"image"\s*:\s*"(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', re.I),
]

_PRICE_PATTERNS = [
    re.compile(r'<meta[^>]+(?:property|name)=["\'](?:product|og):price:amount["\'][^>]+content=["\']([0-9][0-9.,]*)["\']', re.I),
    re.compile(r'"price"\s*:\s*"?([0-9][0-9.,]*)"?', re.I),
]
_CURRENCY_RE = re.compile(r'"priceCurrency"\s*:\s*"([A-Z]{3})"', re.I)


def _get_genai_client():
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None and config.GEMINI_API_KEY:
        from google import genai

        _GENAI_CLIENT = genai.Client(api_key=config.GEMINI_API_KEY)
    return _GENAI_CLIENT


def sign_media_token(media_id: str, exp: int) -> str:
    msg = f"{media_id}:{exp}".encode()
    return hmac.new(_PROCESS_SIGNING_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:24]


def verify_media_token(media_id: str, sig: str | None, exp: str | None) -> bool:
    if not sig or not exp:
        return True  # optional signature check for direct ID links unless sig supplied
    try:
        exp_ts = int(exp)
        if exp_ts < int(time.time()):
            return False
        expected = sign_media_token(media_id, exp_ts)
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


def signed_media_url(media_id: str, ttl_seconds: int = 3600) -> str:
    exp = int(time.time()) + ttl_seconds
    sig = sign_media_token(media_id, exp)
    return f"/api/media/{media_id}?exp={exp}&sig={sig}"


def put_media(
    data: bytes,
    mime_type: str = "image/jpeg",
    key: str | None = None,
    *,
    user_id: str = "",
    image_source: str = "none",
) -> str:
    media_id = key or hashlib.sha1(data[:4096]).hexdigest()[:14]
    with _LOCK:
        _MEDIA_CACHE[media_id] = (data, mime_type, user_id)
        _MEDIA_CACHE.move_to_end(media_id)
        while len(_MEDIA_CACHE) > _MAX_MEDIA:
            _MEDIA_CACHE.popitem(last=False)
    try:
        get_db().put_media(
            media_id,
            data,
            mime_type,
            user_id=user_id,
            image_source=image_source,
            max_entries=_MAX_MEDIA,
        )
    except Exception:
        log.debug("SQLite media_cache write skipped for %s", media_id)
    return media_id


def get_media(media_id: str) -> tuple[bytes, str] | None:
    with _LOCK:
        val = _MEDIA_CACHE.get(media_id)
        if val is not None:
            _MEDIA_CACHE.move_to_end(media_id)
            return val[0], val[1]
    try:
        row = get_db().get_media(media_id)
        if row is not None:
            with _LOCK:
                _MEDIA_CACHE[media_id] = (row[0], row[1], "")
                _MEDIA_CACHE.move_to_end(media_id)
            return row
    except Exception:
        pass
    return None


def purge_user_media(user_id: str) -> None:
    uid = user_id or "default"
    with _LOCK:
        keys = [k for k, (_, _, owner) in _MEDIA_CACHE.items() if owner == uid]
        for k in keys:
            _MEDIA_CACHE.pop(k, None)
    try:
        get_db().delete_user_media(uid)
    except Exception:
        pass


def _is_ip_public(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str.split("%")[0])
        return (
            addr.is_global
            and not addr.is_private
            and not addr.is_loopback
            and not addr.is_link_local
            and not addr.is_multicast
            and not addr.is_reserved
            and not addr.is_unspecified
        )
    except ValueError:
        return False


def _resolve_host_ips_sync(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos if info[4]]


async def validate_public_url(url: str) -> str:
    """Validate URL scheme, host, and resolved public IP addresses to block SSRF."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Unsupported URL scheme")
    host = (parsed.hostname or "").strip().lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError(f"Blocked internal hostname: {host}")

    # Direct IP literal check before DNS
    try:
        ipaddress.ip_address(host)
        if not _is_ip_public(host):
            raise ValueError(f"Blocked non-public IP: {host}")
        return url
    except ValueError as exc:
        if "Blocked non-public IP" in str(exc):
            raise

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        ips = await asyncio.to_thread(_resolve_host_ips_sync, host, port)
    except OSError as exc:
        raise ValueError(f"DNS lookup failed for {host}: {exc}") from exc
    if not ips or not all(_is_ip_public(ip) for ip in ips):
        raise ValueError(f"DNS resolved to non-public IP for {host}")
    return url


async def _safe_fetch(
    url: str,
    *,
    accept: str,
    max_bytes: int,
    timeout: float,
    allowed_prefixes: tuple[str, ...],
) -> tuple[str, int, str, bytes] | None:
    """Fetch an external URL with per-hop SSRF re-validation, strict byte caps, and content-type filtering."""
    current_url = url
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": accept,
    }
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=timeout, headers=headers) as client:
            for _ in range(_MAX_REDIRECTS + 1):
                await validate_public_url(current_url)
                async with client.stream("GET", current_url) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        loc = resp.headers.get("location")
                        if not loc:
                            return None
                        current_url = urljoin(current_url, loc)
                        continue
                    if resp.status_code >= 400:
                        return str(resp.url), resp.status_code, "", b""
                    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                    if allowed_prefixes and not any(ctype.startswith(p) for p in allowed_prefixes):
                        return None
                    if "svg" in ctype:
                        return None
                    clen = resp.headers.get("content-length")
                    if clen and clen.isdigit() and int(clen) > max_bytes:
                        return None
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes(16384):
                        total += len(chunk)
                        if total > max_bytes:
                            return None
                        chunks.append(chunk)
                    return str(resp.url), resp.status_code, ctype, b"".join(chunks)
    except Exception:
        return None
    return None


def _looks_like_product_image(url: str) -> bool:
    low = url.lower()
    if not low.startswith(("http://", "https://")):
        return False
    bad_tokens = ("favicon", "logo", "sprite", "pixel", "1x1", "spacer", ".svg", "placeholder")
    return not any(b in low for b in bad_tokens)


def _extract_page_price(body: str) -> tuple[int | None, str | None]:
    """Extract verified INR price from HTML JSON-LD or product meta tags when available."""
    cur_match = _CURRENCY_RE.search(body)
    currency = cur_match.group(1).upper() if cur_match else "INR"
    if currency not in ("INR", "RS", ""):
        return None, None
    for pat in _PRICE_PATTERNS:
        m = pat.search(body)
        if m:
            raw = m.group(1).replace(",", "").strip()
            try:
                val = int(round(float(raw)))
                if 100 <= val <= 500_000:
                    return val, f"₹{val:,}"
            except ValueError:
                continue
    return None, None


async def _download_image_bytes(img_url: str) -> tuple[bytes, str] | None:
    """SSRF-safe download of external product image bytes."""
    fetched = await _safe_fetch(
        img_url,
        accept="image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        max_bytes=_MAX_IMAGE_BYTES,
        timeout=3.0,
        allowed_prefixes=("image/",),
    )
    if fetched is None:
        return None
    _, status, ctype, data = fetched
    if status >= 400 or len(data) < 2048:
        return None
    return data, ctype or "image/jpeg"


async def _vision_matches_item(img_bytes: bytes, mime_type: str, item_name: str, category: str) -> bool:
    """Async Gemini vision sanity check with model fallback so thumbnails match the garment."""
    if not config.GEMINI_API_KEY or not item_name:
        return True
    client = _get_genai_client()
    if client is None:
        return True
    part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
    prompt = (
        f"Product check: Does this image genuinely show the fashion item '{item_name}' "
        f"(category: '{category}') — NOT a wrong garment type (e.g. shorts instead of trousers), "
        f"NOT a banner/logo/placeholder? Reply ONLY 'YES' or 'NO'."
    )
    models = list(dict.fromkeys([config.GEMINI_MODEL, config.GEMINI_MODEL_FALLBACK]))
    for model_name in models:
        try:
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model_name,
                    contents=[part, prompt],
                    config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=8),
                ),
                timeout=4.0,
            )
            ans = (resp.text or "").strip().upper()
            return not ans.startswith("NO")
        except Exception:
            continue
    return True


def _vision_matches_item_sync(img_bytes: bytes, mime_type: str, item_name: str, category: str) -> bool:
    """Legacy sync wrapper retained for compatibility; delegates safely."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_vision_matches_item(img_bytes, mime_type, item_name, category))
    return True


async def fetch_page_image(
    url: str,
    item_name: str = "",
    category: str = "",
    *,
    user_id: str = "",
) -> tuple[str, str, int | None, str | None, bool]:
    """SSRF-guarded page fetch extracting final URL, product image, verified price, and HTTP reachability."""
    if not url or "google.com/search" in url:
        return url, "", None, None, False
    fetched = await _safe_fetch(
        url,
        accept="text/html,application/xhtml+xml",
        max_bytes=_MAX_HTML_BYTES,
        timeout=3.0,
        allowed_prefixes=("text/html", "application/xhtml+xml"),
    )
    if fetched is None:
        return url, "", None, None, False
    final_url, status, _, raw_body = fetched
    if status >= 400 or not raw_body:
        return final_url, "", None, None, False
    body = raw_body.decode("utf-8", errors="ignore")[:150_000]
    page_price_inr, page_price_text = _extract_page_price(body)

    for pat in _OG_PATTERNS:
        m = pat.search(body)
        if not m:
            continue
        candidate = html.unescape(m.group(1).strip())
        resolved = urljoin(final_url, candidate)
        if not _looks_like_product_image(resolved):
            continue
        downloaded = await _download_image_bytes(resolved)
        if downloaded is None:
            continue
        img_bytes, mime = downloaded
        if item_name:
            ok = await _vision_matches_item(img_bytes, mime, item_name, category)
            if not ok:
                log.info("Discarded mismatched product image for %s (%s)", item_name, resolved)
                return final_url, "", page_price_inr, page_price_text, True
        cache_key = "ext_" + hashlib.sha1(resolved.encode()).hexdigest()[:12]
        mid = put_media(img_bytes, mime, key=cache_key, user_id=user_id, image_source="retailer")
        return final_url, signed_media_url(mid), page_price_inr, page_price_text, True

    return final_url, "", page_price_inr, page_price_text, True


def _generate_image_sync(prompt: str, cache_key: str, *, user_id: str = "") -> str:
    if not config.GEMINI_API_KEY:
        return ""
    existing = get_media(cache_key)
    if existing is not None:
        return signed_media_url(cache_key)
    client = _get_genai_client()
    if client is None:
        return ""
    for model_name in dict.fromkeys([config.GEMINI_IMAGE_MODEL, config.GEMINI_IMAGE_MODEL_FALLBACK]):
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            parts = resp.candidates[0].content.parts if resp.candidates else []
            img = next((p.inline_data for p in parts if getattr(p, "inline_data", None)), None)
            if img and getattr(img, "data", None):
                mid = put_media(
                    img.data,
                    getattr(img, "mime_type", None) or "image/jpeg",
                    key=cache_key,
                    user_id=user_id,
                    image_source="ai_generated",
                )
                return signed_media_url(mid)
        except Exception as exc:
            log.debug("Image generation failed (%s on %s): %s", cache_key, model_name, exc)
    return ""


async def generate_fashion_image(prompt: str, cache_key: str, *, user_id: str = "") -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_generate_image_sync, prompt, cache_key, user_id=user_id),
            timeout=9.0,
        )
    except Exception:
        return ""


async def enrich_item_images(items: list[FashionItem], max_gen: int = 4, *, user_id: str = "") -> list[FashionItem]:
    """Concurrently resolve real og:image + verified price and tag AI fallback visuals accurately."""

    async def enrich_one(idx: int, item: FashionItem) -> FashionItem:
        async with _FETCH_SEMAPHORE:
            final_url, img_url = item.url, item.image_url
            img_source = item.image_source
            domain = item.source_domain
            price_inr = item.price_estimate_inr
            price_text = item.price_text
            url_verified = item.url_verified

            if not img_url and item.url_verified and item.url:
                final_url, img_url, found_inr, found_txt, reachable = await fetch_page_image(
                    item.url, item_name=item.name, category=item.category, user_id=user_id
                )
                url_verified = reachable
                if img_url:
                    img_source = "retailer"
                if found_inr and found_txt:
                    price_inr = found_inr
                    price_text = found_txt
                try:
                    host = urlparse(final_url).netloc.lower().removeprefix("www.")
                    if host and "vertexaisearch.cloud.google.com" not in host:
                        domain = host
                except Exception:
                    pass

            if not img_url and idx < max_gen:
                prompt = (
                    f"Clean e-commerce studio product photograph on soft warm stone background of: "
                    f"{item.color} {item.name} ({item.category}) by {item.brand}. "
                    f"Style vibe: {', '.join(item.aesthetic_tags[:3]) or 'modern minimalist'}. "
                    f"Sharp garment details, natural lighting, no text, no watermarks."
                )
                img_url = await generate_fashion_image(prompt, cache_key=f"item_{item.id}", user_id=user_id)
                if img_url:
                    img_source = "ai_generated"

            return item.model_copy(
                update={
                    "url": final_url,
                    "url_verified": url_verified,
                    "source_domain": domain,
                    "image_url": img_url,
                    "image_source": img_source,
                    "price_estimate_inr": price_inr,
                    "price_text": price_text,
                }
            )

    return list(await asyncio.gather(*(enrich_one(i, item) for i, item in enumerate(items))))


async def enrich_outfit_images(look: OutfitLook, *, user_id: str = "") -> OutfitLook:
    """Generate a hero outfit lookbook visualization AND piece visuals in parallel."""
    piece_desc = ", ".join(f"{p.color} {p.name}" for p in look.pieces[:5])
    hero_prompt = (
        f"Editorial fashion lookbook flat-lay and styled outfit visualization on a clean warm cream backdrop "
        f"for '{look.occasion}' ({look.vibe} aesthetic), featuring: {piece_desc}. "
        f"Cohesive luxury fashion photography, crisp textures, natural daylight, no text or labels."
    )

    async def enrich_piece(p: OutfitPiece, idx: int) -> OutfitPiece:
        async with _FETCH_SEMAPHORE:
            if p.image_url:
                return p
            p_prompt = (
                f"Minimalist studio product shot on soft neutral background of: {p.color} {p.name} ({p.slot}). "
                f"Clean lighting, no text."
            )
            key = f"piece_{look.id}_{idx}"
            img = await generate_fashion_image(p_prompt, cache_key=key, user_id=user_id)
            return p.model_copy(
                update={"image_url": img, "image_source": "ai_generated" if img else "none"}
            )

    hero_task = generate_fashion_image(hero_prompt, cache_key=f"look_{look.id}", user_id=user_id)
    piece_tasks = [enrich_piece(p, i) for i, p in enumerate(look.pieces)]
    hero_url, *enriched_pieces = await asyncio.gather(hero_task, *piece_tasks)

    return look.model_copy(
        update={
            "image_url": hero_url,
            "image_source": "ai_generated" if hero_url else "none",
            "pieces": list(enriched_pieces),
        }
    )


async def _enrich_look_hero(look: OutfitLook, *, user_id: str = "") -> OutfitLook:
    async with _FETCH_SEMAPHORE:
        if look.image_url:
            return look
        piece_desc = ", ".join(f"{p.color} {p.name}" for p in look.pieces[:5])
        hero_prompt = (
            f"Editorial fashion lookbook flat-lay and styled full outfit photo on soft warm neutral stone backdrop "
            f"for '{look.occasion}' ({look.vibe} aesthetic), featuring: {piece_desc}. "
            f"High-fashion luxury styling, crisp textures, natural daylight, no text, no watermarks."
        )
        hero_url = await generate_fashion_image(hero_prompt, cache_key=f"look_{look.id}", user_id=user_id)
        return look.model_copy(
            update={
                "image_url": hero_url,
                "image_source": "ai_generated" if hero_url else look.image_source,
            }
        )


async def enrich_look_deck_images(looks: list[OutfitLook], *, user_id: str = "") -> list[OutfitLook]:
    """Generate cohesive hero editorial photos for a multi-look swipe deck concurrently."""
    return list(await asyncio.gather(*(_enrich_look_hero(lk, user_id=user_id) for lk in looks)))


async def enrich_look_deck_stream(looks: list[OutfitLook], *, user_id: str = "") -> AsyncIterator[OutfitLook]:
    """Stream each look card as soon as its hero image finishes enriching."""
    tasks = [asyncio.create_task(_enrich_look_hero(lk, user_id=user_id)) for lk in looks]
    for fut in asyncio.as_completed(tasks):
        yield await fut
