from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FashionItem(BaseModel):
    id: str
    name: str
    brand: str = "Independent / Curated"
    category: str = "apparel"
    price_text: str = "Check store"
    price_estimate_inr: int | None = None
    color: str = "neutral"
    color_hex: str = "#8C7A6B"
    aesthetic_tags: list[str] = Field(default_factory=list)
    fit_note: str = ""
    why_it_suits_you: str = ""
    styling_tip: str = ""
    image_url: str = ""
    image_source: Literal["retailer", "ai_generated", "none"] = "none"
    url: str = ""
    url_verified: bool = False
    source_domain: str = ""
    match_score: float = 75.0
    match_reasons: list[str] = Field(default_factory=list)


class OutfitPiece(BaseModel):
    slot: str  # Top, Bottom, Outerwear, Footwear, Accessory
    name: str
    brand: str = ""
    store: str = ""
    color: str = ""
    color_hex: str = "#8C7A6B"
    fit_guidance: str = ""
    from_closet: bool = False
    item_id: str | None = None
    search_query: str = ""
    image_url: str = ""
    image_source: Literal["retailer", "ai_generated", "none"] = "none"
    url: str = ""
    url_verified: bool = False
    price_text: str = ""
    price_estimate_inr: int | None = None


class OutfitLook(BaseModel):
    id: str
    title: str
    occasion: str
    vibe: str
    image_url: str = ""
    image_source: Literal["retailer", "ai_generated", "none"] = "none"
    look_fingerprint: str = ""
    tags: list[str] = Field(default_factory=list)
    color_story: str
    proportion_tip: str
    styling_hacks: list[str] = Field(default_factory=list)
    pieces: list[OutfitPiece] = Field(default_factory=list)
    total_estimate_text: str = ""
    total_estimate_inr: int | None = None
    saved_at: str = ""


class FactEntry(BaseModel):
    key: str
    value: str
    source: Literal["stated", "confirmed", "swiped", "inferred"] = "stated"


class SwipeRecord(BaseModel):
    item_id: str
    item_name: str
    direction: Literal["like", "dislike", "super_like"]
    tags: list[str] = Field(default_factory=list)
    color: str = ""
    brand: str = ""
    occasion: str = ""
    price_estimate_inr: int | None = None
    timestamp: str = ""


class StyleDNA(BaseModel):
    user_id: str = "default"
    sizes: dict[str, str] = Field(default_factory=dict)
    aesthetics: dict[str, float] = Field(default_factory=dict)
    occasion_aesthetics: dict[str, dict[str, float]] = Field(default_factory=dict)
    aesthetic_timestamps: dict[str, str] = Field(default_factory=dict)
    liked_colors: list[str] = Field(default_factory=list)
    disliked_colors: list[str] = Field(default_factory=list)
    liked_brands: list[str] = Field(default_factory=list)
    disliked_brands: list[str] = Field(default_factory=list)
    budget_min: int | None = None
    budget_max: int | None = None
    skin_tone: str | None = None
    undertone: str | None = None
    color_season: str | None = None
    fit_preference: str | None = None
    saved_closet: list[FashionItem] = Field(default_factory=list)
    saved_outfits: list[OutfitLook] = Field(default_factory=list)
    disliked_item_keys: list[str] = Field(default_factory=list)
    seen_look_ids: list[str] = Field(default_factory=list)
    seen_look_fingerprints: list[str] = Field(default_factory=list)
    seen_item_ids: list[str] = Field(default_factory=list)
    tutorial_seen: bool = False
    swipe_history: list[SwipeRecord] = Field(default_factory=list)
    facts: list[FactEntry] = Field(default_factory=list)
    declined: bool = False


class SearchMeta(BaseModel):
    query: str
    category: str = "apparel"
    max_budget_inr: int | None = None


class UIAction(BaseModel):
    type: Literal[
        "none",
        "swipe_deck",
        "grid",
        "focus_item",
        "outfit_board",
        "compare",
        "closet",
        "request_photo",
        "confirm_forget",
    ] = "none"
    items: list[FashionItem] = Field(default_factory=list)
    outfit: OutfitLook | None = None
    looks: list[OutfitLook] = Field(default_factory=list)
    focus_item: FashionItem | None = None
    photo_mode: Literal["complexion", "outfit_check"] | None = None
    search_meta: SearchMeta | None = None


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    user_id: str = Field(default="default", min_length=1, max_length=120)
    message: str = Field(..., min_length=1, max_length=2000)
    focus_item_id: str | None = None
    style_dna: StyleDNA | None = None


class ChatResponse(BaseModel):
    reply: str
    ui_action: UIAction = Field(default_factory=UIAction)
    style_dna: StyleDNA = Field(default_factory=StyleDNA)
    tools_used: list[str] = Field(default_factory=list)
    telemetry: dict[str, Any] = Field(default_factory=dict)


class SwipeRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    user_id: str = Field(default="default", min_length=1, max_length=120)
    item: FashionItem
    direction: Literal["like", "dislike", "super_like"]
    idempotency_key: str | None = Field(default=None, max_length=120)


class SwipeResponse(BaseModel):
    style_dna: StyleDNA
    reaction: str
    stats: dict[str, int]


class SessionReq(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    user_id: str = Field(default="default", min_length=1, max_length=120)


class ProfileSyncReq(BaseModel):
    user_id: str = Field(default="default", min_length=1, max_length=120)
    style_dna: StyleDNA


class ComplexionEstimate(BaseModel):
    skin_tone: Literal["fair", "light", "medium", "tan", "deep"]
    undertone: Literal["warm", "cool", "neutral"]
    color_season: Literal["Spring", "Summer", "Autumn", "Winter"]
    confidence: Literal["low", "medium", "high"]
    recommended_colors: list[str] = Field(default_factory=list)
    note: str = ""


class AnalyzeReq(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    user_id: str = Field(default="default", min_length=1, max_length=120)
    image_base64: str = Field(..., min_length=1)
    mime_type: str = Field(..., min_length=1, max_length=64)
    note: str = Field(default="", max_length=500)


class ConfirmComplexionReq(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    user_id: str = Field(default="default", min_length=1, max_length=120)
    skin_tone: Literal["fair", "light", "medium", "tan", "deep"]
    undertone: Literal["warm", "cool", "neutral"]
    color_season: Literal["Spring", "Summer", "Autumn", "Winter"] | None = None


class OutfitCheckResult(BaseModel):
    overall_vibe: str
    what_works: list[str] = Field(default_factory=list)
    elevation_tips: list[str] = Field(default_factory=list)
    suggested_additions: list[str] = Field(default_factory=list)
    rating_out_of_10: int = Field(default=8, ge=1, le=10)
    honest_bestie_summary: str


class LookSearchRequest(BaseModel):
    session_id: str = Field(default="default", min_length=1, max_length=120)
    user_id: str = Field(default="default", min_length=1, max_length=120)
    occasion: str = Field(..., min_length=1, max_length=300)
    vibe: str = Field(default="effortless modern", max_length=120)
    budget_inr: int | None = None
    anchor_item: str = ""
    exclude_look_ids: list[str] = Field(default_factory=list)
    style_dna: StyleDNA | None = None


class ItemSearchRequest(BaseModel):
    session_id: str = Field(default="default", min_length=1, max_length=120)
    user_id: str = Field(default="default", min_length=1, max_length=120)
    query: str = Field(..., min_length=1, max_length=300)
    category: str = Field(default="apparel", max_length=40)
    max_budget_inr: int | None = None
    exclude_item_ids: list[str] = Field(default_factory=list)
    style_dna: StyleDNA | None = None


class LookSwipeRequest(BaseModel):
    session_id: str = Field(default="default", min_length=1, max_length=120)
    user_id: str = Field(default="default", min_length=1, max_length=120)
    look: OutfitLook | None = None
    item: FashionItem | None = None
    action: Literal["save", "skip", "buy_intent", "undo"] = "save"
    idempotency_key: str | None = Field(default=None, max_length=120)


class PreferencesUpdateReq(BaseModel):
    user_id: str = Field(default="default", min_length=1, max_length=120)
    tutorial_seen: bool | None = None
    fit_preference: str | None = None
    budget_max: int | None = None
    sizes: dict[str, str] | None = None
    liked_colors: list[str] | None = None


class TranscribeReq(BaseModel):
    audio_base64: str = Field(..., min_length=1)
    mime_type: str = Field(default="audio/webm", min_length=1, max_length=80)
