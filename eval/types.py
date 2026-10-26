from dataclasses import asdict, dataclass, field


@dataclass
class Persona:
    id: str
    category: str
    use: str | None
    size: float | None
    budget: int | None
    for_whom: str
    objection: str | None      # "price" | "fit" | None: what the judge looks for
    opening: str
    off_topic: str | None
    hidden: str                # the private persona card given to the LLM-simulated user
    expected_empty: bool = False   # nothing in stock matches: an honest "no" is the right answer
    max_turns: int = 12
    product_category: str = "shoes"


@dataclass
class Turn:
    role: str                  # "user" | "assistant"
    text: str
    shown_ids: list[int] = field(default_factory=list)
    action: str = ""
    rule: str | None = None
    order_id: str | None = None
    latency: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    amounts: list[int] = field(default_factory=list)  # rupee figures the system states that are not product prices (e.g. a price ceiling)
    tokens_thought: int = 0   # hidden reasoning tokens (not in tokens_out, but they cost time and money)


@dataclass
class Conversation:
    persona: Persona
    system: str
    turns: list[Turn] = field(default_factory=list)
    verdict: dict | None = None
    judge: dict | None = None
    orders: list[dict] = field(default_factory=list)
    error: str | None = None

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "Conversation":
        return Conversation(Persona(**d["persona"]), d["system"], [Turn(**t) for t in d["turns"]],
                            d.get("verdict"), d.get("judge"), d.get("orders", []), d.get("error"))
