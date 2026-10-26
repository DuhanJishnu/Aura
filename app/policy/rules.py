"""Decision policy as a rule table: situation -> action. First matching rule wins.

Kept as plain data so it is easy to read, test, log (every reply reports the rule that fired) and
later replace with another decision layer, while this table stays as the baseline for evaluation."""
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class Action(StrEnum):
    RESPECT_NO = "respect_no"
    ANSWER = "answer"
    CONFIRM_ORDER = "confirm_order"
    REJECT_ITEM = "reject_item"
    OPINION = "opinion"
    FOCUS = "focus"
    COMPARE = "compare"
    OBJECTION = "objection"
    DISCOVER = "discover"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    RESUME_CART = "resume_cart"
    REFINE = "refine"
    GREET = "greet"
    CLARIFY = "clarify"
    RETRIEVE = "retrieve"
    QUIET = "quiet"
    FORGET_PROFILE = "forget_profile"
    SHOW_PROFILE = "show_profile"
    UPDATE_PROFILE = "update_profile"
    GRANT_CONSENT = "grant_consent"
    CONFIRM_COMPLEXION = "confirm_complexion"
    COMPLEXION_START = "complexion_start"


@dataclass(frozen=True)
class Situation:
    intent: str
    refine: str | None = None
    objection: str | None = None
    declined: bool = False          # user said no earlier and has not re-engaged since
    engaged: bool = False           # this message carries explicit shopping content
    awaiting_confirm: bool = False
    has_shortlist: bool = False
    has_focus: bool = False
    slots_empty: bool = True
    missing_slot: str | None = None
    awaiting_consent: bool = False   # photo-analysis consent was just asked for
    pending_complexion: bool = False  # an unconfirmed estimate is waiting for the user
    pending_ready: bool = False     # a cart add was waiting for a size and we now have one


@dataclass(frozen=True)
class Rule:
    name: str
    when: Callable[[Situation], bool]
    action: Action
    note: str


RULES: list[Rule] = [
    Rule("no_means_no", lambda s: s.intent == "decline", Action.RESPECT_NO,
         "An explicit no always wins over everything else in the message."),
    Rule("answer_off_topic", lambda s: s.intent == "off_topic", Action.ANSWER,
         "Answer briefly, change nothing, do not pitch."),
    Rule("forget_profile", lambda s: s.intent == "profile_forget", Action.FORGET_PROFILE,
         "Delete saved size and preferences on request, always, even after a no."),
    Rule("show_profile", lambda s: s.intent == "profile_show", Action.SHOW_PROFILE,
         "Show everything saved, marking guesses as guesses."),
    Rule("update_profile", lambda s: s.intent == "profile_update", Action.UPDATE_PROFILE,
         "Save what the user states, never pitch."),
    Rule("just_looking", lambda s: s.intent == "just_looking", Action.QUIET,
         "\"Just browsing, thanks\": stay quiet, show nothing, leave the door open."),
    Rule("passive_after_no", lambda s: s.declined and not s.engaged, Action.RESPECT_NO,
         "After a no, small talk gets a quiet reply with no question and no products."),
    Rule("grant_consent", lambda s: s.intent == "confirm" and s.awaiting_consent, Action.GRANT_CONSENT,
         "A yes to the photo-consent question unlocks one upload."),
    Rule("confirm_complexion", lambda s: s.intent == "confirm" and s.pending_complexion, Action.CONFIRM_COMPLEXION,
         "A yes to an estimate saves it as confirmed."),
    Rule("confirm_order", lambda s: s.intent == "confirm" and s.awaiting_confirm, Action.CONFIRM_ORDER,
         "A yes only places an order when one was just offered."),
    Rule("checkout", lambda s: s.intent == "checkout", Action.CONFIRM_ORDER,
         "An explicit 'place order' / 'check out' is itself the confirmation."),
    Rule("reject_item", lambda s: s.intent == "reject", Action.REJECT_ITEM,
         "Drop that shoe, acknowledge, do not push alternatives."),
    Rule("opinion", lambda s: s.intent == "opinion", Action.OPINION, "Honest, data-only opinion."),
    Rule("focus", lambda s: s.intent == "focus", Action.FOCUS, "Open one shoe."),
    Rule("compare", lambda s: s.intent == "compare", Action.COMPARE, "Side by side with plain trade-offs."),
    Rule("objection", lambda s: s.intent == "object", Action.OBJECTION,
         "Price, fit or quality concern: answer with evidence, alternatives or honest gaps."),
    Rule("complexion", lambda s: s.intent == "complexion", Action.COMPLEXION_START,
         "Use a saved undertone, or ask for consent before any photo analysis."),
    Rule("browse", lambda s: s.intent == "browse", Action.DISCOVER,
         "Vague interest: offer a relaxed look around, ask nothing."),
    Rule("cart", lambda s: s.intent in ("buy", "cart_add"), Action.CART_ADD, "Add to cart; buy asks for confirmation."),
    Rule("cart_remove", lambda s: s.intent == "cart_remove", Action.CART_REMOVE, "Remove from cart."),
    Rule("resume_pending_cart", lambda s: s.pending_ready, Action.RESUME_CART,
         "Finish the cart add that was waiting for a size."),
    Rule("refine", lambda s: s.intent == "refine" and bool(s.refine) and s.has_shortlist, Action.REFINE,
         "Cheaper / other colors / show more by updating filters."),
    Rule("greet", lambda s: s.intent == "greeting" and s.slots_empty, Action.GREET, "Greet and ask the first question."),
    Rule("clarify_missing", lambda s: s.missing_slot is not None, Action.CLARIFY, "Ask exactly one missing question."),
    Rule("retrieve", lambda s: True, Action.RETRIEVE, "Enough information: search and show products."),
]


def decide(situation: Situation) -> tuple[Action, str]:
    for rule in RULES:
        if rule.when(situation):
            return rule.action, rule.name
    raise AssertionError("unreachable: the last rule always matches")
