"""Gemini client for evaluation runs: same wrapper as the app, plus retry/backoff for rate limits."""
import time

from app.llm.client import GeminiLLM


class EvalGemini(GeminiLLM):
    def _generate(self, *args, **kwargs):
        delay = 2.0
        for attempt in range(5):
            try:
                return super()._generate(*args, **kwargs)
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(delay)
                delay *= 2
