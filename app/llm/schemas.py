from typing import Literal

from pydantic import BaseModel, Field


class Extraction(BaseModel):
    """What the LLM understood from one user message."""

    intent: Literal[
        "shopping", "greeting", "off_topic", "decline", "other",
        "opinion", "focus", "refine", "cart_add", "cart_remove", "buy", "confirm",
        "browse", "just_looking", "compare", "object", "reject",
        "profile_update", "complexion", "profile_show", "profile_forget", "checkout",
    ] = "shopping"
    use: Literal["sports", "office", "casual"] | None = None
    for_whom: Literal["self", "other"] | None = None
    size: float | None = None
    category: Literal["shoes", "apparel", "accessories"] | None = None
    budget: int | None = None
    color: str | None = None
    query: str | None = None
    occasion: str | None = None
    item_type: str | None = None
    refine: Literal["cheaper", "other_colors", "show_more"] | None = None
    product_index: int | None = None
    objection: Literal["price", "fit", "quality"] | None = None
    compare_indices: list[int] = Field(default_factory=list)
    undertone: Literal["warm", "cool", "neutral"] | None = None
    skin_tone: Literal["fair", "light", "medium", "tan", "deep"] | None = None
    style: Literal["sporty", "classic", "casual", "bold"] | None = None
    liked_color: str | None = None
    disliked_color: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None


class ComplexionEstimate(BaseModel):
    skin_tone: Literal["fair", "light", "medium", "tan", "deep"]
    undertone: Literal["warm", "cool", "neutral"]
    confidence: Literal["low", "medium", "high"]
    note: str = ""
