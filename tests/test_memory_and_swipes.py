from __future__ import annotations

from stylist_agent.memory import (
    PreferenceStore,
    apply_swipe,
    infer_season,
    rerank_items,
    summarize_dna_for_prompt,
)
from stylist_agent.schemas import FashionItem, StyleDNA


def _item(id: str, name: str, color: str, tags: list[str], price: int = 2500, brand: str = "Uniqlo") -> FashionItem:
    return FashionItem(
        id=id,
        name=name,
        brand=brand,
        category="tops",
        price_text=f"₹{price:,}",
        price_estimate_inr=price,
        color=color,
        color_hex="#556B2F",
        aesthetic_tags=tags,
        url=f"https://www.google.com/search?tbm=shop&q={name}",
    )


def test_swipe_like_and_dislike_update_style_dna_and_rerank():
    dna = StyleDNA(user_id="u_swipe", undertone="warm", budget_max=3000)
    olive = _item("i1", "Olive Linen Shirt", "olive", ["minimalist", "linen"], price=2400)
    neon = _item("i2", "Neon Mesh Vest", "neon yellow", ["sporty", "bold"], price=4500, brand="Nike")
    cream = _item("i3", "Cream Minimalist Tee", "cream", ["minimalist"], price=1800)

    reaction_like = apply_swipe(dna, olive, "like")
    assert "Saved Olive Linen Shirt" in reaction_like
    assert len(dna.saved_closet) == 1
    assert dna.aesthetics["minimalist"] > 0
    assert "olive" in dna.liked_colors

    reaction_pass = apply_swipe(dna, neon, "dislike")
    assert "passing on Neon Mesh Vest" in reaction_pass
    assert len(dna.disliked_item_keys) == 1

    ranked = rerank_items([neon, cream, olive], dna)
    assert [i.id for i in ranked] == ["i1", "i3"]  # neon excluded, olive boosted highest
    assert ranked[0].match_score >= ranked[1].match_score
    assert any("undertone" in r.lower() or "minimalist" in r.lower() for r in ranked[0].match_reasons)


def test_super_like_encourages_outfit_curation():
    dna = StyleDNA(user_id="u_super")
    shirt = _item("i1", "Sage Overshirt", "sage", ["quiet luxury"])
    msg = apply_swipe(dna, shirt, "super_like")
    assert "style an outfit around it" in msg.lower()
    assert dna.aesthetics["quiet luxury"] >= 2.5
    assert len(dna.saved_closet) == 1


def test_preference_store_persistence_sync_and_forget(tmp_path):
    store = PreferenceStore(base_dir=tmp_path / "p", persist=True)
    dna = store.get("alice")
    dna.sizes["shoes"] = "8"
    apply_swipe(dna, _item("i1", "Cream Trouser", "cream", ["tailored"]), "like")
    store.save(dna)

    # Fresh store reads persisted JSON cleanly
    store2 = PreferenceStore(base_dir=tmp_path / "p", persist=True)
    loaded = store2.get("alice")
    assert loaded.sizes["shoes"] == "8"
    assert len(loaded.saved_closet) == 1

    # Client sync restores taste on a cold/empty server store
    cold_store = PreferenceStore(base_dir=tmp_path / "cold", persist=True)
    synced = cold_store.sync_from_client("alice", loaded)
    assert synced.sizes["shoes"] == "8"
    assert len(synced.saved_closet) == 1

    # Forget deletes state and disk file
    cleared = cold_store.forget("alice")
    assert cleared.saved_closet == []
    assert not (tmp_path / "cold" / "alice.json").exists()


def test_season_inference_and_prompt_summary():
    assert infer_season("medium", "warm") == "Autumn"
    assert infer_season("fair", "cool") == "Summer"

    dna = StyleDNA(
        user_id="u1",
        sizes={"shoes": "9"},
        undertone="warm",
        color_season="Autumn",
        liked_colors=["olive"],
        disliked_colors=["neon"],
        declined=True,
    )
    summary = summarize_dna_for_prompt(dna)
    assert "shoes=9" in summary
    assert "Autumn" in summary
    assert "BOUNDARY" in summary
