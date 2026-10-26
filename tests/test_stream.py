import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.engine import state
from app.engine.engine import handle
from app.engine.state import SESSIONS, Session, get_session
from app.main import app, get_conn, get_conn_factory, get_llm
from tests.fakes import FakeLLM


def parse(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


@pytest.fixture
def api(conn):
    @contextmanager
    def shared():  # the test's connection must not be closed by the endpoint
        yield conn

    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_conn_factory] = lambda: shared
    SESSIONS.clear()
    yield TestClient(app), conn
    app.dependency_overrides.clear()


def stream(client, message, sid="s1", **kw):
    r = client.post("/chat/stream", json={"session_id": sid, "message": message, "user_id": "u", **kw})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    return parse(r.text)


def test_products_arrive_before_the_sentence_and_the_pieces_add_up(api):
    client, _ = api
    events = stream(client, "sports shoes, size 9")
    names = [n for n, _ in events]
    assert names[0] == "status" and names[-1] == "done" and "ui" in names and "text" in names
    assert names.index("ui") < names.index("text")                    # panel first, words after
    ui, done = dict(events)["ui"], events[-1][1]
    assert ui["ui_action"]["product_ids"] == done["ui_action"]["product_ids"] and ui["slots"]["use"] == "sports"
    assert "".join(d["delta"] for n, d in events if n == "text") == done["reply"]


def test_a_reply_with_no_products_has_no_ui_event(api):
    client, _ = api
    names = [n for n, _ in stream(client, "hi")]
    assert names == ["status", "text", "done"] or ("ui" not in names and names[-1] == "done")


def test_stream_and_plain_endpoints_give_the_same_answer(api):
    client, _ = api
    streamed = stream(client, "sports shoes, size 9", sid="a")[-1][1]
    plain = client.post("/chat", json={"session_id": "b", "message": "sports shoes, size 9", "user_id": "u"}).json()
    assert streamed["reply"] == plain["reply"] and streamed["ui_action"] == plain["ui_action"]


def test_a_failure_is_reported_as_an_event_not_a_dropped_connection(api):
    client, _ = api

    @contextmanager
    def broken():
        raise RuntimeError("db is down")
        yield

    app.dependency_overrides[get_conn_factory] = lambda: broken
    events = stream(client, "sports shoes")
    assert [n for n, _ in events] == ["error"] and "try again" in events[0][1]["message"]


def test_the_ui_hook_fires_before_the_reply_is_worded(conn):
    order = []

    class Spy(FakeLLM):
        def phrase(self, instruction, context, fallback):
            order.append("worded")
            return fallback

    handle(Session(), "sports shoes, size 9", Spy(), conn, on_ui=lambda ui, slots: order.append("ui"))
    assert order == ["ui", "worded"]


def test_the_hook_does_not_leak_into_the_next_turn(conn):
    s, seen = Session(), []
    handle(s, "sports shoes, size 9", FakeLLM(), conn, on_ui=lambda *a: seen.append(1))
    handle(s, "show more options", FakeLLM(), conn)
    assert len(seen) == 1 and s.on_ui is None


# ---- limits ----
def test_input_limits(api):
    client, _ = api
    assert client.post("/chat", json={"session_id": "x", "message": "a" * 1001}).status_code == 422
    assert client.post("/chat", json={"session_id": "x", "message": ""}).status_code == 422
    assert client.post("/chat/stream", json={"session_id": "", "message": "hi"}).status_code == 422


def test_session_store_is_bounded_and_keeps_recently_used(monkeypatch):
    SESSIONS.clear()
    monkeypatch.setattr(state, "MAX_SESSIONS", 3)
    for sid in "abc":
        get_session(sid)
    get_session("a")                 # touch a: b is now the oldest
    get_session("d")
    assert list(SESSIONS) == ["c", "a", "d"]


def test_ready_reports_what_is_missing(api, monkeypatch):
    client, _ = api
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.get("/ready").json()["llm_key"] is False
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert client.get("/ready").json()["llm_key"] is True


def test_rate_limit_returns_429_with_a_friendly_message(api, monkeypatch):
    from app import main
    client, _ = api
    monkeypatch.setattr(main, "RATE_LIMIT", 3)
    codes = [client.post("/chat", json={"session_id": "r", "message": "hi"}).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    r = client.post("/chat/stream", json={"session_id": "r", "message": "hi"})
    assert r.status_code == 429 and "slow down" in r.json()["detail"]


def test_rate_limit_can_be_turned_off(api, monkeypatch):
    from app import main
    client, _ = api
    monkeypatch.setattr(main, "RATE_LIMIT", 0)
    assert all(client.post("/chat", json={"session_id": "r", "message": "hi"}).status_code == 200 for _ in range(8))
