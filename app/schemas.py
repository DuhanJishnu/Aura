"""Chat API contract (fixed early, see README)."""
from typing import Literal

from pydantic import BaseModel, Field

UIActionType = Literal["show_products", "focus_product", "add_to_cart", "checkout", "compare", "request_photo", "none"]


class Slots(BaseModel):
    category: str | None = None
    for_whom: Literal["self", "other"] | None = None
    size: float | None = None
    use: Literal["sports", "office", "casual"] | None = None
    budget: int | None = None
    color: str | None = None
    query: str | None = None


class UIAction(BaseModel):
    type: UIActionType = "none"
    filters: dict = Field(default_factory=dict)
    product_id: int | None = None
    product_ids: list[int] = Field(default_factory=list)
    order_id: str | None = None


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    user_id: str | None = None
    focus_product_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    slots: Slots = Field(default_factory=Slots)
    ui_action: UIAction = Field(default_factory=UIAction)
    policy: dict | None = None  # which rule fired


class CartAdd(BaseModel):
    session_id: str
    user_id: str | None = None
    product_id: int
    size: float


class CartRemove(BaseModel):
    session_id: str
    product_id: int
    size: float | None = None


class CheckoutReq(BaseModel):
    session_id: str
    user_id: str | None = None


class SessionReq(BaseModel):
    session_id: str
    user_id: str | None = None


class AnalyzeReq(SessionReq):
    image_base64: str
    mime_type: str


class ConfirmComplexionReq(SessionReq):
    skin_tone: Literal["fair", "light", "medium", "tan", "deep"]
    undertone: Literal["warm", "cool", "neutral"]
