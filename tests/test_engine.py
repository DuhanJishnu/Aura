import pytest
from fastapi.testclient import TestClient

from app.catalog.db import connect
from app.engine.engine import handle
from app.engine.state import SESSIONS, Session
from app.main import app, get_conn, get_llm
from data.seed import seed
from tests.fakes import FakeLLM


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "t.db"
    seed(path=path)
    c = connect(path)
    yield c
    c.close()


def run(conn, session, text):
    return handle(session, text, FakeLLM(), conn)


def test_happy_path_asks_one_question_at_a_time(conn):
    s = Session()
    assert run(conn, s, "hi").ui_action.type == "none"
    r = run(conn, s, "I want sports shoes")
    assert "for you" in r.reply and r.ui_action.type == "none"
    r = run(conn, s, "for me")
    assert "size" in r.reply
    r = run(conn, s, "9")
    assert r.ui_action.type == "show_products"
    assert r.ui_action.filters == {"use": "sports", "size": 9.0}


def test_size_up_front_skips_questions(conn):
    r = run(conn, Session(), "sports shoes, size 9")
    assert r.ui_action.type == "show_products"
    assert r.slots.for_whom == "self"


def test_saved_profile_size_is_used(conn):
    s = Session(profile_size=8.0)
    r = run(conn, s, "office shoes")
    assert r.ui_action.filters["size"] == 8.0


def test_other_person_size_ignores_and_keeps_profile(conn):
    s = Session(profile_size=8.0)
    r = run(conn, s, "casual shoes for my brother")
    assert "size" in r.reply and r.ui_action.type == "none"
    r = run(conn, s, "10")
    assert r.ui_action.filters["size"] == 10.0
    assert s.profile_size == 8.0


def test_change_of_mind_updates_filters_without_restart(conn):
    s = Session()
    run(conn, s, "sports shoes, size 9")
    r = run(conn, s, "actually office")
    assert r.ui_action.filters["use"] == "office" and r.ui_action.filters["size"] == 9.0


def test_off_topic_answers_and_keeps_state(conn):
    s = Session()
    run(conn, s, "sports shoes")
    r = run(conn, s, "what's the weather like?")
    assert r.ui_action.type == "none" and s.slots.use == "sports"


def test_no_thanks_backs_off(conn):
    s = Session()
    run(conn, s, "sports shoes")
    r = run(conn, s, "no thanks")
    assert s.declined and "?" not in r.reply and r.ui_action.type == "none"


def test_no_results_is_honest(conn):
    r = run(conn, Session(), "office shoes size 9 under 10")
    assert r.ui_action.type == "none" and "couldn't find" in r.reply


def test_chat_endpoint_end_to_end(conn):
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    app.dependency_overrides[get_conn] = lambda: conn
    SESSIONS.clear()
    try:
        c = TestClient(app)
        r = c.post("/chat", json={"session_id": "x", "message": "sports shoes, size 9"}).json()
        assert r["ui_action"]["type"] == "show_products"
    finally:
        app.dependency_overrides.clear()
