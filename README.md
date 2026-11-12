# Aura — Google ADK AI Fashion Stylist

An AI personal fashion stylist and style-savvy friend built on the **Google Agent Development Kit (`google-adk`)** — **with zero database**. Aura searches real buyable clothes, shoes, and accessories online using **Google Search grounding**, builds head-to-toe **Outfit Lookbooks**, learns your taste through a **Tinder/Instagram-style Swipe Deck**, and talks with you in real time over **Gemini Live bidirectional voice**.

## What it does

- **Live Online Fashion Discovery (No DB)**: Uses an ADK Google Search sub-agent (`google_search` + `grounding_metadata`) to find real items online across retailers with verified links or clean search fallbacks — never fake catalog rows.
- **Tinder / Instagram Swipe Deck**: Swipe Right (`♥ Save`), Swipe Left (`✕ Pass`), or Swipe Up (`★ Style This`) on search results. Every swipe trains your **Style DNA** (aesthetic affinity weights, color palette, brand preferences, and exclusion list) to sharpen future recommendations.
- **Head-to-Toe Outfit Lookbooks**: Curates cohesive multi-piece outfits (Top, Bottom, Outerwear, Footwear, Accessory) using the 60-30-10 color rule, proportion balance, styling hacks, and pieces from your **Saved Closet**.
- **Friend-First + Fashion Circle-Back**: Ask off-topic questions (recipes, work stress, random chat) and Aura replies warmly like a real friend before naturally circling back to fashion and styling.
- **Strict Boundary Respect ("No Means No")**: Say `"no thanks"` or `"stop"` and Aura immediately backs off — zero pitching or circle-backs until you ask about style again.
- **Gemini Live Voice + Browser Mic Fallback**: Full-duplex real-time voice via ADK `Runner.run_live()` (`StreamingMode.BIDI` WebSocket) plus Web Speech API fallback.
- **Consent-First Photo Studio**: Upload a photo (never stored on disk/session) for either **Seasonal Color & Undertone Analysis** or **Rate My Outfit / Style Check**.
- **100% Free-Tier Deployable**: Zero database, zero paid search APIs — you only pay for your Gemini API key.

## Quick start

Python 3.11+, Node 20+, and a Gemini API key from [Google AI Studio](https://aistudio.google.com/).

```bash
# 1. Backend
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q                            # free offline tests (no API key needed)

cp .env.example .env                 # set GEMINI_API_KEY
uvicorn app.main:app --reload        # API + Live WS on http://localhost:8000

# 2. Frontend (second terminal)
cd web
npm install
npm run dev                          # open http://localhost:3000
```

### Key-less demo mode (no API key required)
```bash
python -m scripts.serve_fake         # deterministic offline stylist on :8000
```

### Run directly with Google ADK CLI
Because `stylist_agent/agent.py` exposes `root_agent`:
```bash
adk web .                            # inspect agent traces, state & tools in ADK Dev UI
```

## Evaluation & Tests

```bash
# Backend lint + tests (14 tests, offline)
ruff check . && pytest -q

# Frontend typecheck, unit tests (12 tests) & production build
cd web && npm run typecheck && npm test && npm run build

# Offline stylist rubric eval (8/8 scenarios)
python -m eval.run --offline --baseline

# Live Gemini + ADK AgentEvaluator (requires GEMINI_API_KEY)
python -m eval.run --live --baseline
python -m eval.run --adk-eval
```

## Documentation

- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Prompt Engineering](docs/PROMPTING.md)
- [Architecture Decisions (ADRs)](docs/DECISIONS.md)
- [Evaluation](docs/EVALUATION.md)
- [Free-Tier Deployment](docs/DEPLOYMENT.md)
