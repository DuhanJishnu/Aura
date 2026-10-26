import re

from app.engine.signals import detect_category
from app.llm.schemas import ComplexionEstimate, Extraction

ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}


class FakeLLM:
    """Keyword-based stand-in so engine logic is tested without any network."""

    def extract(self, message, known):
        m = message.lower().strip()
        if re.search(r"\b(no thanks|never mind|nevermind|not interested)\b", m):
            return Extraction(intent="decline")
        if "weather" in m or "capital of" in m or "leap year" in m:
            return Extraction(intent="off_topic")
        if m in {"hi", "hello", "hey"}:
            return Extraction(intent="greeting")
        if "forget my profile" in m:
            return Extraction(intent="profile_forget")
        if "what do you know about me" in m:
            return Extraction(intent="profile_show")
        if u := re.search(r"\b(warm|cool|neutral) undertone", m):
            return Extraction(intent="profile_update", undertone=u.group(1))
        if c := re.search(r"i don't like (black|white|navy|grey|brown|red|olive|tan|pink)\b", m):
            return Extraction(intent="profile_update", disliked_color=c.group(1))
        if c := re.search(r"i (?:really )?like (black|white|navy|grey|brown|red|olive|tan|pink)\b", m):
            return Extraction(intent="profile_update", liked_color=c.group(1))
        if s := re.search(r"my style is (sporty|classic|casual|bold)", m):
            return Extraction(intent="profile_update", style=s.group(1))
        if b := re.search(r"usual budget is (\d+) to (\d+)", m):
            return Extraction(intent="profile_update", budget_min=int(b.group(1)), budget_max=int(b.group(2)))
        if re.search(r"which colou?rs suit|suit my skin|colou?r advice", m):
            return Extraction(intent="complexion")
        if m in {"ok", "okay", "thanks", "hmm", "fine", "cool"}:
            return Extraction(intent="other")
        if re.search(r"\bbored\b|just looking|just browsing|surprise me|\bbrowse\b|show me something", m):
            return Extraction(intent="browse")
        if "compare" in m:
            ords = [ORD[w] for w in re.findall(r"\b(first|second|third|fourth)\b", m)]
            return Extraction(intent="compare", compare_indices=ords)
        if re.search(r"not this one|don't like (it|this)", m):
            return Extraction(intent="reject")
        if re.search(r"too (expensive|much)|pricey", m):
            return Extraction(intent="object", objection="price")
        if re.search(r"runs? small|will it fit|too tight|unsure (of|about) (my )?size", m):
            return Extraction(intent="object", objection="fit")
        if re.search(r"will it last|durable|looks cheap", m):
            return Extraction(intent="object", objection="quality")
        idx = next((v for k, v in ORD.items() if re.search(rf"\b{k}\b", m)), None)
        if re.search(r"place (the )?order|\byes\b|\bconfirm", m):
            return Extraction(intent="confirm")
        if re.search(r"what do you think|is it good|your opinion|who is it for", m):
            return Extraction(intent="opinion", product_index=idx)
        if idx and re.search(r"tell me about|show me|look at", m):
            return Extraction(intent="focus", product_index=idx)
        if "cheaper" in m:
            return Extraction(intent="refine", refine="cheaper")
        if re.search(r"other colou?rs|different colou?r", m):
            return Extraction(intent="refine", refine="other_colors")
        if re.search(r"show more|more options", m):
            return Extraction(intent="refine", refine="show_more")
        if re.search(r"\bbuy (this|it|the)\b|i.ll take", m):
            return Extraction(intent="buy", product_index=idx, size=_size(m))
        if re.search(r"add (it|this)|add to (my )?cart", m):
            return Extraction(intent="cart_add", product_index=idx, size=_size(m))
        if m.startswith("remove"):
            return Extraction(intent="cart_remove")
        ex = Extraction(size=_size(m))
        if cat := detect_category(m):
            ex.category = cat
        for use in ("sports", "office", "casual"):
            if use in m:
                ex.use = use
        if re.search(r"\b(for my|for him|for her|gift)\b", m):
            ex.for_whom = "other"
        elif re.search(r"\bfor me\b|\bmyself\b", m):
            ex.for_whom = "self"
        if b := re.search(r"under (\d+)", m):
            ex.budget = int(b.group(1))
        return ex

    def analyze_complexion(self, image, mime_type):
        self.seen_image = image  # lets tests prove the bytes reached the model and nowhere else
        return ComplexionEstimate(skin_tone="medium", undertone="warm", confidence="medium", note="")

    def phrase(self, instruction, context, fallback):
        return fallback

    def answer_offtopic(self, message):
        return "I think it's sunny somewhere, but I'm better with store products."

    def opinion(self, facts, question, avoid=None):
        cat = facts.get("category") or "shoes"
        noun = "shoe" if cat == "shoes" else ("clothes" if cat == "apparel" else "accessory")
        return (f"The {facts['name']} is a {facts['color']} {facts['use_type']} {noun} at ₹{facts['price']:,}. "
                f"It suits everyday {facts['use_type']} use, though at {facts['rating']} stars it is decent rather than outstanding.")


    def objection(self, kind, data, question, avoid=None):
        if kind == "quality":
            return f"I don't have durability data beyond the description, but it is rated {data['rating']}."
        if data["alternatives"]:
            a = data["alternatives"][0]
            return (f"Fair point on price. The {a['name']} is ₹{a['price']:,}, about {a['cheaper_by_pct']}% less, "
                    f"and rated {a['rating']}.")
        return "It's already one of the lowest priced options in your size."

    def compare(self, data, avoid=None):
        return " ".join(data["tradeoffs"])


class HallucinatingLLM(FakeLLM):
    """Always invents a price and a wrong brand; the validator must strip both."""

    def opinion(self, facts, question, avoid=None):
        other = next(b for b in ("Nike", "Clarks") if b != facts["brand"])
        return f"It costs only ₹99,999 today. {other} would be a better pick. Great."


LETTER = {"xs": 1, "small": 2, "s": 2, "medium": 3, "m": 3, "large": 4, "l": 4, "xl": 5, "extra large": 5, "xxl": 6}


def _size(m):
    if letter := re.search(r"\b(xxl|xl|xs|small|medium|large|extra large)\b|\bsize (s|m|l)\b", m):
        return float(LETTER[letter.group(1) or letter.group(2)])
    clean = m.strip().lower()
    if clean in LETTER:
        return float(LETTER[clean])
    s = re.search(r"size (\d+(?:\.5)?)", m) or re.fullmatch(r"(\d+(?:\.5)?)", m)
    return float(s.group(1)) if s else None


def _halluc_objection(self, kind, data, question, avoid=None):
    return "It is just ₹99,999 so it is worth every rupee."


def _halluc_compare(self, data, avoid=None):
    other = next(b for b in ("Nike", "Clarks") if b not in {s["brand"] for s in data["shoes"]})
    return f"{other} would be far better and costs ₹1. Great."


HallucinatingLLM.objection = _halluc_objection
HallucinatingLLM.compare = _halluc_compare
