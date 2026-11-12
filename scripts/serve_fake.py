"""Run the FastAPI server with the offline deterministic stylist (no GEMINI_API_KEY needed)."""
from __future__ import annotations

import uvicorn

from app.main import app, set_service
from stylist_agent.offline import OfflineStylistService

set_service(OfflineStylistService())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
