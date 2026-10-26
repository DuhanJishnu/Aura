"""Semantic search & free-text query matching using SQLite FTS5 and optional Gemini embeddings."""
from __future__ import annotations

import math
import re
import sqlite3
from functools import lru_cache

from app.config import GEMINI_API_KEY

STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "for", "with", "about",
    "is", "it", "to", "from", "of", "some", "any", "show", "me", "want", "need",
    "looking", "shoes", "shoe", "clothes", "clothing", "item", "accessory", "accessories",
}

SEMANTIC_CONCEPTS: dict[str, list[str]] = {
    "monsoon": ["grippy outsole", "slip-resistant sole", "mesh", "rain", "water"],
    "rain": ["grippy outsole", "slip-resistant sole", "mesh"],
    "rainy": ["grippy outsole", "slip-resistant sole", "mesh"],
    "waterproof": ["grippy outsole", "slip-resistant sole", "sturdy build"],
    "water-resistant": ["grippy outsole", "slip-resistant sole"],
    "wet": ["grippy outsole", "slip-resistant sole"],
    "light": ["lightweight build", "light to carry", "breathable mesh upper"],
    "lightweight": ["lightweight build", "light to carry", "breathable mesh upper"],
    "heavy": ["sturdy build", "genuine leather upper"],
    "sturdy": ["sturdy build", "genuine leather upper"],
    "durable": ["sturdy build", "genuine leather upper"],
    "durability": ["sturdy build", "genuine leather upper"],
    "cushion": ["cushioned midsole", "padded insole", "everyday comfort"],
    "cushioned": ["cushioned midsole", "padded insole", "everyday comfort"],
    "cushioning": ["cushioned midsole", "padded insole"],
    "comfort": ["everyday comfort", "padded insole", "soft lining", "relaxed fit"],
    "comfortable": ["everyday comfort", "padded insole", "soft lining", "relaxed fit"],
    "breathable": ["breathable mesh upper", "breathable weave", "soft cotton"],
    "summer": ["breathable mesh upper", "breathable weave", "lightweight build"],
    "winter": ["genuine leather upper", "sturdy build", "track jacket", "hoodie"],
    "formal": ["genuine leather upper", "classic stitching", "wrinkle-resistant fabric", "tailored fit"],
    "office": ["genuine leather upper", "classic stitching", "wrinkle-resistant fabric", "tailored fit"],
    "interview": ["genuine leather upper", "classic stitching", "formal shirt", "tailored fit"],
    "running": ["cushioned midsole", "breathable mesh upper", "lightweight build", "moisture-wicking fabric"],
    "workout": ["moisture-wicking fabric", "stretch fit", "breathable weave", "lightweight build"],
    "gym": ["moisture-wicking fabric", "stretch fit", "sturdy build", "gym bag"],
    "walking": ["everyday comfort", "flexible sole", "cushioned midsole", "padded insole"],
    "travel": ["sturdy build", "light to carry", "easy to clean", "everyday comfort"],
    "wrinkle-free": ["wrinkle-resistant fabric"],
    "soft": ["soft cotton", "soft lining", "padded insole"],
    "grip": ["grippy outsole", "slip-resistant sole"],
    "slippery": ["grippy outsole", "slip-resistant sole"],
}


def tokenize_query(query: str) -> list[str]:
    """Extract clean search terms from a free-text user query."""
    words = re.findall(r"\b[a-zA-Z0-9_-]+\b", query.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def build_fts_expressions(terms: list[str]) -> list[str]:
    """Generate FTS5 MATCH expressions expanding domain concepts."""
    if not terms:
        return []
    clauses = []
    for term in terms:
        parts = [f'"{term}"*']
        if term in SEMANTIC_CONCEPTS:
            for syn in SEMANTIC_CONCEPTS[term]:
                parts.append(f'"{syn}"')
        clauses.append(" OR ".join(parts))
    return clauses


def fts_search(
    conn: sqlite3.Connection,
    query: str,
    category: str | None = None,
    limit: int = 50,
) -> dict[int, float]:
    """Score products using SQLite FTS5 and semantic concept expansion. Returns {shoe_id: score}."""
    terms = tokenize_query(query)
    if not terms:
        return {}

    clauses = build_fts_expressions(terms)
    # First attempt: all concepts must match (AND)
    match_str = " AND ".join(f"({c})" for c in clauses)
    sql = """
        SELECT f.id, bm25(shoes_fts) as rank
        FROM shoes_fts f
        WHERE shoes_fts MATCH ?
    """
    params: list = [match_str]
    if category:
        sql += " AND f.category = ?"
        params.append(category)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        rows = []

    # Fallback attempt if strict AND returned no candidates: union (OR)
    if not rows and len(clauses) > 1:
        match_str = " OR ".join(f"({c})" for c in clauses)
        params[0] = match_str
        try:
            rows = conn.execute(sql, params).fetchall()
        except Exception:
            rows = []

    scores: dict[int, float] = {}
    for r in rows:
        # bm25 returns negative values where lower/more negative is better. Convert to positive.
        scores[int(r["id"])] = max(0.1, -float(r["rank"]))
    return scores


@lru_cache(maxsize=128)
def get_query_embedding(query: str) -> list[float] | None:
    """Fetch query embedding from Gemini API when available."""
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.embed_content(model="gemini-embedding-001", contents=query)
        return list(resp.embeddings[0].values)
    except Exception:
        return None


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def semantic_rank(
    conn: sqlite3.Connection,
    candidates: list[dict],
    query: str,
    top_k: int = 6,
) -> list[dict]:
    """Re-ranks candidates by blending semantic relevance score with product rating and price."""
    if not candidates or not query.strip():
        return candidates[:top_k]

    scores = fts_search(conn, query, limit=100)

    # Optional: if query embedding is available and persisted embeddings exist
    q_emb = get_query_embedding(query)
    emb_scores: dict[int, float] = {}
    if q_emb:
        try:
            c_ids = [c["id"] for c in candidates]
            placeholders = ",".join("?" * len(c_ids))
            rows = conn.execute(
                f"SELECT shoe_id, vector FROM shoe_embeddings WHERE shoe_id IN ({placeholders})",
                c_ids,
            ).fetchall()
            for r in rows:
                import json
                vec = json.loads(r["vector"]) if isinstance(r["vector"], (str, bytes)) else r["vector"]
                emb_scores[r["shoe_id"]] = cosine_similarity(q_emb, vec)
        except Exception:
            pass

    def rank_key(p: dict) -> float:
        pid = p["id"]
        fts_score = scores.get(pid, 0.0)
        emb_score = emb_scores.get(pid, 0.0)
        # Combined relevance signal
        relevance = fts_score * 2.0 + emb_score * 5.0
        # If product matches query terms, boost significantly above plain rating
        return relevance + (p.get("rating", 4.0) * 0.1)

    return sorted(candidates, key=rank_key, reverse=True)[:top_k]
