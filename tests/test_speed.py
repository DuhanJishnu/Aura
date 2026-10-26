"""The speed work must make easy cases faster without changing what happens."""
import re
import types

import pytest

from app import config
from app.engine.engine import handle
from app.engine.state import Session
from app.llm.client import GeminiLLM
from app.llm.fastpath import fastpath
from tests.fakes import FakeLLM

EMPTY = {"slots": {}}


# ---- fast path ----
@pytest.mark.parametrize("msg,field,value", [
    ("9", "size", 9.0), ("size 9.5", "size", 9.5), ("UK 10", "size", 10.0),
    ("sports shoes", "use", "sports"), ("Casual", "use", "casual"), ("office shoes", "use", "office"),
    ("for me", "for_whom", "self"), ("for someone else", "for_whom", "other"),
])
def test_simple_answers_skip_the_llm(msg, field, value):
    assert getattr(fastpath(msg, EMPTY), field) == value


@pytest.mark.parametrize("msg", ["hi", "Hello!", "hey", "good morning"])
def test_greetings(msg):
    assert fastpath(msg, EMPTY).intent == "greeting"


@pytest.mark.parametrize("msg", ["no thanks", "No thank you.", "not interested", "never mind", "no thanks, too pricey"])
def test_short_explicit_no_is_decline(msg):
    assert fastpath(msg, EMPTY).intent == "decline"


def test_yes_only_counts_when_something_is_waiting():
    assert fastpath("yes", EMPTY) is None and fastpath("place order", EMPTY) is None
    for flag in ("awaiting_order_confirmation", "awaiting_photo_consent", "pending_complexion_estimate"):
        assert fastpath("yes, place the order", {**EMPTY, flag: True}).intent == "confirm"


@pytest.mark.parametrize("msg,known", [
    ("I need sports shoes size 9 under 5000", EMPTY),           # more than one thing: let the LLM parse it
    ("9", {"slots": {"size": 8.0}}),                            # a size is already known: a number may mean something else
    ("3", EMPTY), ("1999", EMPTY),                              # not shoe sizes
    ("sports shoes please, but cheaper", EMPTY),
    ("no", EMPTY), ("no thanks, I want sports shoes in size 9 for my brother actually", EMPTY),
    ("what do you think of the second one, honestly, is it worth it?", EMPTY),
])
def test_anything_else_goes_to_the_llm(msg, known):
    assert fastpath(msg, known) is None


@pytest.mark.parametrize("msg,intent,extra", [
    ("show me the second one", "focus", {"product_index": 2}),
    ("what do you think of it?", "opinion", {"product_index": None}),
    ("what do you think of the third one", "opinion", {"product_index": 3}),
    ("compare the first and third", "compare", {"compare_indices": [1, 3]}),
    ("buy this", "buy", {}), ("I'll take it", "buy", {}),
    ("show me something cheaper", "refine", {"refine": "cheaper"}), ("show more options", "refine", {"refine": "show_more"}),
    ("any other colors?", "refine", {"refine": "other_colors"}),
])
def test_common_shopping_commands_skip_the_llm(msg, intent, extra):
    ex = fastpath(msg, EMPTY)
    assert ex.intent == intent and all(getattr(ex, k) == v for k, v in extra.items())


def test_place_order_is_checkout_only_when_the_cart_has_something():
    assert fastpath("place order", {**EMPTY, "items_in_cart": 1}).intent == "checkout"
    assert fastpath("place order", EMPTY) is None


def test_profile_commands():
    assert fastpath("forget my profile", EMPTY).intent == "profile_forget"
    assert fastpath("what do you know about me?", EMPTY).intent == "profile_show"


class CountingLLM(FakeLLM):
    def __init__(self):
        self.extracts, self.phrases = 0, []

    def extract(self, message, known):
        self.extracts += 1
        return super().extract(message, known)

    def phrase(self, instruction, context, fallback):
        self.phrases.append(instruction)
        return fallback


def test_a_whole_happy_path_start_needs_no_extraction_call(conn):
    llm, s = CountingLLM(), Session(user_id="u")
    for msg in ("hi", "sports shoes", "for me"):
        handle(s, msg, llm, conn)
    r = handle(s, "9", llm, conn)
    assert llm.extracts == 0 and r.ui_action.type == "show_products" and r.policy["fast"] is True
    assert r.slots.use == "sports" and r.slots.size == 9.0 and r.slots.for_whom == "self"


def test_fast_and_slow_paths_agree(conn, monkeypatch):
    def run(fast):
        monkeypatch.setattr(config, "FASTPATH", fast)
        s, out = Session(user_id="u"), []
        for msg in ("hi", "sports shoes", "for me", "9", "show me the first one", "buy this", "yes, place the order"):
            r = handle(s, msg, FakeLLM(), conn)
            out.append((re.sub(r"ORD-[0-9A-F]{8}", "ORD-X", r.reply), r.ui_action.type, r.ui_action.product_ids, bool(r.ui_action.order_id)))
        return [(a, b, c) for a, b, c, _ in out], out[-1][3]

    assert run(True) == run(False)


def test_confirmation_and_no_use_no_extraction_either(conn):
    llm, s = CountingLLM(), Session(user_id="u")
    handle(s, "sports shoes, size 9", llm, conn)
    handle(s, "show me the first one", llm, conn)
    handle(s, "buy this", llm, conn)
    before = llm.extracts
    r = handle(s, "yes", llm, conn)
    assert llm.extracts == before and r.ui_action.order_id
    r = handle(s, "no thanks", llm, conn)
    assert llm.extracts == before and r.policy["rule"] == "no_means_no"


# ---- plain questions are not sent to the LLM ----
def test_plain_questions_use_fixed_text_but_results_are_worded_by_the_llm(conn):
    llm, s = CountingLLM(), Session()
    handle(s, "hi", llm, conn)
    handle(s, "sports", llm, conn)
    assert llm.phrases == []                                  # greet + "what size?" etc: no LLM wording
    handle(s, "9", llm, conn)
    assert len(llm.phrases) == 1 and "top_picks" in llm.phrases[0] or len(llm.phrases) == 1


def test_phrase_all_switch_restores_llm_wording(conn, monkeypatch):
    monkeypatch.setattr(config, "PHRASE_ALL", True)
    llm = CountingLLM()
    handle(Session(), "hello", llm, conn)
    assert len(llm.phrases) == 1


# ---- thinking configuration ----
def client(model, thinking):
    return GeminiLLM(api_key="x", model=model, thinking=thinking)


def test_gemini3_gets_a_thinking_level_and_gemini25_a_budget():
    tc = client("gemini-3.8-flash", "low")._thinking_config("gemini-3.8-flash")
    assert str(tc.thinking_level).upper().endswith("LOW") and tc.thinking_budget is None
    tc = client("gemini-2.5-flash", "low")._thinking_config("gemini-2.5-flash")
    assert tc.thinking_budget == 0 and tc.thinking_level is None
    assert client("gemini-2.5-pro", "low")._thinking_config("gemini-2.5-pro").thinking_budget == 128
    assert client("gemini-2.5-flash", "512")._thinking_config("gemini-2.5-flash").thinking_budget == 512
    assert client("gemini-3.8-flash", "default")._thinking_config("gemini-3.8-flash") is None


def fake_resp():
    meta = types.SimpleNamespace(prompt_token_count=100, candidates_token_count=10, thoughts_token_count=40)
    return types.SimpleNamespace(text="hi", parsed=None, usage_metadata=meta)


def test_a_model_that_rejects_the_thinking_setting_is_retried_without_it_once():
    llm, seen = client("gemini-3.8-flash", "low"), []

    def generate_content(model, contents, config):
        seen.append(config.thinking_config)
        if config.thinking_config is not None:
            raise RuntimeError("400 INVALID_ARGUMENT: thinking level not supported for this model")
        return fake_resp()

    llm.client = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=generate_content))
    llm._generate("x", "sys", 0.0)
    llm._generate("y", "sys", 0.0)
    assert seen[0] is not None and seen[1] is None and seen[2] is None   # retried once, then stopped sending it
    assert llm.usage == {"calls": 2, "in": 200, "out": 20, "thought": 80}


def test_other_errors_are_not_swallowed():
    llm = client("gemini-3.8-flash", "low")

    def boom(model, contents, config):
        raise RuntimeError("429 spending cap")

    llm.client = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=boom))
    with pytest.raises(RuntimeError, match="429"):
        llm._generate("x", "sys", 0.0)


def test_parsing_and_short_wording_use_the_fast_model_but_opinions_do_not():
    llm = GeminiLLM(api_key="x", model="big", fast_model="small", thinking="default")
    used = []

    def generate_content(model, contents, config):
        used.append(model)
        return fake_resp()

    llm.client = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=generate_content))
    llm.phrase("i", {}, "fb")
    llm.answer_offtopic("q")
    llm.opinion({"name": "x"}, "q")
    assert used == ["small", "small", "big"]
