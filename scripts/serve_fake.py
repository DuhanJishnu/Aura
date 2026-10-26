"""Run the API with the keyword-matching fake LLM, so the UI can be tried or smoke-tested WITHOUT an API key.

    python -m scripts.serve_fake          # backend on :8000 (then: cd web && npm run dev)

This is not Gemini: it understands only the phrases in tests/fakes.py. It exists for UI work and automated smoke tests."""
import os

import uvicorn

from app.main import app, get_llm
from tests.fakes import FakeLLM

os.environ.setdefault("AUTO_SEED", "1")
app.dependency_overrides[get_llm] = lambda: FakeLLM()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")), log_level="warning")
