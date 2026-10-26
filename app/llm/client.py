import json
import warnings
from typing import Protocol

from app.config import GEMINI_API_KEY, GEMINI_FAST_MODEL, GEMINI_MODEL, GEMINI_THINKING
from app.llm import prompts
from app.llm.schemas import ComplexionEstimate, Extraction

# Newer Gemini finish reasons (e.g. MALFORMED_RESPONSE) are unknown to older SDK enums; we retry those, so the warning is noise.
warnings.filterwarnings("ignore", message=r".*is not a valid FinishReason")


class LLM(Protocol):
    def extract(self, message: str, known: dict) -> Extraction: ...
    def phrase(self, instruction: str, context: dict, fallback: str) -> str: ...
    def answer_offtopic(self, message: str) -> str: ...
    def opinion(self, facts: dict, question: str, avoid: list[str] | None = None) -> str: ...
    def objection(self, kind: str, data: dict, question: str, avoid: list[str] | None = None) -> str: ...
    def compare(self, data: dict, avoid: list[str] | None = None) -> str: ...
    def analyze_complexion(self, image: bytes, mime_type: str) -> ComplexionEstimate: ...


class GeminiLLM:
    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL,
                 thinking: str | None = None, fast_model: str | None = None):
        from google import genai  # imported lazily so tests don't need a key

        self._genai_types = __import__("google.genai.types", fromlist=["types"])
        self.client = genai.Client(api_key=api_key)
        self.usage = {"calls": 0, "in": 0, "out": 0, "thought": 0}  # token counters, used by the evaluation harness
        self.model = model
        self.fast_model = fast_model or GEMINI_FAST_MODEL or model  # parsing and short wording
        self.thinking = GEMINI_THINKING if thinking is None else thinking
        self._thinking_ok = True

    def _thinking_config(self, model: str):
        """Gemini 3 takes a thinking level, Gemini 2.5 a token budget. Returns None to leave the model's default."""
        setting = str(self.thinking or "").strip().lower()
        if not setting or setting == "default" or not self._thinking_ok:
            return None
        types = self._genai_types
        try:
            if setting.lstrip("-").isdigit():
                return types.ThinkingConfig(thinking_budget=int(setting))
            if "2.5" in model:  # older models: translate the level into a budget
                pro = "pro" in model
                budget = {"minimal": 128 if pro else 0, "low": 128 if pro else 0, "medium": 1024, "high": -1}.get(setting)
                return types.ThinkingConfig(thinking_budget=budget) if budget is not None else None
            return types.ThinkingConfig(thinking_level=setting.upper())
        except Exception:
            return None

    def _generate(self, contents: str, system: str, temperature: float, schema=None, model: str | None = None) -> object:
        t = self._genai_types
        model = model or self.model
        cfg = {"system_instruction": system, "temperature": temperature}
        if schema is not None:
            cfg.update(response_mime_type="application/json", response_schema=schema)
        thinking = self._thinking_config(model)
        if thinking is not None:
            cfg["thinking_config"] = thinking
        for attempt in range(2):
            try:
                resp = self.client.models.generate_content(model=model, contents=contents, config=t.GenerateContentConfig(**cfg))
                break
            except Exception as exc:
                if attempt == 0 and "thinking_config" in cfg and "thinking" in str(exc).lower():
                    self._thinking_ok = False  # this model rejected our thinking setting: stop sending it
                    cfg.pop("thinking_config")
                    continue
                raise
        meta = getattr(resp, "usage_metadata", None)
        self.usage["calls"] += 1
        self.usage["in"] += getattr(meta, "prompt_token_count", 0) or 0
        self.usage["out"] += getattr(meta, "candidates_token_count", 0) or 0
        self.usage["thought"] += getattr(meta, "thoughts_token_count", 0) or 0
        return resp

    def extract(self, message: str, known: dict) -> Extraction:
        prompt = f"Known state: {json.dumps(known)}\nUser message: {message}"
        last: Exception | None = None
        for _ in range(2):  # a malformed / empty structured response is rare; one retry is cheap
            resp = self._generate(prompt, prompts.EXTRACT_SYSTEM, 0.0, schema=Extraction, model=self.fast_model)
            parsed = getattr(resp, "parsed", None)
            if isinstance(parsed, Extraction):
                return parsed
            try:
                return Extraction.model_validate_json(resp.text)
            except Exception as exc:
                last = exc
        raise ValueError(f"could not parse the model's response: {last}")

    def phrase(self, instruction: str, context: dict, fallback: str) -> str:
        prompt = f"Instruction: {instruction}\nContext: {json.dumps(context)}"
        try:
            text = (self._generate(prompt, prompts.PHRASE_SYSTEM, 0.7, model=self.fast_model).text or "").strip()
            return text or fallback
        except Exception:
            return fallback  # wording is optional; behavior never depends on it

    def answer_offtopic(self, message: str) -> str:
        try:
            text = (self._generate(message, prompts.OFFTOPIC_SYSTEM, 0.5, model=self.fast_model).text or "").strip()
            return text or "Good question, though I'm better with shoes than with that."
        except Exception:
            return "Good question, though I'm better with shoes than with that."

    def opinion(self, facts: dict, question: str, avoid: list[str] | None = None) -> str:
        prompt = f"Product data (the ONLY facts you may use): {json.dumps(facts)}\nShopper asks: {question}"
        if avoid:
            prompt += f"\nYour previous answer broke these rules, fix them: {avoid}"
        return (self._generate(prompt, prompts.OPINION_SYSTEM, 0.6).text or "").strip()

    def objection(self, kind: str, data: dict, question: str, avoid: list[str] | None = None) -> str:
        prompt = (f"Concern type: {kind}\nData (the ONLY facts you may use): {json.dumps(data)}\n"
                  f"Shopper said: {question}")
        if avoid:
            prompt += f"\nYour previous answer broke these rules, fix them: {avoid}"
        return (self._generate(prompt, prompts.OBJECTION_SYSTEM, 0.6).text or "").strip()

    def compare(self, data: dict, avoid: list[str] | None = None) -> str:
        prompt = f"Data (the ONLY facts you may use): {json.dumps(data)}"
        if avoid:
            prompt += f"\nYour previous answer broke these rules, fix them: {avoid}"
        return (self._generate(prompt, prompts.COMPARE_SYSTEM, 0.5).text or "").strip()

    def analyze_complexion(self, image: bytes, mime_type: str) -> ComplexionEstimate:
        """Vision call. The image lives only in this call's memory; nothing here writes it anywhere."""
        types = self._genai_types
        part = types.Part.from_bytes(data=image, mime_type=mime_type)
        resp = self.client.models.generate_content(
            model=self.model,
            contents=[part, "Estimate skin tone and undertone for shoe color styling."],
            config=types.GenerateContentConfig(
                system_instruction=prompts.COMPLEXION_SYSTEM, temperature=0.0,
                response_mime_type="application/json", response_schema=ComplexionEstimate),
        )
        parsed = getattr(resp, "parsed", None)
        return parsed if isinstance(parsed, ComplexionEstimate) else ComplexionEstimate.model_validate_json(resp.text)
