import base64

import pytest
from fastapi.testclient import TestClient

from app.engine.engine import handle
from app.engine.state import SESSIONS, Session
from app.main import app, get_conn, get_llm
from app.profile import store
from tests.fakes import FakeLLM

PHOTO = base64.b64encode(b"\xff\xd8\xff fake-jpeg-bytes " * 50).decode()


@pytest.fixture
def api(conn):
    llm = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_conn] = lambda: conn
    SESSIONS.clear()
    yield TestClient(app), llm, conn
    app.dependency_overrides.clear()


def body(**kw):
    return {"session_id": "s1", "user_id": "u1", **kw}


def test_analysis_requires_consent(api):
    client, llm, _ = api
    r = client.post("/complexion/analyze", json=body(image_base64=PHOTO, mime_type="image/jpeg"))
    assert r.status_code == 403 and not hasattr(llm, "seen_image")


def test_full_flow_estimate_is_not_saved_until_confirmed_and_photo_is_not_kept(api):
    client, llm, conn = api
    client.post("/complexion/consent", json=body())
    est = client.post("/complexion/analyze", json=body(image_base64=PHOTO, mime_type="image/jpeg")).json()["estimate"]
    assert est["undertone"] == "warm" and llm.seen_image  # the model got the bytes...
    assert store.load_profile(conn, "u1").facts == []     # ...but nothing is saved yet
    session = SESSIONS["s1"]
    assert PHOTO not in repr(session.__dict__) and b"fake-jpeg" not in repr(session.__dict__).encode()
    # the user corrects the estimate; the corrected values are what get saved
    r = client.post("/complexion/confirm", json=body(skin_tone="deep", undertone="cool")).json()
    assert "cool undertone" in r["message"] and "tend to complement cool" in r["message"]
    saved = {(f.key, f.value, f.status) for f in store.load_profile(conn, "u1").facts}
    assert saved == {("undertone", "cool", "confirmed"), ("skin_tone", "deep", "confirmed")}
    assert session.pending_complexion is None


def test_consent_covers_one_photo_only(api):
    client, _, _ = api
    client.post("/complexion/consent", json=body())
    client.post("/complexion/analyze", json=body(image_base64=PHOTO, mime_type="image/jpeg"))
    again = client.post("/complexion/analyze", json=body(image_base64=PHOTO, mime_type="image/jpeg"))
    assert again.status_code == 403


def test_bad_uploads_rejected_and_cancel_discards(api):
    client, _, conn = api
    client.post("/complexion/consent", json=body())
    assert client.post("/complexion/analyze", json=body(image_base64=PHOTO, mime_type="application/pdf")).status_code == 400
    client.post("/complexion/consent", json=body())
    assert client.post("/complexion/analyze", json=body(image_base64="not base64!!", mime_type="image/png")).status_code == 400
    client.post("/complexion/consent", json=body())
    client.post("/complexion/analyze", json=body(image_base64=PHOTO, mime_type="image/png"))
    client.post("/complexion/cancel", json=body())
    assert client.post("/complexion/confirm", json=body(skin_tone="fair", undertone="warm")).status_code == 409
    assert store.load_profile(conn, "u1").facts == []


def test_forget_endpoint_clears_everything(api):
    client, _, conn = api
    client.post("/complexion/consent", json=body())
    client.post("/complexion/analyze", json=body(image_base64=PHOTO, mime_type="image/jpeg"))
    client.post("/complexion/confirm", json=body(skin_tone="medium", undertone="warm"))
    store.save_size(conn, "u1", 9.0)
    r = client.post("/profile/forget", json=body()).json()
    assert r["profile"]["facts"] == [] and store.load_profile(conn, "u1").facts == [] and store.get_size(conn, "u1") is None


# ---- through chat ----
def chat(conn, s, text):
    return handle(s, text, FakeLLM(), conn)


def test_chat_asks_consent_first_then_unlocks_upload(conn):
    s = Session(user_id="u1")
    r = chat(conn, s, "which colors suit my skin tone?")
    assert s.complexion == "awaiting_consent" and "Want to go ahead?" in r.reply and not s.consent
    assert "delete the photo" in r.reply and r.ui_action.type == "none"
    r = chat(conn, s, "yes")
    assert s.consent and r.ui_action.type == "request_photo" and r.policy["rule"] == "grant_consent"


def test_declining_consent_cancels_and_is_respected(conn):
    s = Session(user_id="u1")
    chat(conn, s, "which colors suit my skin tone?")
    r = chat(conn, s, "no thanks")
    assert s.complexion is None and not s.consent and "?" not in r.reply
    assert chat(conn, s, "yes").policy["rule"] == "passive_after_no"
    assert not s.consent


def test_stating_undertone_needs_no_photo_and_gets_soft_advice(conn):
    s = Session(user_id="u1")
    r = chat(conn, s, "I have a warm undertone")
    assert s.profile.get("undertone").status == "stated" and "tend to complement warm" in r.reply
    assert [f.key for f in store.load_profile(conn, "u1").facts] == ["undertone"]


def test_chat_can_confirm_a_pending_estimate(conn):
    s = Session(user_id="u1", pending_complexion={"skin_tone": "light", "undertone": "neutral", "confidence": "high", "note": ""})
    r = chat(conn, s, "yes")
    assert r.policy["rule"] == "confirm_complexion" and s.profile.get("undertone").status == "confirmed"


def test_correcting_a_pending_estimate_in_words_replaces_it(conn):
    s = Session(user_id="u1", pending_complexion={"skin_tone": "light", "undertone": "warm", "confidence": "low", "note": ""})
    chat(conn, s, "I have a cool undertone")
    assert s.pending_complexion is None and s.profile.value("undertone") == "cool"


def test_known_undertone_is_reused_not_reasked(conn):
    s = Session(user_id="u1")
    chat(conn, s, "I have a warm undertone")
    r = chat(conn, s, "which colors suit my skin tone?")
    assert s.complexion is None and "I have your undertone as warm" in r.reply


def test_forget_profile_works_even_after_a_no_and_asks_nothing(conn):
    s = Session(user_id="u1", profile_size=9.0)
    chat(conn, s, "I have a warm undertone")
    store.save_size(conn, "u1", 9.0)
    chat(conn, s, "no thanks")
    r = chat(conn, s, "forget my profile")
    assert r.policy["rule"] == "forget_profile" and "deleted" in r.reply and "?" not in r.reply
    assert s.profile.facts == [] and s.profile_size is None
    assert store.load_profile(conn, "u1").facts == [] and store.get_size(conn, "u1") is None


def test_profile_updates_are_saved_quietly_after_a_no(conn):
    s = Session(user_id="u1")
    chat(conn, s, "no thanks")
    r = chat(conn, s, "I like olive")
    assert "?" not in r.reply and r.ui_action.type == "none" and s.declined
    assert s.profile.values("liked_color")[0].status == "stated"


def test_show_profile_marks_guesses(conn):
    s = Session(user_id="u1")
    s.profile.set_color("black", True, "inferred")
    s.profile.set("undertone", "warm", "confirmed")
    r = chat(conn, s, "what do you know about me?")
    assert "a guess, tell me if it's wrong" in r.reply and "you confirmed it" in r.reply


def test_purchase_adds_only_a_tentative_guess_that_can_be_corrected(conn):
    s = Session(user_id="u1")
    for msg in ("sports shoes, size 9", "show me the first one", "buy this"):
        r = chat(conn, s, msg)
    r = chat(conn, s, "yes, place the order")
    liked = s.profile.values("liked_color")
    assert liked and liked[0].status == "inferred" and "tentatively" in r.reply
    color = liked[0].value
    chat(conn, s, f"i don't like {color}")  # the user corrects the guess
    assert not s.profile.values("liked_color")
    assert s.profile.values("rejected_color")[0].status == "stated"


def test_unstocked_color_is_not_saved(conn):
    s = Session(user_id="u1")
    r = chat(conn, s, "I like pink")
    assert "don't stock pink" in r.reply and not s.profile.facts


def test_style_changes_what_browsing_leads_with(conn):
    plain = chat(conn, Session(), "I'm bored")
    s = Session()
    chat(conn, s, "my style is classic")
    classic = chat(conn, s, "I'm bored")
    from app.catalog.search import get_shoes_by_ids
    count = lambda r: sum(x["use_type"] == "office" for x in get_shoes_by_ids(conn, r.ui_action.product_ids))  # noqa: E731
    assert count(classic) == count(plain) + 1
