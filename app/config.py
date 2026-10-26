import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Model name is configurable: check Google's current model list and set GEMINI_MODEL.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- speed knobs (see README "Performance") ---
# Gemini 3 models think by default, which adds seconds to every call. Our calls are simple (parse a message,
# word one reply), so default to the lowest level that is allowed. Values: minimal | low | medium | high,
# a token budget such as 0 for Gemini 2.5 models, or "default" to leave the model's own setting.
GEMINI_THINKING = os.getenv("GEMINI_THINKING", "low")
# Optional faster/cheaper model for message parsing and short wording (empty = use GEMINI_MODEL).
GEMINI_FAST_MODEL = os.getenv("GEMINI_FAST_MODEL", "")
# Skip the LLM for unambiguous messages ("9", "sports shoes", "hi", "yes" at a confirmation, "no thanks").
FASTPATH = os.getenv("FASTPATH", "1") != "0"
# By default only replies that carry content (results, comparisons) are worded by the LLM; plain questions
# like "what size?" use fixed text. Set PHRASE_ALL=1 to have the LLM word every reply (slower).
PHRASE_ALL = os.getenv("PHRASE_ALL", "0") == "1"
