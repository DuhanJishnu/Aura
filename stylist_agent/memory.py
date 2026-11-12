"""SQLite-backed Style DNA & Swipe Preference Memory.

Stores user preferences, seasonal color palettes, per-occasion tastes, time-decayed aesthetic weights,
saved closet/wishlist items, and swipe history atomically via AuraDatabase SQLite.
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

from app.config import PROFILE_STORE_DIR
from stylist_agent.db import AuraDatabase, get_db
from stylist_agent.schemas import FactEntry, FashionItem, OutfitLook, StyleDNA, SwipeRecord

UNDERTONE_PALETTES: dict[str, dict[str, list[str]]] = {
    "warm": {
        "best": ["olive", "terracotta", "camel", "mustard", "rust", "cream", "ivory", "forest green", "warm brown", "coral", "gold", "khaki"],
        "avoid": ["icy blue", "stark optic white", "neon pink", "silver"],
    },
    "cool": {
        "best": ["navy", "cobalt", "emerald", "burgundy", "charcoal", "crisp white", "lavender", "plum", "slate", "silver", "berry", "black"],
        "avoid": ["mustard", "orange", "rust", "yellow-green"],
    },
    "neutral": {
        "best": ["sage", "taupe", "dusty rose", "soft white", "navy", "stone", "charcoal", "jade", "teal", "oatmeal", "black"],
        "avoid": ["harsh neon"],
    },
}

SEASON_MAP: dict[tuple[str, str], str] = {
    ("fair", "warm"): "Spring",
    ("light", "warm"): "Spring",
    ("medium", "warm"): "Autumn",
    ("tan", "warm"): "Autumn",
    ("deep", "warm"): "Autumn",
    ("fair", "cool"): "Summer",
    ("light", "cool"): "Summer",
    ("medium", "cool"): "Winter",
    ("tan", "cool"): "Winter",
    ("deep", "cool"): "Winter",
    ("fair", "neutral"): "Summer",
    ("light", "neutral"): "Spring",
    ("medium", "neutral"): "Autumn",
    ("tan", "neutral"): "Autumn",
    ("deep", "neutral"): "Winter",
}


def item_key(item: FashionItem) -> str:
    raw = f"{item.brand.strip().lower()}|{item.name.strip().lower()}"
    return re.sub(r"\s+", " ", raw)


def look_fingerprint(look: OutfitLook) -> str:
    """Stable content fingerprint independent of LLM-generated look IDs/titles."""
    if look.look_fingerprint:
        return look.look_fingerprint
    tokens: list[str] = []
    for p in look.pieces:
        if p.url and p.url_verified:
            tokens.append(f"u:{p.url.split('?')[0].strip().lower()}")
        else:
            brand = re.sub(r"\s+", " ", (p.brand or p.store or "").strip().lower())
            name = re.sub(r"\s+", " ", p.name.strip().lower())
            color = re.sub(r"\s+", " ", p.color.strip().lower())
            tokens.append(f"p:{brand}|{name}|{color}")
    canonical = "|".join(sorted(tokens)) or re.sub(r"\s+", " ", look.title.strip().lower())
    return "fp_" + hashlib.sha1(canonical.encode()).hexdigest()[:12]


def _safe_user_id(user_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id.strip())
    return cleaned[:80] or "default"


def _decay_factor(timestamp_iso: str | None, half_life_days: float = 21.0) -> float:
    """Exponential time decay (recent taste outweighs stale swipes)."""
    if not timestamp_iso:
        return 1.0
    try:
        dt = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        age_days = max(0.0, (datetime.now(UTC) - dt).total_seconds() / 86400.0)
        return math.pow(0.5, age_days / half_life_days)
    except Exception:
        return 1.0


def decayed_aesthetic_map(dna: StyleDNA, occasion: str | None = None) -> dict[str, float]:
    """Return effective time-decayed aesthetic weights, blending occasion-specific + explicit + global swipes."""
    out: dict[str, float] = {}
    stated_tags = {f.value.strip().lower() for f in dna.facts if f.key == "aesthetic" and f.source in ("stated", "confirmed")}
    for tag, raw in dna.aesthetics.items():
        t = tag.strip().lower()
        factor = 1.0 if t in stated_tags else _decay_factor(dna.aesthetic_timestamps.get(t))
        out[t] = round(raw * factor, 3)

    if occasion:
        occ_key = re.sub(r"\s+", " ", occasion.strip().lower())
        occ_map = dna.occasion_aesthetics.get(occ_key, {})
        for tag, val in occ_map.items():
            t = tag.strip().lower()
            out[t] = round(out.get(t, 0.0) + val * 0.75, 3)
    return out


def pref_hash(dna: StyleDNA) -> str:
    """Compact deterministic hash of user taste constraints for search cache keys."""
    sig = {
        "aesthetics": sorted((k, round(v, 1)) for k, v in dna.aesthetics.items() if abs(v) >= 0.5)[:10],
        "liked": sorted(dna.liked_colors)[:8],
        "disliked": sorted(dna.disliked_colors)[:8],
        "undertone": dna.undertone or "",
        "budget": dna.budget_max or 0,
        "fit": dna.fit_preference or "",
    }
    return hashlib.sha1(str(sig).encode("utf-8")).hexdigest()[:12]


def _upsert_fact(dna: StyleDNA, key: str, value: str, source: str, singleton: bool = True) -> None:
    if singleton:
        existing = next((f for f in dna.facts if f.key == key), None)
        if existing and existing.source in ("stated", "confirmed") and source in ("swiped", "inferred"):
            return
        dna.facts = [f for f in dna.facts if f.key != key]
    else:
        existing = next((f for f in dna.facts if f.key == key and f.value.lower() == value.lower()), None)
        if existing and existing.source in ("stated", "confirmed") and source in ("swiped", "inferred"):
            return
        dna.facts = [f for f in dna.facts if not (f.key == key and f.value.lower() == value.lower())]
    dna.facts.append(FactEntry(key=key, value=value, source=source))  # type: ignore[arg-type]


def infer_season(skin_tone: str | None, undertone: str | None) -> str | None:
    if not skin_tone or not undertone:
        return None
    return SEASON_MAP.get((skin_tone.lower(), undertone.lower()))


def _learn_tastes(
    dna: StyleDNA,
    *,
    positive: bool,
    weight: float,
    tags: list[str],
    colors: list[str],
    brands: list[str],
    occasion: str = "",
    timestamp: str = "",
) -> None:
    """Unified taste-learning helper shared by item swipes and outfit-look swipes."""
    occ_key = re.sub(r"\s+", " ", occasion.strip().lower()) if occasion else ""
    occ_bucket = dna.occasion_aesthetics.setdefault(occ_key, {}) if occ_key else None

    for tag in tags:
        t = tag.strip().lower()
        if not t:
            continue
        prev = dna.aesthetics.get(t, 0.0)
        if positive:
            dna.aesthetics[t] = round(min(10.0, prev + weight), 2)
            if occ_bucket is not None:
                occ_bucket[t] = round(min(10.0, occ_bucket.get(t, 0.0) + weight), 2)
            dna.aesthetic_timestamps[t] = timestamp
            _upsert_fact(dna, "aesthetic", t, "swiped", singleton=False)
        else:
            # Implicit skip penalty is gentler than explicit stated dislikes (user may just dislike the photo)
            dna.aesthetics[t] = round(max(-5.0, prev - weight), 2)
            if occ_bucket is not None:
                occ_bucket[t] = round(max(-5.0, occ_bucket.get(t, 0.0) - weight), 2)

    if positive:
        for c in colors:
            cl = c.strip().lower()
            if cl and cl not in dna.disliked_colors and cl not in dna.liked_colors:
                dna.liked_colors.append(cl)
                _upsert_fact(dna, "liked_color", cl, "swiped", singleton=False)
        for b in brands:
            bs = b.strip()
            if bs and bs.lower() not in ("independent / curated", "google shopping") and bs not in dna.liked_brands:
                dna.liked_brands.append(bs)


def apply_swipe(dna: StyleDNA, item: FashionItem, direction: str) -> str:
    """Update StyleDNA from an item swipe (like/dislike/super_like) and return a stylist reaction."""
    key = item_key(item)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    dna.swipe_history = [
        *dna.swipe_history[-49:],
        SwipeRecord(
            item_id=item.id,
            item_name=item.name,
            direction=direction,  # type: ignore[arg-type]
            tags=item.aesthetic_tags[:5],
            color=item.color,
            brand=item.brand,
            price_estimate_inr=item.price_estimate_inr,
            timestamp=now,
        ),
    ]

    if direction in ("like", "super_like"):
        weight = 2.5 if direction == "super_like" else 1.25
        dna.disliked_item_keys = [k for k in dna.disliked_item_keys if k != key]
        if not any(item_key(c) == key or c.id == item.id for c in dna.saved_closet):
            dna.saved_closet.insert(0, item)
            dna.saved_closet = dna.saved_closet[:60]
        _learn_tastes(
            dna,
            positive=True,
            weight=weight,
            tags=item.aesthetic_tags,
            colors=[item.color],
            brands=[item.brand],
            timestamp=now,
        )
        if direction == "super_like":
            return f"Ooh, loving that pick! Saved {item.name} to your closet — say 'style an outfit around it' anytime!"
        tags_note = f" ({', '.join(item.aesthetic_tags[:2])})" if item.aesthetic_tags else ""
        return f"Saved {item.name} to your closet! Noted your taste for {item.color}{tags_note}."

    # direction == "dislike"
    if key not in dna.disliked_item_keys:
        dna.disliked_item_keys.append(key)
        dna.disliked_item_keys = dna.disliked_item_keys[-120:]
    dna.saved_closet = [c for c in dna.saved_closet if item_key(c) != key and c.id != item.id]
    _learn_tastes(
        dna,
        positive=False,
        weight=0.45,
        tags=item.aesthetic_tags,
        colors=[],
        brands=[],
        timestamp=now,
    )
    return f"Got it, passing on {item.name} — I'll steer away from that vibe in your next picks."


def apply_look_swipe(dna: StyleDNA, look: OutfitLook, action: str) -> str:
    """Update StyleDNA & Wishlist from a LookCard swipe (save/skip/buy_intent/undo)."""
    if action == "undo":
        return undo_last_swipe(dna)

    now = datetime.now(UTC).isoformat(timespec="seconds")
    fp = look_fingerprint(look)
    if look.id and look.id not in dna.seen_look_ids:
        dna.seen_look_ids.append(look.id)
        dna.seen_look_ids = dna.seen_look_ids[-200:]
    if fp and fp not in dna.seen_look_fingerprints:
        dna.seen_look_fingerprints.append(fp)
        dna.seen_look_fingerprints = dna.seen_look_fingerprints[-250:]

    colors = list(dict.fromkeys(p.color.strip().lower() for p in look.pieces if p.color.strip()))
    brands = list(dict.fromkeys((p.brand or p.store).strip() for p in look.pieces if (p.brand or p.store).strip()))
    direction = "like" if action == "save" else ("super_like" if action == "buy_intent" else "dislike")
    dna.swipe_history = [
        *dna.swipe_history[-49:],
        SwipeRecord(
            item_id=look.id,
            item_name=look.title,
            direction=direction,  # type: ignore[arg-type]
            tags=(look.tags or [look.vibe])[:5],
            color=", ".join(colors[:3]),
            brand=", ".join(brands[:3]),
            occasion=look.occasion,
            price_estimate_inr=look.total_estimate_inr,
            timestamp=now,
        ),
    ]

    if action in ("save", "buy_intent"):
        weight = 2.0 if action == "buy_intent" else 1.5
        _learn_tastes(
            dna,
            positive=True,
            weight=weight,
            tags=[look.vibe, *look.tags],
            colors=colors,
            brands=brands,
            occasion=look.occasion,
            timestamp=now,
        )
        if action == "save":
            stamped = look.model_copy(update={"saved_at": now, "look_fingerprint": fp})
            dna.saved_outfits = [stamped, *[o for o in dna.saved_outfits if o.id != look.id]][:30]
            return f"Saved '{look.title}' to your Wishlist!"
        return f"Logged shopping intent for '{look.title}' — happy shopping!"

    # action == "skip"
    dna.saved_outfits = [o for o in dna.saved_outfits if o.id != look.id]
    _learn_tastes(
        dna,
        positive=False,
        weight=0.4,
        tags=[look.vibe, *look.tags],
        colors=[],
        brands=[],
        occasion=look.occasion,
        timestamp=now,
    )
    return f"Skipped '{look.title}' — tuning your next looks."


def undo_last_swipe(dna: StyleDNA) -> str:
    """Revert the most recent swipe action cleanly."""
    if not dna.swipe_history:
        return "Nothing to undo."
    last = dna.swipe_history.pop()
    target_id = last.item_id
    # Remove from wishlist or closet if it was a save/like
    if last.direction in ("like", "super_like"):
        dna.saved_outfits = [o for o in dna.saved_outfits if o.id != target_id]
        dna.saved_closet = [i for i in dna.saved_closet if i.id != target_id]
        delta = -1.5
    else:
        dna.disliked_item_keys = [k for k in dna.disliked_item_keys if k != target_id]
        delta = 0.4

    dna.seen_look_ids = [lid for lid in dna.seen_look_ids if lid != target_id]
    for tag in last.tags:
        t = tag.strip().lower()
        if t and t in dna.aesthetics:
            dna.aesthetics[t] = round(max(-5.0, min(10.0, dna.aesthetics[t] + delta)), 2)
    return f"Undid swipe on '{last.item_name}'."


def score_item(item: FashionItem, dna: StyleDNA, occasion: str | None = None) -> tuple[float, list[str]]:
    """Score an online-discovered fashion item against StyleDNA (explicit statements > swiped signals)."""
    score = 72.0
    reasons: list[str] = []
    color_l = item.color.strip().lower()
    brand_l = item.brand.strip().lower()

    stated_colors = {f.value.strip().lower() for f in dna.facts if f.key == "liked_color" and f.source == "stated"}
    disliked_stated = {f.value.strip().lower() for f in dna.facts if f.key == "disliked_color" and f.source == "stated"}

    if any(c.lower() in color_l or color_l in c.lower() for c in dna.liked_colors):
        is_stated = any(c in color_l or color_l in c for c in stated_colors)
        score += 14.0 if is_stated else 8.0
        reasons.append(f"In your liked {item.color} palette")
    if any(c.lower() in color_l or color_l in c.lower() for c in dna.disliked_colors):
        is_stated = any(c in color_l or color_l in c for c in disliked_stated)
        score -= 24.0 if is_stated else 14.0

    if dna.undertone and dna.undertone.lower() in UNDERTONE_PALETTES:
        pal = UNDERTONE_PALETTES[dna.undertone.lower()]
        if any(c in color_l for c in pal["best"]):
            score += 9.0
            reasons.append(f"Flatters {dna.undertone} undertone")
        elif any(c in color_l for c in pal["avoid"]):
            score -= 8.0

    eff_aesthetics = decayed_aesthetic_map(dna, occasion=occasion)
    stated_aesthetics = {f.value.strip().lower() for f in dna.facts if f.key == "aesthetic" and f.source == "stated"}
    tag_boost = 0.0
    matched_tags: list[str] = []
    for tag in item.aesthetic_tags:
        t = tag.strip().lower()
        aff = eff_aesthetics.get(t, 0.0)
        mult = 2.6 if t in stated_aesthetics else 1.8
        if aff > 0:
            tag_boost += min(7.0, aff * mult)
            matched_tags.append(tag)
        elif aff < 0:
            tag_boost += max(-8.0, aff * mult)
    if matched_tags:
        reasons.append(f"Matches your {matched_tags[0]} taste")
    score += min(16.0, tag_boost)

    if any(b.lower() == brand_l for b in dna.liked_brands):
        score += 6.0
        reasons.append(f"Brand you liked: {item.brand}")

    if item.price_estimate_inr and dna.budget_max:
        if item.price_estimate_inr <= dna.budget_max:
            score += 5.0
            reasons.append(f"Within ₹{dna.budget_max:,} budget")
        elif item.price_estimate_inr > dna.budget_max * 1.25:
            score -= 12.0

    if item.url_verified:
        score += 3.0

    bounded = round(max(15.0, min(99.0, score)), 1)
    return bounded, reasons[:3]


def rerank_items(items: list[FashionItem], dna: StyleDNA, occasion: str | None = None) -> list[FashionItem]:
    """Filter out disliked items and rank remaining items by StyleDNA fit."""
    disliked = set(dna.disliked_item_keys)
    filtered: list[FashionItem] = []
    for item in items:
        if item_key(item) in disliked or item.id in disliked:
            continue
        sc, reasons = score_item(item, dna, occasion=occasion)
        updated = item.model_copy(update={"match_score": sc, "match_reasons": reasons})
        filtered.append(updated)
    filtered.sort(key=lambda x: x.match_score, reverse=True)
    return filtered


def summarize_dna_for_prompt(dna: StyleDNA, occasion: str | None = None) -> str:
    """Compact Style DNA snapshot injected into ADK stylist context."""
    parts: list[str] = []
    if dna.sizes:
        parts.append("Sizes: " + ", ".join(f"{k}={v}" for k, v in dna.sizes.items()))
    eff = decayed_aesthetic_map(dna, occasion=occasion)
    top_aesthetics = sorted(((k, v) for k, v in eff.items() if v > 0.2), key=lambda kv: -kv[1])[:5]
    if top_aesthetics:
        label = f"Preferred aesthetics ({occasion})" if occasion else "Preferred aesthetics"
        parts.append(f"{label}: " + ", ".join(k for k, _ in top_aesthetics))
    if dna.liked_colors:
        parts.append("Liked colors: " + ", ".join(dna.liked_colors[:8]))
    if dna.disliked_colors:
        parts.append("Avoid colors: " + ", ".join(dna.disliked_colors[:6]))
    if dna.undertone:
        season = f" ({dna.color_season})" if dna.color_season else ""
        parts.append(f"Complexion: {dna.skin_tone or 'unspecified'} skin, {dna.undertone} undertone{season}")
    if dna.fit_preference:
        parts.append(f"Fit preference: {dna.fit_preference}")
    if dna.budget_max or dna.budget_min:
        parts.append(f"Budget comfort: ₹{dna.budget_min or 0} - ₹{dna.budget_max or 'open'}")
    if dna.liked_brands:
        parts.append("Liked brands: " + ", ".join(dna.liked_brands[:6]))
    if dna.saved_closet:
        closet_names = [f"{i.name} ({i.color}, {i.category})" for i in dna.saved_closet[:6]]
        parts.append("Saved closet items: " + "; ".join(closet_names))
    recent_dislikes = [s.item_name for s in dna.swipe_history[-10:] if s.direction == "dislike"]
    if recent_dislikes:
        parts.append("Recently passed on: " + ", ".join(recent_dislikes[-4:]))
    if dna.declined:
        parts.append("BOUNDARY: User previously declined shopping pitches; respect their space unless they ask.")
    return "\n".join(parts) if parts else "No saved Style DNA yet — discover gently through conversation."


class PreferenceStore:
    """Thread-safe SQLite-backed StyleDNA store (in-memory only when persist=False)."""

    def __init__(self, base_dir: Path | None = None, persist: bool = True, db: AuraDatabase | None = None):
        self.base_dir = base_dir or PROFILE_STORE_DIR
        self.persist = persist
        self._lock = threading.RLock()
        self._cache: dict[str, StyleDNA] = {}
        self._db: AuraDatabase | None = db
        if persist and self._db is None:
            if base_dir is not None:
                self._db = AuraDatabase(Path(base_dir) / "aura.db")
            else:
                self._db = get_db()

    def _legacy_path(self, user_id: str) -> Path:
        return self.base_dir / f"{_safe_user_id(user_id)}.json"

    def get(self, user_id: str) -> StyleDNA:
        uid = user_id or "default"
        with self._lock:
            if self.persist and self._db is not None:
                dna = self._db.get_profile(uid)
                # One-time migration from legacy JSON file if DB has empty default and JSON exists
                if (
                    not dna.facts
                    and not dna.saved_closet
                    and not dna.saved_outfits
                    and not dna.swipe_history
                ):
                    legacy = self._legacy_path(uid)
                    if legacy.exists():
                        try:
                            dna = StyleDNA.model_validate_json(legacy.read_text(encoding="utf-8"))
                            self._db.save_profile(dna)
                        except Exception:
                            pass
                self._cache[uid] = dna
                return dna.model_copy(deep=True)
            if uid in self._cache:
                return self._cache[uid].model_copy(deep=True)
            dna = StyleDNA(user_id=uid)
            self._cache[uid] = dna
            return dna.model_copy(deep=True)

    def save(self, dna: StyleDNA) -> StyleDNA:
        uid = dna.user_id or "default"
        copy = dna.model_copy(deep=True)
        with self._lock:
            if self.persist and self._db is not None:
                copy = self._db.save_profile(copy)
            self._cache[uid] = copy
        return copy.model_copy(deep=True)

    def sync_from_client(self, user_id: str, client_dna: StyleDNA) -> StyleDNA:
        """Merge client snapshot ONLY when server profile is completely empty; otherwise server is authoritative."""
        uid = user_id or "default"
        with self._lock:
            server = self.get(uid)
            server_empty = (
                not server.facts
                and not server.saved_closet
                and not server.saved_outfits
                and not server.swipe_history
                and not server.sizes
                and not server.tutorial_seen
            )
            if server_empty:
                client_copy = client_dna.model_copy(update={"user_id": uid})
                return self.save(client_copy)
            # Server is Single Source of Truth; only allow benign tutorial flag sync
            if client_dna.tutorial_seen and not server.tutorial_seen:
                server.tutorial_seen = True
                return self.save(server)
            return server

    def forget(self, user_id: str) -> StyleDNA:
        uid = user_id or "default"
        with self._lock:
            if self.persist and self._db is not None:
                fresh = self._db.forget_user(uid)
            else:
                fresh = StyleDNA(user_id=uid)
            self._cache[uid] = fresh
            legacy = self._legacy_path(uid)
            if legacy.exists():
                legacy.unlink(missing_ok=True)
        return fresh.model_copy(deep=True)

    def save_outfit(self, user_id: str, outfit: OutfitLook) -> StyleDNA:
        dna = self.get(user_id)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        fp = look_fingerprint(outfit)
        stamped = outfit.model_copy(update={"saved_at": outfit.saved_at or now, "look_fingerprint": fp})
        if not any(o.id == stamped.id or look_fingerprint(o) == fp for o in dna.saved_outfits):
            dna.saved_outfits.insert(0, stamped)
            dna.saved_outfits = dna.saved_outfits[:30]
        return self.save(dna)

    def remove_outfit(self, user_id: str, look_id: str) -> StyleDNA:
        dna = self.get(user_id)
        dna.saved_outfits = [o for o in dna.saved_outfits if o.id != look_id]
        return self.save(dna)
