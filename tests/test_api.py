from __future__ import annotations

import base64
import json

from app import config


def test_health_and_ready_sqlite_db(client):
    assert client.get("/health").json() == {"ok": True}
    ready = client.get("/ready").json()
    assert ready["adk"] is True
    assert ready["database"] == "sqlite"
    assert ready["llm_key"] is True


def test_chat_and_sse_stream(client):
    r = client.post(
        "/chat",
        json={"session_id": "s1", "user_id": "u1", "message": "Find clean sneakers under 7000"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ui_action"]["type"] == "swipe_deck"
    assert len(body["ui_action"]["items"]) >= 3
    assert "search_fashion_online" in body["tools_used"]

    # SSE stream emits ui before done
    with client.stream(
        "POST",
        "/chat/stream",
        json={"session_id": "s2", "user_id": "u1", "message": "Build a date night outfit"},
    ) as resp:
        assert resp.status_code == 200
        raw = "".join(resp.iter_text())
    assert "event: status" in raw
    assert "event: ui" in raw
    assert "event: text" in raw
    assert "event: done" in raw
    assert raw.index("event: ui") < raw.index("event: done")


def test_swipe_closet_sync_and_forget_lifecycle(client):
    chat_resp = client.post(
        "/chat",
        json={"session_id": "s_sw", "user_id": "u_sw", "message": "Find olive overshirts"},
    ).json()
    first_item = chat_resp["ui_action"]["items"][0]

    swipe_resp = client.post(
        "/swipe",
        json={"session_id": "s_sw", "user_id": "u_sw", "item": first_item, "direction": "like"},
    )
    assert swipe_resp.status_code == 200
    data = swipe_resp.json()
    assert data["stats"]["closet"] == 1
    assert data["style_dna"]["saved_closet"][0]["id"] == first_item["id"]

    # Remove from closet
    del_resp = client.delete(f"/closet/{first_item['id']}?user_id=u_sw")
    assert del_resp.status_code == 200
    assert del_resp.json()["saved_closet"] == []

    # Forget profile
    fg = client.post("/profile/forget", json={"session_id": "s_sw", "user_id": "u_sw"})
    assert fg.status_code == 200
    assert fg.json()["style_dna"]["swipe_history"] == []


def test_friend_circle_back_and_no_means_no_boundary(client):
    off = client.post(
        "/chat",
        json={"session_id": "s_cb", "user_id": "u_cb", "message": "How do I make creamy pasta at home?"},
    ).json()
    assert "pasta" in off["reply"].lower()
    assert any(w in off["reply"].lower() for w in ("outfit", "swipe", "fit", "style"))

    # Explicit decline stops pitching
    dec = client.post(
        "/chat",
        json={"session_id": "s_cb", "user_id": "u_cb", "message": "No thanks, stop pitching outfits"},
    ).json()
    assert dec["style_dna"]["declined"] is True

    after = client.post(
        "/chat",
        json={"session_id": "s_cb", "user_id": "u_cb", "message": "How do I make creamy pasta at home?"},
    ).json()
    assert after["ui_action"]["type"] == "none"
    assert "outfit" not in after["reply"].lower()


def test_consent_first_photo_privacy_complexion_and_outfit_check(client, offline_service):
    img_b64 = base64.b64encode(b"fake-jpeg-bytes").decode()

    # Without consent -> 403
    no_consent = client.post(
        "/complexion/analyze",
        json={"session_id": "s_ph", "user_id": "u_ph", "image_base64": img_b64, "mime_type": "image/jpeg"},
    )
    assert no_consent.status_code == 403

    # Grant consent -> analyze once -> second attempt without new consent fails
    assert client.post("/complexion/consent", json={"session_id": "s_ph", "user_id": "u_ph"}).status_code == 200
    analyzed = client.post(
        "/complexion/analyze",
        json={"session_id": "s_ph", "user_id": "u_ph", "image_base64": img_b64, "mime_type": "image/jpeg"},
    )
    assert analyzed.status_code == 200
    assert analyzed.json()["estimate"]["undertone"] == "warm"
    # Ensure photo bytes are never kept in photo_state
    assert "fake-jpeg-bytes" not in json.dumps(offline_service.photo_state("s_ph"))

    second_try = client.post(
        "/complexion/analyze",
        json={"session_id": "s_ph", "user_id": "u_ph", "image_base64": img_b64, "mime_type": "image/jpeg"},
    )
    assert second_try.status_code == 403

    confirmed = client.post(
        "/complexion/confirm",
        json={"session_id": "s_ph", "user_id": "u_ph", "skin_tone": "medium", "undertone": "warm"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["style_dna"]["color_season"] == "Autumn"

    # Outfit check also requires consent
    assert client.post("/complexion/consent", json={"session_id": "s_ph", "user_id": "u_ph"}).status_code == 200
    check = client.post(
        "/outfit-check/analyze",
        json={"session_id": "s_ph", "user_id": "u_ph", "image_base64": img_b64, "mime_type": "image/png"},
    )
    assert check.status_code == 200
    assert check.json()["result"]["rating_out_of_10"] >= 1


def test_rate_limit_enforced(client, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 2)
    from app import main

    main._hits.clear()
    for _ in range(2):
        assert client.post("/chat", json={"session_id": "rl", "user_id": "rl", "message": "hi"}).status_code == 200
    blocked = client.post("/chat", json={"session_id": "rl", "user_id": "rl", "message": "hi"})
    assert blocked.status_code == 429
    main._hits.clear()


def test_media_endpoint_serves_cached_image_and_404s_missing(client):
    from stylist_agent.media import put_media

    media_id = put_media(b"\xff\xd8\xff\xe0fake-jpeg", "image/jpeg")
    res = client.get(f"/media/{media_id}")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/jpeg")
    assert res.content == b"\xff\xd8\xff\xe0fake-jpeg"

    missing = client.get("/media/nonexistent-id-1234")
    assert missing.status_code == 404


def test_looks_search_swipes_wishlist_and_preferences(client):
    # Update preferences including tutorial_seen flag
    pref = client.put(
        "/preferences",
        json={"user_id": "u_look", "tutorial_seen": True, "budget_max": 12000, "fit_preference": "relaxed"},
    )
    assert pref.status_code == 200
    assert pref.json()["tutorial_seen"] is True

    # Search 5-look outfit deck
    res = client.post(
        "/looks/search",
        json={"session_id": "s_look", "user_id": "u_look", "occasion": "date night", "vibe": "quiet luxury"},
    )
    assert res.status_code == 200
    looks = res.json()["looks"]
    assert len(looks) == 5

    # Right swipe ("save") adds to Wishlist and de-duplicates next search
    sw1 = client.post(
        "/swipes",
        json={"session_id": "s_look", "user_id": "u_look", "look": looks[0], "action": "save"},
    )
    assert sw1.status_code == 200
    assert sw1.json()["stats"]["wishlist"] == 1

    # Left swipe ("skip") + Up swipe ("buy_intent")
    assert client.post(
        "/swipes",
        json={"session_id": "s_look", "user_id": "u_look", "look": looks[1], "action": "skip"},
    ).status_code == 200
    assert client.post(
        "/swipes",
        json={"session_id": "s_look", "user_id": "u_look", "look": looks[2], "action": "buy_intent"},
    ).status_code == 200

    wl = client.get("/wishlist?user_id=u_look").json()["wishlist"]
    assert len(wl) == 1
    assert wl[0]["id"] == looks[0]["id"]

    # Exclude seen looks on next search
    res2 = client.post(
        "/looks/search",
        json={"session_id": "s_look", "user_id": "u_look", "occasion": "date night"},
    )
    assert res2.status_code == 200
    returned_ids = {lk["id"] for lk in res2.json()["looks"]}
    assert looks[0]["id"] not in returned_ids

    # Delete from wishlist
    del_wl = client.delete(f"/wishlist/{looks[0]['id']}?user_id=u_look")
    assert del_wl.status_code == 200
    assert del_wl.json()["saved_outfits"] == []


def test_voice_transcribe_endpoint(client):
    audio_b64 = base64.b64encode(b"fake-webm-bytes").decode()
    res = client.post("/voice/transcribe", json={"audio_base64": audio_b64, "mime_type": "audio/webm;codecs=opus"})
    assert res.status_code == 200
    assert res.json()["text"] == "Build a smart-casual date night outfit"
