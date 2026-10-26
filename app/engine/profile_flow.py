"""Profile and complexion behaviours. Replies here are fixed templates, not free LLM text.

Privacy rules enforced here and in the API:
- a photo is only analysed after explicit, one-shot consent;
- the photo itself is never stored (only the estimate, in memory, until the user confirms or cancels);
- only a user-confirmed (or user-stated) undertone/skin tone is saved;
- the user can see everything saved and delete it at any time."""
from app.catalog.search import all_colors
from app.engine.common import _resp, _sz
from app.engine.state import Session
from app.llm.schemas import Extraction
from app.profile import store
from app.profile.ranking import palette_note

LABEL = {"stated": "you told me", "confirmed": "you confirmed it", "inferred": "a guess, tell me if it's wrong"}
TITLE = {"undertone": "undertone", "skin_tone": "skin tone", "style": "style", "budget_min": "budget from",
         "budget_max": "budget up to", "liked_color": "likes", "rejected_color": "avoids"}


def save(session: Session, conn) -> None:
    if session.user_id:
        store.save_profile(conn, session.user_id, session.profile)


def view(session: Session) -> dict:
    return {
        "size": session.profile_size,
        "facts": [{"key": f.key, "value": f.value, "status": f.status} for f in session.profile.facts],
        "pending_estimate": session.pending_complexion,
    }


def show(session: Session):
    items = []
    if session.profile_size is not None:
        items.append(f"shoe size {_sz(session.profile_size)}")
    for f in session.profile.facts:
        items.append(f"{TITLE.get(f.key, f.key)} {f.value} ({LABEL.get(f.status, f.status)})")
    if not items:
        return _resp(session, "I don't have anything saved about you yet. I only save what you tell me or confirm, and I never store photos.")
    return _resp(session, "Here's what I have saved: " + "; ".join(items) + ". Say “forget my profile” to clear all of it, or tell me what to correct.")


def forget(session: Session, conn):
    if session.user_id:
        store.forget_all(conn, session.user_id)
    session.profile.clear()
    session.profile_size = None
    session.pending_complexion, session.complexion, session.consent = None, None, False
    return _resp(session, "Done. Your saved size and preferences are deleted. I never store photos.")


def update(session: Session, ex: Extraction, conn):
    notes, skipped = [], []
    if ex.undertone:
        session.profile.set("undertone", ex.undertone, "stated")
        session.pending_complexion, session.complexion = None, None
        notes.append(f"a {ex.undertone} undertone")
    if ex.skin_tone:
        session.profile.set("skin_tone", ex.skin_tone, "stated")
        notes.append(f"{ex.skin_tone} skin tone")
    if ex.style:
        session.profile.set("style", ex.style, "stated")
        notes.append(f"your style as {ex.style}")
    if ex.budget_min:
        session.profile.set("budget_min", ex.budget_min, "stated")
        notes.append(f"a budget from ₹{ex.budget_min:,}")
    if ex.budget_max:
        session.profile.set("budget_max", ex.budget_max, "stated")
        notes.append(f"a budget up to ₹{ex.budget_max:,}")
    stocked = {c.lower() for c in all_colors(conn)}
    for color, liked in ((ex.liked_color, True), (ex.disliked_color, False)):
        if not color:
            continue
        color = color.lower().strip()
        if color in stocked:
            session.profile.set_color(color, liked, "stated")
            notes.append(f"you like {color}" if liked else f"you'd rather avoid {color}")
        else:
            skipped.append(color)
    if not notes and not skipped:
        return _resp(session, "I didn't catch a preference to save. You can tell me things like your style, a color you like, or your usual budget.")
    save(session, conn)
    text = ("Noted: " + "; ".join(notes) + ".") if notes else ""
    if skipped:
        text += f" I don't stock {', '.join(skipped)}, so I haven't saved that."
    if ex.undertone:
        text += " " + palette_note(ex.undertone)
    text += " Ask “what do you know about me” to review it, or say “forget my profile” to clear it."
    return _resp(session, text.strip())


def known_note(undertone: str) -> str:
    return f"I have your undertone as {undertone}. {palette_note(undertone)} I'll weigh it when I rank items for you."


def ask_consent(session: Session):
    session.complexion, session.awaiting_confirm = "awaiting_consent", False
    return _resp(
        session,
        "I can suggest colors that tend to complement your skin tone. If you like, you can upload a photo: I'll "
        "estimate your skin tone and undertone, show you the result to confirm or correct, then delete the photo. "
        "Only what you confirm is saved, and you can say “forget my profile” any time. Want to go ahead? "
        "You can also just tell me your undertone instead.",
    )


def grant_consent(session: Session):
    session.consent, session.complexion = True, "awaiting_photo"
    return _resp(
        session,
        "Thanks. Use the upload box on the right and pick a clear, well-lit photo. I'll show you my estimate "
        "before anything is saved, and the photo is deleted as soon as it has been analysed.",
        type="request_photo",
    )


def apply_confirmed(session: Session, conn, skin_tone: str, undertone: str) -> str:
    session.profile.set("skin_tone", skin_tone, "confirmed")
    session.profile.set("undertone", undertone, "confirmed")
    session.pending_complexion, session.complexion, session.consent = None, None, False
    save(session, conn)
    return (f"Saved: {skin_tone} skin tone with a {undertone} undertone. {palette_note(undertone)} "
            "I'll weigh this when I rank items, and you can clear it any time with “forget my profile”.")
