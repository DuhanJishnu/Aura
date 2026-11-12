"""Tests for architecture review hardening: SSRF, auth scoping, idempotency, undo, SSOT, SQLite & SSE streaming."""
from __future__ import annotations

import pytest

from stylist_agent.db import AuraDatabase, SqliteSessionService, set_db
from stylist_agent.media import put_media, signed_media_url, validate_public_url, verify_media_token
from stylist_agent.memory import PreferenceStore, decayed_aesthetic_map, look_fingerprint
from stylist_agent.schemas import OutfitLook, OutfitPiece, StyleDNA
from stylist_agent.tools import _compute_look_total


@pytest.mark.asyncio
async def test_ssrf_blocks_localhost_private_and_metadata_ips():
    for bad in (
        "http://localhost/admin",
        "http://127.0.0.1:8000/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://10.0.0.1/internal",
        "http://192.168.1.50/router",
        "file:///etc/passwd",
        "http://myhost.internal/api",
    ):
        with pytest.raises(ValueError):
            await validate_public_url(bad)


def test_user_token_scoping_and_403_on_mismatch(client):
    tok_resp = client.post("/auth/session", json={"user_id": "scoped_user"})
    assert tok_resp.status_code == 200
    token = tok_resp.json()["token"]
    assert token

    # Missing or wrong token cannot read or mutate scoped_user's profile
    assert client.get("/profile?user_id=scoped_user").status_code == 403
    assert (
        client.get("/profile?user_id=scoped_user", headers={"X-Aura-Token": "wrong-token"}).status_code
        == 403
    )

    # Valid token succeeds
    ok = client.get("/profile?user_id=scoped_user", headers={"X-Aura-Token": token})
    assert ok.status_code == 200
    assert ok.json()["user_id"] == "scoped_user"


def test_swipe_idempotency_and_undo(client):
    res = client.post(
        "/looks/search",
        json={"session_id": "s_idem", "user_id": "u_idem", "occasion": "date night"},
    )
    looks = res.json()["looks"]
    first = looks[0]

    # Duplicate swipes with same idempotency_key only count once
    r1 = client.post(
        "/swipes",
        json={"session_id": "s_idem", "user_id": "u_idem", "look": first, "action": "save", "idempotency_key": "k-1"},
    )
    r2 = client.post(
        "/swipes",
        json={"session_id": "s_idem", "user_id": "u_idem", "look": first, "action": "save", "idempotency_key": "k-1"},
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert len(r2.json()["style_dna"]["swipe_history"]) == 1
    assert len(r2.json()["style_dna"]["saved_outfits"]) == 1

    # Undo reverts last swipe cleanly
    undo = client.post(
        "/swipes",
        json={"session_id": "s_idem", "user_id": "u_idem", "action": "undo"},
    )
    assert undo.status_code == 200
    dna_after = undo.json()["style_dna"]
    assert dna_after["swipe_history"] == []
    assert dna_after["saved_outfits"] == []


def test_server_ssot_rejects_client_overwrite(tmp_path):
    db = AuraDatabase(tmp_path / "ssot.db")
    set_db(db)
    try:
        store = PreferenceStore(base_dir=tmp_path / "p", persist=True, db=db)
        server_dna = StyleDNA(user_id="ssot_u", liked_colors=["olive"], sizes={"shoes": "9"})
        store.save(server_dna)

        # Client sends tampered / stale StyleDNA
        tampered = StyleDNA(user_id="ssot_u", liked_colors=["neon pink"], sizes={"shoes": "12"}, tutorial_seen=True)
        merged = store.sync_from_client("ssot_u", tampered)
        assert merged.liked_colors == ["olive"]
        assert merged.sizes["shoes"] == "9"
        assert merged.tutorial_seen is True  # benign tutorial flag merges cleanly
    finally:
        set_db(None)
        db.close()


def test_deterministic_look_total_and_fingerprint_dedupe():
    p1 = OutfitPiece(slot="Top", name="Olive Linen Shirt", brand="Uniqlo", color="olive", price_estimate_inr=2490)
    p2 = OutfitPiece(slot="Bottom", name="Ecru Chino", brand="Zara", color="cream", price_estimate_inr=3290)
    total_inr, total_txt = _compute_look_total([p1, p2], 99999, "~₹99,999")
    assert total_inr == 5780
    assert total_txt == "₹5,780"

    look_a = OutfitLook(
        id="look_llm_1",
        title="Evening Olive Linen",
        occasion="date night",
        vibe="minimalist",
        color_story="Neutral + olive",
        proportion_tip="Boxy top",
        pieces=[p1, p2],
    )
    look_b = look_a.model_copy(update={"id": "look_llm_999", "title": "Completely Renamed Olive Evening"})
    assert look_fingerprint(look_a) == look_fingerprint(look_b)


def test_signed_media_url_verification_and_looks_stream(client):
    mid = put_media(b"\xff\xd8\xff\xe0jpg-data", "image/jpeg", key="signed_1", user_id="u_s", image_source="ai_generated")
    url = signed_media_url(mid, ttl_seconds=600)
    sig = url.split("sig=")[1]
    exp = url.split("exp=")[1].split("&")[0]
    assert verify_media_token(mid, sig, exp) is True
    assert client.get(f"/media/{mid}?exp={exp}&sig={sig}").status_code == 200
    assert client.get(f"/media/{mid}?exp={exp}&sig=tampered").status_code == 403

    with client.stream(
        "POST",
        "/looks/search/stream",
        json={"session_id": "s_str", "user_id": "u_s", "occasion": "date night"},
    ) as resp:
        assert resp.status_code == 200
        raw = "".join(resp.iter_text())
    assert "event: look" in raw
    assert "event: done" in raw


def test_preference_time_decay_weights_recent_higher():
    dna = StyleDNA(
        user_id="decay_u",
        aesthetics={"minimalist": 4.0, "y2k": 4.0},
        aesthetic_timestamps={"minimalist": "2026-11-11T00:00:00+00:00", "y2k": "2026-01-01T00:00:00+00:00"},
    )
    decayed = decayed_aesthetic_map(dna)
    assert decayed["minimalist"] > decayed["y2k"]


@pytest.mark.asyncio
async def test_sqlite_session_persists_across_instances_and_forgets(tmp_path):
    db = AuraDatabase(tmp_path / "sess.db")
    set_db(db)
    try:
        ss1 = SqliteSessionService(db=db)
        await ss1.create_session(app_name="shopper_stylist", user_id="u_sess", session_id="s_1", state={"step": 2})

        ss2 = SqliteSessionService(db=db)
        restored = await ss2.get_session(app_name="shopper_stylist", user_id="u_sess", session_id="s_1")
        assert restored is not None
        assert restored.state["step"] == 2

        await ss2.delete_user_sessions("u_sess")
        assert await ss2.get_session(app_name="shopper_stylist", user_id="u_sess", session_id="s_1") is None
    finally:
        set_db(None)
        db.close()
