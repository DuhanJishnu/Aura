import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

from app.profile.model import Profile
from app.profile.store import get_size, load_profile
from app.schemas import Slots


@dataclass
class CartItem:
    shoe_id: int
    size: float
    for_whom: str = "self"
    category: str = "shoes"


@dataclass
class Session:
    slots: Slots = field(default_factory=Slots)
    user_id: str = ""
    shortlist: list[int] = field(default_factory=list)   # ids currently on screen
    shown: list[int] = field(default_factory=list)       # ids shown for the current search ("show more")
    rejected: list[int] = field(default_factory=list)
    avoid_colors: list[str] = field(default_factory=list)
    focused_id: int | None = None
    top_pick_id: int | None = None  # the shoe the assistant put first (and usually named) on the last results
    cart: list[CartItem] = field(default_factory=list)
    profile_size: float | None = None  # saved size, written after a purchase for yourself
    pending: tuple[int, bool] | None = None  # (shoe_id, buy_now) waiting for a size
    awaiting_confirm: bool = False
    declined: bool = False
    on_ui: Callable | None = field(default=None, repr=False, compare=False)   # set per request by the streaming endpoint
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    last_reply: str = ""
    profile: Profile = field(default_factory=Profile)
    profile_loaded: bool = False
    complexion: str | None = None            # None | "awaiting_consent" | "awaiting_photo"
    consent: bool = False                        # one-shot consent to analyse one photo
    pending_complexion: dict | None = None    # unconfirmed estimate (never the photo)


MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "5000"))  # oldest-idle sessions are dropped beyond this (in-memory store)
SESSIONS: OrderedDict[str, Session] = OrderedDict()


def get_session(session_id: str, user_id: str | None = None, conn=None) -> Session:
    s = SESSIONS.get(session_id)
    if s is None:
        s = SESSIONS[session_id] = Session()
        while len(SESSIONS) > MAX_SESSIONS:
            SESSIONS.popitem(last=False)
    else:
        SESSIONS.move_to_end(session_id)
    if user_id and not s.user_id:
        s.user_id = user_id
        if conn is not None and s.profile_size is None:
            s.profile_size = get_size(conn, user_id)
        if conn is not None and not s.profile_loaded:
            s.profile, s.profile_loaded = load_profile(conn, user_id), True
    return s
