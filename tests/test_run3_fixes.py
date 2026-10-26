"""Regression tests for problems found in the third real evaluation run (seed 11, gemini-3.5-flash-lite).
The catalog here is the same deterministic seed, so shoe ids match the shoppers' screens in those transcripts."""
import pytest

from app.engine.engine import handle
from app.engine.signals import explicit_budget, is_fit_question, is_quality_question, is_take
from app.engine.state import Session
from app.llm.schemas import ComplexionEstimate, Extraction  # noqa: F401
from eval.metrics import Ctx, score
from eval.types import Conversation, Persona, Turn
from tests.fakes import FakeLLM


class GeminiLike(FakeLLM):
    def __init__(self, ex):
        self.ex = ex

    def extract(self, message, known):
        return self.ex


def start(conn, text):
    s = Session(user_id="u")
    return s, handle(s, text, FakeLLM(), conn)


# ---- signals ----
@pytest.mark.parametrize("msg,value", [
    ("something under ₹899", 899), ("my budget of ₹1,500", 1500), ("max 2000 please", 2000), ("below Rs. 3,500", 3500),
    ("size 9 under 5", None), ("I wear size 9", None), ("sports shoes please", None),
])
def test_explicit_budget(msg, value):
    assert explicit_budget(msg) == value


def test_fit_quality_and_take_patterns():
    assert is_fit_question("Do these run small at all?") and is_fit_question("will they fit me?")
    assert not is_fit_question("I want a good fit for running")
    assert is_quality_question("will it last a couple of years?") and not is_quality_question("good quality sports shoes")
    assert is_take("I'll take them in a size 9") and is_take("just process it") and not is_take("I want sports shoes")


# ---- p014: an explicit budget was ignored twice, and the agent claimed it had "lowered the price range" ----
def test_budget_stated_inside_a_price_complaint_is_applied_as_stated(conn):
    s, r = start(conn, "casual shoes, size 9")
    assert r.ui_action.product_ids == [86, 285, 158, 24, 73, 288]   # what that shopper saw
    msg = "Those look nice, but they are way too expensive for me since I'm looking for something under ₹899."
    for label in (Extraction(intent="object", objection="price"), Extraction(intent="refine", refine="cheaper")):
        s2, _ = start(conn, "casual shoes, size 9")
        r = handle(s2, msg, GeminiLike(label), conn)
        assert s2.slots.budget == 899 and r.ui_action.type == "none"
        assert "couldn't find" in r.reply and "lowered the price range" not in r.reply and "or less" not in r.reply


# ---- p006: "do these run small?" was answered by re-showing the same shoes ----
def test_fit_question_is_answered_even_when_the_llm_mislabels_it(conn):
    s, r = start(conn, "office shoes, size 11")
    assert r.ui_action.product_ids == [179, 282, 27, 141, 148, 264]
    msg = "Oh nice, I see the Hush Puppies Derby in grey comes in a size 11! Do these run small at all?"
    r = handle(s, msg, GeminiLike(Extraction(intent="shopping")), conn)
    assert r.policy["action"] == "objection" and r.ui_action.type == "focus_product" and r.ui_action.product_id == 179
    assert "don't have fit" in r.reply


# ---- p001/p002...: "I'll take it" got only "Added to cart", so nobody knew how to finish ----
def test_ill_take_it_is_a_purchase_and_asks_for_confirmation(conn):
    s, _ = start(conn, "office shoes, size 9")
    msg = "The Red Tape Oxford looks great and I'll take them in a size 9, please."
    r = handle(s, msg, GeminiLike(Extraction(intent="cart_add")), conn)
    assert r.policy["action"] == "cart_add" and s.awaiting_confirm and r.ui_action.type == "checkout"
    assert "place order" in r.reply.lower()


def test_plain_add_to_cart_still_says_how_to_finish_but_does_not_assume_a_purchase(conn):
    s, _ = start(conn, "office shoes, size 9")
    s.focused_id = s.shortlist[0]
    r = handle(s, "add it to my cart", FakeLLM(), conn)
    assert "Say “place order”" in r.reply and not s.awaiting_confirm


def test_place_order_works_any_time_the_cart_has_something(conn):
    s, _ = start(conn, "office shoes, size 9")
    s.focused_id = s.shortlist[0]
    handle(s, "add it to my cart", FakeLLM(), conn)
    r = handle(s, "place order", FakeLLM(), conn)
    assert r.policy["rule"] == "checkout" and r.ui_action.order_id


def test_an_old_offer_to_confirm_does_not_survive_an_unrelated_turn(conn):
    s, _ = start(conn, "office shoes, size 9")
    handle(s, "show me the first one", FakeLLM(), conn)
    handle(s, "buy this", FakeLLM(), conn)
    assert s.awaiting_confirm
    handle(s, "what do you think of it?", FakeLLM(), conn)
    assert not s.awaiting_confirm
    r = handle(s, "yes", FakeLLM(), conn)
    assert not r.ui_action.order_id and not s.profile_size  # a stray yes places nothing




# ---- a malformed model response must not crash the conversation ----
def test_extraction_failure_gets_a_polite_retry_prompt(conn):
    class Broken(FakeLLM):
        def extract(self, message, known):
            raise ValueError("MALFORMED_RESPONSE")

    r = handle(Session(), "I need some shoes for the monsoon", Broken(), conn)
    assert "say it again" in r.reply and r.policy["rule"] == "llm_error"


def test_client_retries_one_malformed_extraction():
    import types

    from app.llm.client import GeminiLLM
    llm, calls = GeminiLLM(api_key="x", model="m", thinking="default"), []

    def generate_content(model, contents, config):
        calls.append(1)
        text = "" if len(calls) == 1 else '{"intent": "greeting"}'
        return types.SimpleNamespace(text=text, parsed=None, usage_metadata=None)

    llm.client = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=generate_content))
    assert llm.extract("hi", {}).intent == "greeting" and len(calls) == 2


# ---- scoring: a stated price ceiling or an order total is not an invented price ----
def test_ceiling_and_order_total_are_not_hallucinations(conn):
    p = Persona("x", "price_objection", "sports", 9.0, None, "self", "price", "x", None, "")
    turns = [Turn("user", "too expensive"),
             Turn("assistant", "Here are cheaper ones. Everything shown is ₹4,559 or less.", shown_ids=[168], amounts=[4559]),
             Turn("assistant", "Order confirmed, total ₹7,198.")]
    orders = [{"shoe_id": 1, "size": 9.0, "price": 3599, "use_type": "sports"}, {"shoe_id": 2, "size": 9.0, "price": 3599, "use_type": "sports"}]
    s = score(Conversation(p, "agent", turns, {"outcome": "buy"}, orders=orders), Ctx(conn))
    assert s["hallucinated"] is False
    turns[1] = Turn("assistant", "Everything shown is ₹4,559 or less.")          # same sentence without the recorded ceiling
    assert score(Conversation(p, "agent", turns, {"outcome": "buy"}), Ctx(conn))["hallucinated"] is True


# ---- a plain "no thanks" is always a no ----
def test_explicit_decline_detection():
    from app.engine.signals import explicit_decline
    assert explicit_decline("No thanks, I'm just browsing around for today") and explicit_decline("not interested, thanks")
    assert not explicit_decline("no thanks, but show me sports shoes") and not explicit_decline("I want sports shoes")


@pytest.mark.parametrize("label", [Extraction(intent="browse"), Extraction(intent="other"), Extraction(intent="shopping"),
                                   Extraction(intent="off_topic")])
def test_no_thanks_wins_even_when_the_llm_says_browsing(conn, label):
    s = Session(user_id="u")
    r = handle(s, "No thanks, I'm just browsing around for today", GeminiLike(label), conn)
    assert r.policy["rule"] == "no_means_no" and r.ui_action.type == "none" and "?" not in r.reply and s.declined


def test_a_no_with_a_new_request_is_left_to_the_llm(conn):
    s, _ = start(conn, "sports shoes, size 9")
    r = handle(s, "no thanks, but show me something cheaper", GeminiLike(Extraction(intent="refine", refine="cheaper")), conn)
    assert r.policy["rule"] != "no_means_no"


def test_show_tool_renders_a_conversation(tmp_path):
    from eval.show import render
    from eval.types import Conversation, Persona, Turn
    p = Persona("p9", "rejection", None, None, None, "self", None, "hi", None, "")
    out = render(Conversation(p, "agent", [Turn("user", "hi"), Turn("assistant", "Hello", rule="greet")]), False)
    assert "[FAILED]" in out and "rule=greet" in out and "U: hi" in out


# ---- run 4: "just browsing, thanks" is a brush-off, not a request to be shown things ----
def test_just_looking_detection():
    from app.engine.signals import is_just_looking
    for msg in ("Hi, just browsing today, thanks!", "Thanks, just browsing.", "just looking around"):
        assert is_just_looking(msg), msg
    for msg in ("just browsing, surprise me", "I'm bored, just looking", "just looking around out of boredom, I guess",
                "just browsing, what do you have?", "just looking for sports shoes", "I want sports shoes"):
        assert not is_just_looking(msg), msg


def test_run4_p012_a_no_then_just_browsing_gets_no_products(conn):
    """The failing transcript: 'Hi, just looking around today, no thanks.' then 'Thanks, just browsing.'"""
    s = Session(user_id="u")
    r1 = handle(s, "Hi, just looking around today, no thanks.", GeminiLike(Extraction(intent="browse")), conn)
    assert r1.policy["rule"] == "no_means_no" and s.declined and r1.ui_action.type == "none"
    r2 = handle(s, "Thanks, just browsing.", GeminiLike(Extraction(intent="browse")), conn)
    assert r2.policy["rule"] == "just_looking" and r2.ui_action.type == "none" and r2.ui_action.product_ids == []
    assert "?" not in r2.reply and "show me something" not in r2.reply   # after a no: quiet, not even an offer
    assert s.declined


def test_run4_p004_just_browsing_first_offers_without_pushing(conn):
    s = Session(user_id="u")
    r = handle(s, "Hi, just browsing today, thanks!", GeminiLike(Extraction(intent="browse")), conn)
    assert r.policy["rule"] == "just_looking" and r.ui_action.type == "none" and not s.declined
    assert "show me something" in r.reply and "?" not in r.reply
    r = handle(s, "No thanks, I'm just looking around.", GeminiLike(Extraction(intent="browse")), conn)
    assert r.policy["rule"] == "no_means_no" and s.declined


@pytest.mark.parametrize("msg", ["I'm bored, show me something", "just browsing, surprise me",
                                 "Just looking around out of boredom, I guess."])
def test_an_actual_invitation_still_browses(conn, msg):
    r = handle(Session(), msg, GeminiLike(Extraction(intent="browse")), conn)
    assert r.policy["action"] == "discover" and r.ui_action.type == "show_products"


def test_the_same_sentence_is_never_said_twice_in_a_row(conn):
    s = Session(user_id="u")
    a = handle(s, "no thanks", FakeLLM(), conn).reply
    b = handle(s, "actually I'm all set, no thanks", GeminiLike(Extraction(intent="decline")), conn).reply
    assert a != b and "?" not in b
    s2 = Session(user_id="u")
    x = handle(s2, "office shoes size 11 under 100", FakeLLM(), conn).reply
    y = handle(s2, "office shoes size 11 under 100", FakeLLM(), conn).reply
    assert "couldn't find" in x and x != y and "nothing in stock" in y
