# Prompt Engineering Guide

All prompts live in [`stylist_agent/prompts.py`](../stylist_agent/prompts.py) and are treated as versioned, testable behavioral specifications.

## 1. Persona & Fashion Sense (`STYLIST_ORCHESTRATOR_INSTRUCTION`)
Aura is prompted as a **stylish, perceptive best friend** rather than a transactional form or pushy salesperson:
- **Fashion Reasoning**: Instructed to justify choices using real styling mechanics — the **rule of thirds** (balancing relaxed vs. structured silhouettes), the **60-30-10 color rule**, seasonal undertone pairing (`UNDERTONE_PALETTES`), and climate/fabric fit.
- **Honest "Bestie Check"**: Explicitly instructed to mention trade-offs (creasing linen, narrow toe box, price vs. alternatives) and never pressure a sale.
- **Dynamic Context Injection**: Uses ADK's `{style_dna_summary?}` state template refreshed before every turn via `before_agent_callback` (`_sync_style_state`), ensuring Aura immediately adapts to swipes made seconds earlier in the UI.

## 2. Friend-First + Fashion Circle-Back Strategy
A signature behavior of this assistant is staying warm and genuinely helpful on off-topic prompts while gently bringing the conversation back to styling:
- **Rule**: When the user asks something off-topic (cooking, work stress, weather, trivia), answer warmly, accurately, and briefly like a real friend (1–2 sentences), then add a playful, low-pressure bridge back to fashion or their current style goals.
- **Why few-shot examples matter**: Including concrete positive examples (iced coffee -> coffee-run fit; presentation stress -> confidence blazer) prevents stiff, jarring transitions ("As a fashion assistant I cannot...").

## 3. Strict Boundary Enforcement ("No Means No")
Circle-back behavior MUST yield immediately to user boundaries:
- If the user declines ("no thanks", "stop pitching", "not shopping right now"), the prompt requires calling `set_shopping_boundary(declined=True)`.
- That flips `BOUNDARY` in `{style_dna_summary?}`, instructing Aura to answer casual or off-topic chat warmly **without** pitching items, running searches, or circling back to fashion until the user re-engages.

## 4. URL Grounding & Anti-Hallucination (`WEB_FINDER_INSTRUCTION` & `CARD_EXTRACTOR_INSTRUCTION`)
LLMs frequently hallucinate realistic-looking e-commerce URLs (`myntra.com/shirt-12345`). To eliminate dead or fabricated links:
1. `WEB_FINDER_INSTRUCTION` restricts findings to actual `google_search` results and forbids guessing URLs.
2. `CARD_EXTRACTOR_INSTRUCTION` receives the exact `grounding_links` extracted from Gemini's `grounding_metadata.grounding_chunks` and is instructed to set `url=""` if no chunk matches.
3. Python post-processing verifies `item.url in valid_urls`; unverified items receive `url_verified=False` and a deterministic Google Shopping search URL (`https://www.google.com/search?tbm=shop&q=...`).

## 5. Head-to-Toe Lookbooks (`OUTFIT_ARCHITECT_INSTRUCTION`)
Instructs the outfit architect to combine **Closet Integration** (reusing items the user swiped right on) with **60-30-10 color distribution**, **silhouette balance**, and actionable **styling hacks** (French tuck, cuffing, texture contrast).
