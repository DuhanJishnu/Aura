import pytest

from app.policy.rules import RULES, Action, Situation, decide

A = Action
CASES = [
    (dict(intent="decline"), A.RESPECT_NO, "no_means_no"),
    (dict(intent="decline", engaged=True, objection="price"), A.RESPECT_NO, "no_means_no"),
    (dict(intent="off_topic"), A.ANSWER, "answer_off_topic"),
    (dict(intent="off_topic", declined=True), A.ANSWER, "answer_off_topic"),
    (dict(intent="just_looking"), A.QUIET, "just_looking"),
    (dict(intent="just_looking", declined=True), A.QUIET, "just_looking"),
    (dict(intent="other", declined=True), A.RESPECT_NO, "passive_after_no"),
    (dict(intent="greeting", declined=True), A.RESPECT_NO, "passive_after_no"),
    (dict(intent="confirm", awaiting_confirm=True, engaged=True), A.CONFIRM_ORDER, "confirm_order"),
    (dict(intent="checkout", engaged=True), A.CONFIRM_ORDER, "checkout"),
    (dict(intent="reject", engaged=True), A.REJECT_ITEM, "reject_item"),
    (dict(intent="opinion", engaged=True), A.OPINION, "opinion"),
    (dict(intent="focus", engaged=True), A.FOCUS, "focus"),
    (dict(intent="compare", engaged=True), A.COMPARE, "compare"),
    (dict(intent="object", engaged=True, objection="fit"), A.OBJECTION, "objection"),
    (dict(intent="browse", engaged=True, declined=True), A.DISCOVER, "browse"),
    (dict(intent="buy", engaged=True), A.CART_ADD, "cart"),
    (dict(intent="cart_remove", engaged=True), A.CART_REMOVE, "cart_remove"),
    (dict(intent="shopping", engaged=True, pending_ready=True), A.RESUME_CART, "resume_pending_cart"),
    (dict(intent="refine", refine="cheaper", has_shortlist=True, engaged=True), A.REFINE, "refine"),
    (dict(intent="greeting"), A.GREET, "greet"),
    (dict(intent="shopping", engaged=True, slots_empty=False, missing_slot="ask_size"), A.CLARIFY, "clarify_missing"),
    (dict(intent="shopping", engaged=True, slots_empty=False), A.RETRIEVE, "retrieve"),
    (dict(intent="confirm", awaiting_confirm=False, engaged=True), A.RETRIEVE, "retrieve"),
    (dict(intent="profile_forget", declined=True), A.FORGET_PROFILE, "forget_profile"),
    (dict(intent="profile_show", declined=True), A.SHOW_PROFILE, "show_profile"),
    (dict(intent="profile_update", declined=True), A.UPDATE_PROFILE, "update_profile"),
    (dict(intent="confirm", awaiting_consent=True, engaged=True), A.GRANT_CONSENT, "grant_consent"),
    (dict(intent="confirm", pending_complexion=True, engaged=True), A.CONFIRM_COMPLEXION, "confirm_complexion"),
    (dict(intent="complexion", engaged=True), A.COMPLEXION_START, "complexion"),
]


@pytest.mark.parametrize("kw,action,rule", CASES)
def test_policy_table(kw, action, rule):
    assert decide(Situation(**kw)) == (action, rule)


def test_every_rule_is_exercised_and_last_rule_is_catch_all():
    assert {r for _, _, r in CASES} == {r.name for r in RULES}
    assert RULES[-1].when(Situation(intent="anything"))
