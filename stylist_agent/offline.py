"""Offline deterministic backends for key-less local demos (`scripts/serve_fake.py`), unit tests, and offline evals."""
from __future__ import annotations

import hashlib
import re
from collections.abc import AsyncIterator
from typing import Any

from app.service import StylistService, VisionBackend
from stylist_agent.memory import PreferenceStore, infer_season, rerank_items, summarize_dna_for_prompt
from stylist_agent.schemas import (
    ChatRequest,
    ChatResponse,
    ComplexionEstimate,
    FashionItem,
    OutfitCheckResult,
    OutfitLook,
    OutfitPiece,
    StyleDNA,
    UIAction,
)
from stylist_agent.tools import SearchBackend

_SAMPLE_ITEMS: list[FashionItem] = [
    FashionItem(
        id="item_olive_linen",
        name="Relaxed Olive Linen Overshirt",
        brand="Uniqlo",
        category="tops",
        price_text="₹2,490",
        price_estimate_inr=2490,
        color="olive",
        color_hex="#556B2F",
        aesthetic_tags=["minimalist", "quiet luxury", "linen", "relaxed"],
        fit_note="Slightly boxy shoulder with breathable weave — true to size.",
        why_it_suits_you="Earthy olive is universally flattering and layers effortlessly over a white tee.",
        styling_tip="Wear open over a crisp ecru tee with straight chinos.",
        url="https://www.google.com/search?tbm=shop&q=Uniqlo+Relaxed+Olive+Linen+Overshirt",
        url_verified=False,
        source_domain="google.com",
    ),
    FashionItem(
        id="item_ecru_chino",
        name="Pleated Ecru Wide-Leg Trousers",
        brand="Zara",
        category="bottoms",
        price_text="₹3,290",
        price_estimate_inr=3290,
        color="cream",
        color_hex="#EDE6D6",
        aesthetic_tags=["quiet luxury", "tailored", "minimalist"],
        fit_note="High-waisted drape with clean front pleats.",
        why_it_suits_you="Cream neutrals brighten almost every upper-body palette and elevate casual tops.",
        styling_tip="Cuff once at the ankle to show clean minimalist sneakers or loafers.",
        url="https://www.google.com/search?tbm=shop&q=Zara+Pleated+Ecru+Wide+Leg+Trousers",
        url_verified=False,
        source_domain="google.com",
    ),
    FashionItem(
        id="item_nb_550",
        name="550 Court Retro Sneakers (White/Green)",
        brand="New Balance",
        category="shoes",
        price_text="₹8,999",
        price_estimate_inr=8999,
        color="white",
        color_hex="#F2F1EC",
        aesthetic_tags=["streetwear", "retro", "casual"],
        fit_note="Structured leather upper; half size up if you have wide feet.",
        why_it_suits_you="Clean retro court silhouette anchors both relaxed streetwear and smart-casual trousers.",
        styling_tip="Pair with ribbed crew socks and relaxed denim or linen trousers.",
        url="https://www.google.com/search?tbm=shop&q=New+Balance+550+White+Green",
        url_verified=False,
        source_domain="google.com",
    ),
    FashionItem(
        id="item_puma_palermo",
        name="Palermo Leather Gum-Sole Sneakers",
        brand="Puma",
        category="shoes",
        price_text="₹5,499",
        price_estimate_inr=5499,
        color="navy",
        color_hex="#20314D",
        aesthetic_tags=["retro", "smart casual", "minimalist"],
        fit_note="Low-profile terrace silhouette; fits true to UK size.",
        why_it_suits_you="Gum sole adds warmth while slim profile keeps wide-leg outfits sharp.",
        styling_tip="Matches navy, stone, or terracotta layers effortlessly.",
        url="https://www.google.com/search?tbm=shop&q=Puma+Palermo+Navy+Gum",
        url_verified=False,
        source_domain="google.com",
    ),
    FashionItem(
        id="item_terracotta_tee",
        name="Heavyweight Boxy Cotton Tee",
        brand="H&M",
        category="tops",
        price_text="₹1,299",
        price_estimate_inr=1299,
        color="terracotta",
        color_hex="#C66B4B",
        aesthetic_tags=["streetwear", "minimalist", "relaxed"],
        fit_note="240gsm cotton jersey with dropped shoulders.",
        why_it_suits_you="Warm terracotta brings rich color without feeling loud.",
        styling_tip="Half-tuck into dark charcoal or indigo denim.",
        url="https://www.google.com/search?tbm=shop&q=HM+Heavyweight+Boxy+Tee+Terracotta",
        url_verified=False,
        source_domain="google.com",
    ),
    FashionItem(
        id="item_cognac_crossbody",
        name="Minimalist Pebble Crossbody Bag",
        brand="Mango",
        category="accessories",
        price_text="₹2,790",
        price_estimate_inr=2790,
        color="warm brown",
        color_hex="#8B5A3C",
        aesthetic_tags=["quiet luxury", "minimalist", "classic"],
        fit_note="Adjustable strap, fits daily essentials cleanly.",
        why_it_suits_you="Warm cognac leather adds polish and ties together earth tones.",
        styling_tip="Crossbody over monochrome outfits to add texture contrast.",
        url="https://www.google.com/search?tbm=shop&q=Mango+Minimalist+Crossbody+Bag+Brown",
        url_verified=False,
        source_domain="google.com",
    ),
    FashionItem(
        id="item_neon_runner",
        name="Volt Neon Mesh Trail Runners",
        brand="Nike",
        category="shoes",
        price_text="₹6,995",
        price_estimate_inr=6995,
        color="neon yellow",
        color_hex="#D9FF00",
        aesthetic_tags=["sporty", "bold", "athleisure"],
        fit_note="Snug forefoot lockdown for active runs.",
        why_it_suits_you="High-energy color pop for gym and outdoor runs.",
        styling_tip="Keep the rest of the outfit neutral charcoal or black.",
        url="https://www.google.com/search?tbm=shop&q=Nike+Volt+Trail+Runners",
        url_verified=False,
        source_domain="google.com",
    ),
    FashionItem(
        id="item_black_blazer",
        name="Unstructured Charcoal Knit Blazer",
        brand="Marks & Spencer",
        category="outerwear",
        price_text="₹4,999",
        price_estimate_inr=4999,
        color="charcoal",
        color_hex="#36393F",
        aesthetic_tags=["smart casual", "tailored", "classic"],
        fit_note="Soft shoulder with stretch comfort.",
        why_it_suits_you="Dresses up a basic tee in 5 seconds without feeling stiff.",
        styling_tip="Push sleeves slightly to the forearm over a crisp white tee.",
        url="https://www.google.com/search?tbm=shop&q=Marks+Spencer+Unstructured+Charcoal+Blazer",
        url_verified=False,
        source_domain="google.com",
    ),
]


class FakeSearchBackend(SearchBackend):
    """Deterministic search & outfit backend for offline testing and key-less demos."""

    async def search(
        self,
        query: str,
        category: str,
        max_budget_inr: int | None,
        dna: StyleDNA,
    ) -> list[FashionItem]:
        q = query.lower()
        cat = category.lower()
        pool = list(_SAMPLE_ITEMS)

        def relevance(item: FashionItem) -> tuple[int, int]:
            score = 0
            if cat in ("shoes", "footwear") and item.category == "shoes":
                score += 4
            elif cat in ("tops", "bottoms", "outerwear", "accessories") and item.category == cat:
                score += 4
            elif cat == "apparel" and item.category in ("tops", "bottoms", "outerwear"):
                score += 3
            for word in re.findall(r"[a-z]+", q):
                if word in item.name.lower() or word in item.color.lower() or any(word in t for t in item.aesthetic_tags):
                    score += 2
            if max_budget_inr and item.price_estimate_inr and item.price_estimate_inr <= max_budget_inr:
                score += 2
            return (-score, item.price_estimate_inr or 0)

        pool.sort(key=relevance)
        if max_budget_inr:
            affordable = [i for i in pool if (i.price_estimate_inr or 0) <= max_budget_inr]
            if affordable:
                pool = affordable + [i for i in pool if i not in affordable]
        return pool[:5]

    async def curate_outfit(
        self,
        occasion: str,
        vibe: str,
        anchor_item: str,
        max_budget_inr: int | None,
        dna: StyleDNA,
    ) -> OutfitLook:
        closet_piece = dna.saved_closet[0] if dna.saved_closet else None
        pieces: list[OutfitPiece] = []
        if closet_piece:
            pieces.append(
                OutfitPiece(
                    slot=closet_piece.category.title(),
                    name=closet_piece.name,
                    color=closet_piece.color,
                    color_hex=closet_piece.color_hex,
                    fit_guidance=closet_piece.fit_note or "Anchor piece from your Saved Closet",
                    from_closet=True,
                    item_id=closet_piece.id,
                    url=closet_piece.url,
                    price_text=closet_piece.price_text,
                )
            )
        else:
            pieces.append(
                OutfitPiece(
                    slot="Top",
                    name=anchor_item or "Relaxed Olive Linen Overshirt",
                    color="olive",
                    color_hex="#556B2F",
                    fit_guidance="Relaxed boxy layer worn open or half-tucked",
                    url="https://www.google.com/search?tbm=shop&q=Relaxed+Olive+Linen+Overshirt",
                    price_text="~₹2,490",
                )
            )

        pieces.extend(
            [
                OutfitPiece(
                    slot="Bottom",
                    name="Pleated Ecru Wide-Leg Trousers",
                    color="cream",
                    color_hex="#EDE6D6",
                    fit_guidance="High-rise relaxed straight drape to balance upper volume",
                    url="https://www.google.com/search?tbm=shop&q=Pleated+Ecru+Wide+Leg+Trousers",
                    price_text="~₹3,290",
                ),
                OutfitPiece(
                    slot="Footwear",
                    name="Palermo Leather Gum-Sole Sneakers",
                    color="navy",
                    color_hex="#20314D",
                    fit_guidance="Low-profile silhouette keeps the trouser break clean",
                    url="https://www.google.com/search?tbm=shop&q=Puma+Palermo+Gum+Sneakers",
                    price_text="~₹5,499",
                ),
                OutfitPiece(
                    slot="Accessory",
                    name="Minimalist Pebble Crossbody Bag",
                    color="warm brown",
                    color_hex="#8B5A3C",
                    fit_guidance="Brings warm leather texture to anchor the neutrals",
                    url="https://www.google.com/search?tbm=shop&q=Cognac+Minimalist+Crossbody+Bag",
                    price_text="~₹2,790",
                ),
            ]
        )
        lid = "look_" + hashlib.sha1(f"{occasion}|{vibe}".encode()).hexdigest()[:8]
        return OutfitLook(
            id=lid,
            title=f"{vibe.title()} — {occasion.title()}",
            occasion=occasion,
            vibe=vibe,
            tags=[vibe.lower(), "minimalist", "smart casual"],
            color_story="60% warm cream & neutrals, 30% earthy olive/navy depth, 10% cognac leather warmth.",
            proportion_tip="Pair a relaxed or open upper layer with clean high-rise trousers for a natural 1/3–2/3 silhouette.",
            styling_hacks=[
                "Leave the overshirt unbuttoned over a fitted neutral tee for effortless movement.",
                "Roll cuffs twice or give trousers one clean hem break above the gum-sole sneakers.",
            ],
            pieces=pieces,
            total_estimate_text="~₹11,000 - ₹14,000",
            total_estimate_inr=12500,
        )

    async def curate_outfit_deck(
        self,
        occasion: str,
        vibe: str,
        anchor_item: str,
        max_budget_inr: int | None,
        exclude_look_ids: list[str],
        dna: StyleDNA,
    ) -> list[OutfitLook]:
        """Build 5 distinct deterministic looks for the swipe stack."""
        primary = await self.curate_outfit(occasion, vibe, anchor_item, max_budget_inr, dna)
        themes = [
            ("Midnight Monochrome Sharp", "tailored nocturnal", 9800, "~₹9,800", ["monochrome", "sharp", "evening"], [
                OutfitPiece(slot="Outerwear", name="Unstructured Charcoal Knit Blazer", brand="Marks & Spencer", store="myntra.com", color="charcoal", color_hex="#36393F", fit_guidance="Soft shoulder drape", url="https://www.google.com/search?tbm=shop&q=Charcoal+Knit+Blazer", price_text="₹4,999", price_estimate_inr=4999),
                OutfitPiece(slot="Top", name="Supima Black Fitted Knit Tee", brand="Uniqlo", store="uniqlo.com", color="black", color_hex="#18181B", fit_guidance="Clean crew neck base", url="https://www.google.com/search?tbm=shop&q=Uniqlo+Supima+Black+Tee", price_text="₹1,290", price_estimate_inr=1290),
                OutfitPiece(slot="Bottom", name="Relaxed Straight Tapered Trousers", brand="Zara", store="zara.com", color="charcoal", color_hex="#2D3036", fit_guidance="Ankle-skimming break", url="https://www.google.com/search?tbm=shop&q=Zara+Relaxed+Trousers", price_text="₹3,490", price_estimate_inr=3490),
            ]),
            ("Terracotta & Ecru Ease", "warm earthy minimal", 7380, "~₹7,380", ["earthy", "warm", "minimalist"], [
                OutfitPiece(slot="Top", name="Heavyweight Boxy Cotton Tee", brand="H&M", store="hm.com", color="terracotta", color_hex="#C66B4B", fit_guidance="Half-tucked relaxed shoulder", url="https://www.google.com/search?tbm=shop&q=HM+Terracotta+Boxy+Tee", price_text="₹1,299", price_estimate_inr=1299),
                OutfitPiece(slot="Bottom", name="Pleated Ecru Wide-Leg Trousers", brand="Zara", store="zara.com", color="cream", color_hex="#EDE6D6", fit_guidance="High-rise fluid drape", url="https://www.google.com/search?tbm=shop&q=Ecru+Wide+Leg+Trousers", price_text="₹3,290", price_estimate_inr=3290),
                OutfitPiece(slot="Accessory", name="Minimalist Pebble Crossbody Bag", brand="Mango", store="ajio.com", color="warm brown", color_hex="#8B5A3C", fit_guidance="Ties in warm contrast", url="https://www.google.com/search?tbm=shop&q=Mango+Brown+Crossbody+Bag", price_text="₹2,790", price_estimate_inr=2790),
            ]),
            ("Riviera Linen Layer", "quiet luxury", 10780, "~₹10,780", ["quiet luxury", "linen", "airy"], [
                OutfitPiece(slot="Top", name="Camp Collar Natural Linen Shirt", brand="Andamen", store="andamen.com", color="sand", color_hex="#D8CBB8", fit_guidance="Breezy relaxed button-down", url="https://www.google.com/search?tbm=shop&q=Andamen+Linen+Shirt", price_text="₹3,690", price_estimate_inr=3690),
                OutfitPiece(slot="Bottom", name="Olive Tailored Drawstring Chinos", brand="Rare Rabbit", store="myntra.com", color="olive", color_hex="#556B2F", fit_guidance="Smart tapered leg", url="https://www.google.com/search?tbm=shop&q=Olive+Tailored+Chinos", price_text="₹2,999", price_estimate_inr=2999),
                OutfitPiece(slot="Footwear", name="Suede Penny Loafers", brand="H&M", store="hm.com", color="warm brown", color_hex="#7A4E36", fit_guidance="Wear with no-show socks", url="https://www.google.com/search?tbm=shop&q=Suede+Loafers", price_text="₹3,999", price_estimate_inr=3999),
            ]),
            ("Retro Terrace Street", "streetwear chic", 11290, "~₹11,290", ["streetwear", "retro", "casual"], [
                OutfitPiece(slot="Outerwear", name="Washed Indigo Chore Jacket", brand="Levi's", store="ajio.com", color="indigo", color_hex="#293E5C", fit_guidance="Cropped boxy hem", url="https://www.google.com/search?tbm=shop&q=Levis+Chore+Jacket", price_text="₹4,499", price_estimate_inr=4499),
                OutfitPiece(slot="Top", name="Cream Waffle Knit Henley", brand="Uniqlo", store="uniqlo.com", color="cream", color_hex="#F3EDE0", fit_guidance="Texture under open jacket", url="https://www.google.com/search?tbm=shop&q=Uniqlo+Waffle+Henley", price_text="₹1,990", price_estimate_inr=1990),
                OutfitPiece(slot="Footwear", name="Palermo Leather Gum-Sole Sneakers", brand="Puma", store="puma.com", color="navy", color_hex="#20314D", fit_guidance="Clean low-profile sole", url="https://www.google.com/search?tbm=shop&q=Puma+Palermo+Navy", price_text="₹5,499", price_estimate_inr=5499),
            ]),
        ]
        looks: list[OutfitLook] = [primary]
        for idx, (title, tvibe, est_inr, est_txt, tags, pcs) in enumerate(themes, start=1):
            lid = "look_" + hashlib.sha1(f"{occasion}|{title}|{idx}".encode()).hexdigest()[:8]
            looks.append(
                OutfitLook(
                    id=lid,
                    title=title,
                    occasion=occasion,
                    vibe=tvibe,
                    tags=tags,
                    color_story="60% balanced neutral anchor, 30% rich tonal contrast, 10% warm leather accent.",
                    proportion_tip="Structured upper frame meets relaxed straight leg for effortless length.",
                    styling_hacks=["Half-tuck the base layer", "Leave top collar open to frame neckline"],
                    pieces=pcs,
                    total_estimate_text=est_txt,
                    total_estimate_inr=est_inr,
                )
            )
        ex = set(exclude_look_ids)
        filtered = [lk for lk in looks if lk.id not in ex]
        return filtered or looks


class FakeVisionBackend(VisionBackend):
    def analyze_complexion(self, image: bytes, mime_type: str) -> ComplexionEstimate:
        return ComplexionEstimate(
            skin_tone="medium",
            undertone="warm",
            color_season="Autumn",
            confidence="medium",
            recommended_colors=["olive", "terracotta", "cream", "warm brown", "mustard"],
            note="Offline demo estimate — adjust skin tone or undertone if lighting feels off.",
        )

    def analyze_outfit(self, image: bytes, mime_type: str, note: str = "") -> OutfitCheckResult:
        return OutfitCheckResult(
            overall_vibe="Clean Minimalist Casual",
            what_works=[
                "Balanced proportions between the top and trousers.",
                "Cohesive neutral palette that reads intentional.",
            ],
            elevation_tips=[
                "Try a gentle front tuck to sharpen the waistline.",
                "Add a textured watch or cognac belt for visual contrast.",
            ],
            suggested_additions=["Warm Brown Leather Belt", "Retro Gum-Sole Sneakers"],
            rating_out_of_10=8,
            honest_bestie_summary="Super clean base! A quick front tuck and one warm accessory will take this from solid to effortlessly styled.",
        )

    def transcribe_audio(self, audio: bytes, mime_type: str) -> str:
        return "Build a smart-casual date night outfit"


class OfflineStylistService(StylistService):
    """Key-less ADK-compatible service for offline demos, tests, and harness validation."""

    offline_mode = True
    requires_key = False

    def __init__(self, store: PreferenceStore | None = None):
        super().__init__(
            store=store or PreferenceStore(persist=False),
            vision=FakeVisionBackend(),
        )
        self.search_backend = FakeSearchBackend()

    async def chat(self, req: ChatRequest, request_id: str | None = None) -> ChatResponse:
        async with self._lock_for(req.session_id):
            dna = await self.ensure_session(req.user_id, req.session_id, req.style_dna)
            m = req.message.strip()
            ml = m.lower()
            ui = UIAction()
            tools: list[str] = []

            if re.search(r"\b(no thanks|never mind|stop pitching|not shopping|leave me alone)\b", ml):
                dna.declined = True
                dna = self.store.save(dna)
                return ChatResponse(
                    reply="Totally respect that — zero pressure! I'm always just a friendly chat away whenever you want company.",
                    ui_action=ui,
                    style_dna=dna,
                    tools_used=["set_shopping_boundary"],
                )

            if "forget my profile" in ml or "forget everything" in ml:
                dna = self.store.forget(req.user_id)
                return ChatResponse(
                    reply="Done — I've cleared your Style DNA, saved closet, swipes, and complexion notes.",
                    ui_action=ui,
                    style_dna=dna,
                    tools_used=["forget_style_profile"],
                )

            if "what do you know about me" in ml or "my profile" in ml or "style dna" in ml:
                summary = summarize_dna_for_prompt(dna)
                return ChatResponse(
                    reply=f"Here's what I've learned about your style so far:\n{summary}",
                    ui_action=ui,
                    style_dna=dna,
                    tools_used=["get_style_profile_and_closet"],
                )

            if "closet" in ml or "saved items" in ml:
                ui = UIAction(type="closet", items=dna.saved_closet)
                reply = (
                    f"Opening your Saved Closet ({len(dna.saved_closet)} pieces)! Want me to build an outfit around one of them?"
                    if dna.saved_closet
                    else "Your Saved Closet is empty so far — swipe right on any pieces you love to save them here!"
                )
                return ChatResponse(reply=reply, ui_action=ui, style_dna=dna, tools_used=["open_saved_closet"])

            if re.search(r"\b(weather|pasta|chai|recipe|capital of|stressed|joke|python|movie)\b", ml):
                off_reply = "I'd say keep it simple: good ingredients, a deep breath, and take things one step at a time!"
                if "pasta" in ml:
                    off_reply = "Save half a cup of starchy pasta water and emulsify it with butter or olive oil off the heat — instant silky sauce!"
                elif "weather" in ml:
                    off_reply = "I can't check live local forecasts directly without searching, though checking radar before heading out always helps!"
                elif "stressed" in ml:
                    off_reply = "Take a slow breath — you've got this, and breaking it into the first tiny step helps fast."
                if dna.declined:
                    return ChatResponse(reply=off_reply, ui_action=ui, style_dna=dna)
                return ChatResponse(
                    reply=f"{off_reply} Speaking of good vibes, want to put together a confidence-boosting outfit or swipe a few fresh finds?",
                    ui_action=ui,
                    style_dna=dna,
                )

            if dna.declined and not re.search(r"\b(outfit|shirt|shoes|sneakers|jacket|dress|wear|style|fashion|buy|find|search|look)\b", ml):
                return ChatResponse(
                    reply="Glad we're chatting! Let me know anytime if there's anything else on your mind.",
                    ui_action=ui,
                    style_dna=dna,
                )

            # Preference recording
            if u := re.search(r"\b(warm|cool|neutral)\s+undertone\b", ml):
                dna.undertone = u.group(1)
                dna.color_season = infer_season(dna.skin_tone or "medium", dna.undertone)
                dna = self.store.save(dna)
                tools.append("record_style_preference")

            if re.search(r"\b(outfit|look|what should i wear|style around|date night|wedding|office look|brunch)\b", ml):
                dna.declined = False
                occasion = "date night" if "date" in ml else ("wedding" if "wedding" in ml else ("office" if "office" in ml else "smart casual"))
                vibe = "quiet luxury" if "luxury" in ml else ("streetwear" if "street" in ml else "effortless modern")
                look = await self.search_backend.curate_outfit(occasion, vibe, "", dna.budget_max, dna)
                dna = self.store.save(dna)
                ui = UIAction(type="outfit_board", outfit=look)
                return ChatResponse(
                    reply=(
                        f"I put together a '{look.title}' lookbook on your board! {look.color_story} "
                        f"Pro tip: {look.proportion_tip}"
                    ),
                    ui_action=ui,
                    style_dna=dna,
                    tools_used=[*tools, "curate_outfit"],
                )

            if re.search(r"\b(shoes|sneakers|shirt|jacket|trousers|jeans|bag|clothes|accessories|find|search|show|recommend|buy)\b", ml):
                dna.declined = False
                cat = "shoes" if any(w in ml for w in ("shoe", "sneaker", "loafer")) else (
                    "accessories" if any(w in ml for w in ("bag", "belt", "watch")) else "apparel"
                )
                budget_match = re.search(r"(?:under|below|budget)\s*₹?\s*(\d+)", ml)
                budget = int(budget_match.group(1)) if budget_match else dna.budget_max
                items = await self.search_backend.search(m, cat, budget, dna)
                ranked = rerank_items(items, dna)
                dna = self.store.save(dna)
                ui = UIAction(type="swipe_deck", items=ranked)
                closet_note = (
                    f" Since you saved {dna.saved_closet[0].name}, I weighted picks that complement it."
                    if dna.saved_closet
                    else ""
                )
                return ChatResponse(
                    reply=(
                        f"Pulled {len(ranked)} fresh online picks into your Swipe Deck!{closet_note} "
                        "Swipe right to save to your closet, left to pass, or up to build an outfit around any piece."
                    ),
                    ui_action=ui,
                    style_dna=dna,
                    tools_used=[*tools, "search_fashion_online"],
                )

            if tools:
                return ChatResponse(
                    reply=f"Got it — saved your {dna.undertone} undertone ({dna.color_season} palette)! Want me to search pieces in your best colors?",
                    ui_action=ui,
                    style_dna=dna,
                    tools_used=tools,
                )

            return ChatResponse(
                reply="Hey bestie! Tell me what vibe or occasion you're dressing for — or ask me to find clothes, shoes, or build a full outfit!",
                ui_action=ui,
                style_dna=dna,
            )

    async def stream_chat(self, req: ChatRequest, request_id: str | None = None) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        yield ("status", {"state": "thinking"})
        resp = await self.chat(req, request_id=request_id)
        if resp.ui_action.type != "none":
            yield ("ui", {"ui_action": resp.ui_action.model_dump(), "style_dna": resp.style_dna.model_dump()})
        words = resp.reply.split(" ")
        for i in range(0, len(words), 4):
            yield ("text", {"delta": " ".join(words[i : i + 4]) + (" " if i + 4 < len(words) else "")})
        yield ("done", resp.model_dump())
