import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
if GEMINI_API_KEY and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE"))

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_MODEL_FALLBACK = os.getenv("GEMINI_MODEL_FALLBACK", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_SEARCH_MODEL = os.getenv("GEMINI_SEARCH_MODEL", GEMINI_MODEL).strip() or GEMINI_MODEL
GEMINI_SEARCH_MODEL_FALLBACK = (
    os.getenv("GEMINI_SEARCH_MODEL_FALLBACK", GEMINI_MODEL_FALLBACK).strip() or GEMINI_MODEL_FALLBACK
)
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-lite-image").strip() or "gemini-3.1-flash-lite-image"
GEMINI_IMAGE_MODEL_FALLBACK = (
    os.getenv("GEMINI_IMAGE_MODEL_FALLBACK", "gemini-2.5-flash-image").strip() or "gemini-2.5-flash-image"
)
GEMINI_LIVE_MODEL = (
    os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025").strip()
    or "gemini-2.5-flash-native-audio-preview-12-2025"
)
GEMINI_LIVE_MODEL_FALLBACK = (
    os.getenv("GEMINI_LIVE_MODEL_FALLBACK", "gemini-2.0-flash-live-001").strip()
    or "gemini-2.0-flash-live-001"
)
GEMINI_LIVE_VOICE = os.getenv("GEMINI_LIVE_VOICE", "Aoede").strip() or "Aoede"
GEMINI_THINKING = os.getenv("GEMINI_THINKING", "low").strip() or "low"

DEFAULT_REGION = os.getenv("DEFAULT_REGION", "India").strip() or "India"
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "INR").strip() or "INR"

RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
TRUST_PROXY = os.getenv("TRUST_PROXY", "0") == "1"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
PROFILE_STORE_DIR = Path(os.getenv("PROFILE_STORE_DIR", str(ROOT_DIR / "data" / "profiles")))
AURA_DB_PATH = Path(os.getenv("AURA_DB_PATH", str(ROOT_DIR / "data" / "aura.db")))
SEARCH_CACHE_TTL_SEC = int(os.getenv("SEARCH_CACHE_TTL_SEC", "900"))
LIVE_WS_MAX_SECONDS = int(os.getenv("LIVE_WS_MAX_SECONDS", "300"))
MEDIA_MAX_ENTRIES = int(os.getenv("MEDIA_MAX_ENTRIES", "250"))
MEDIA_SIGNING_SECRET = os.getenv("MEDIA_SIGNING_SECRET", "").strip()
STRICT_AUTH = os.getenv("AURA_STRICT_AUTH", "0") == "1"
APP_NAME = "shopper_stylist"
