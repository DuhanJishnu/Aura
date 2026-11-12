# Free-Tier Deployment Guide

This stack is engineered to cost **$0/month in infrastructure** — **zero databases, zero Redis, zero paid search APIs**. You only pay for your Gemini API usage (and Google AI Studio offers a generous free tier for development).

## Option A: Split Free Deploy — Render (Backend) + Vercel (Frontend)
Recommended for the best always-on WebSocket (Gemini Live) + Next.js experience.

### 1. Deploy Backend on Render (Free Web Service)
1. Push this repository to GitHub.
2. In [Render](https://render.com), click **New -> Blueprint** (uses `render.yaml` at repo root) or **New Web Service** with Docker runtime.
3. Set `GEMINI_API_KEY` in Render Environment Variables.
4. Note your Render URL, e.g. `https://aura-adk-stylist-api.onrender.com`.

### 2. Deploy Frontend on Vercel (Hobby Free Tier)
1. Import the repo in [Vercel](https://vercel.com) and set **Root Directory** to `web`.
2. Add Environment Variables:
   - `BACKEND_URL=https://aura-adk-stylist-api.onrender.com`
   - `NEXT_PUBLIC_WS_URL=wss://aura-adk-stylist-api.onrender.com` (needed so Gemini Live WebSocket connects directly to FastAPI, since Next.js API routes only proxy HTTP/SSE).
3. Deploy!

> **Why Style DNA survives free-tier spin-downs**: Render's free tier sleeps after inactivity and resets local disk on redeploy. Because the frontend persists `StyleDNA` + `SavedCloset` in `localStorage` and syncs automatically via `POST /profile/sync`, your taste profile and saved items survive every backend restart!

---

## Option B: Docker Compose (Local or Any Free VPS / Oracle Cloud Always-Free)
```bash
cp .env.example .env    # set GEMINI_API_KEY
docker compose up --build
```
Open `http://localhost:3000`.

---

## Option C: Hugging Face Spaces (Free 16GB RAM Docker Space for Backend)
1. Create a new **Docker Space** on Hugging Face.
2. Point it to the root `Dockerfile`, set `PORT=7860` and secret `GEMINI_API_KEY`.
3. Point Vercel's `BACKEND_URL` and `NEXT_PUBLIC_WS_URL` at your Space URL (`https://<user>-<space>.hf.space` / `wss://...`).
