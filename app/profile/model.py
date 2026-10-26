"""In-memory view of what we know about a user. Every fact says where it came from:
stated (user said it), confirmed (user confirmed an estimate) or inferred (our guess, used lightly)."""
from dataclasses import dataclass, field

SINGLE = {"undertone", "skin_tone", "style", "budget_min", "budget_max"}
STRONG = {"stated", "confirmed"}
SIGNAL_KEYS = {"undertone", "liked_color", "rejected_color", "budget_min", "budget_max"}


@dataclass(frozen=True)
class Fact:
    key: str
    value: str
    status: str


@dataclass
class Profile:
    facts: list[Fact] = field(default_factory=list)

    def get(self, key: str) -> Fact | None:
        return next((f for f in self.facts if f.key == key), None)

    def value(self, key: str) -> str | None:
        f = self.get(key)
        return f.value if f else None

    def values(self, key: str) -> list[Fact]:
        return [f for f in self.facts if f.key == key]

    def set(self, key: str, value, status: str) -> None:
        value = str(value)
        if key in SINGLE:
            self.facts = [f for f in self.facts if f.key != key]
        else:
            old = next((f for f in self.facts if f.key == key and f.value == value), None)
            if old and old.status in STRONG and status == "inferred":
                return  # a guess never overwrites something the user said
            self.facts = [f for f in self.facts if not (f.key == key and f.value == value)]
        self.facts.append(Fact(key, value, status))

    def set_color(self, color: str, liked: bool, status: str) -> None:
        other = "rejected_color" if liked else "liked_color"
        if status == "inferred" and any(f.value == color and f.status in STRONG for f in self.values(other)):
            return
        self.facts = [f for f in self.facts if not (f.key == other and f.value == color)]
        self.set("liked_color" if liked else "rejected_color", color, status)

    def has_signals(self) -> bool:
        return any(f.key in SIGNAL_KEYS for f in self.facts)

    def clear(self) -> None:
        self.facts = []
