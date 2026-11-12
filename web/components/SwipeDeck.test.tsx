import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { FashionItem } from "@/lib/types";
import SwipeDeck from "./SwipeDeck";

function makeItem(idx: number): FashionItem {
  return {
    id: `i${idx}`,
    name: `Item ${idx}`,
    brand: idx % 2 === 0 ? "Puma" : "Uniqlo",
    category: "shoes",
    price_text: `₹${2000 + idx * 100}`,
    color: "olive",
    color_hex: "#556B2F",
    aesthetic_tags: ["minimalist", "linen"],
    fit_note: "Boxy relaxed drape",
    why_it_suits_you: "Great for earthy styling",
    styling_tip: "Layer over ecru tee",
    url: `https://example.com/${idx}`,
    url_verified: true,
    source_domain: "uniqlo.com",
    image_url: `https://cdn.example.com/${idx}.jpg`,
    image_source: "retailer",
    match_score: 94,
    match_reasons: ["Matches minimalist taste"],
  };
}

describe("SwipeDeck", () => {
  it("keeps front face image-first without tags/tips, supports Save/Skip/Buy/Style This", async () => {
    const items = [makeItem(1), makeItem(2)];
    const onSwipe = vi.fn(async () => ({ reaction: "Saved to closet!" }));
    const onStyleAround = vi.fn();
    const onBuy = vi.fn();

    render(
      <SwipeDeck
        items={items}
        deckId="deck_1"
        onSwipe={onSwipe}
        onBuy={onBuy}
        onStyleAround={onStyleAround}
        onAskOpinion={vi.fn()}
        onOpenDetail={vi.fn()}
        onSwitchToGrid={vi.fn()}
        onFindMore={vi.fn()}
      />,
    );

    // Front shows image + name + price only (no tags/tips/match score)
    expect(screen.getByText("Item 1")).toBeInTheDocument();
    expect(screen.getByText("₹2100")).toBeInTheDocument();
    expect(screen.queryByText("Layer over ecru tee")).not.toBeInTheDocument();
    expect(screen.queryByText(/99% MATCH/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Card 1 of 2/)).toBeInTheDocument();

    // Right / Save
    fireEvent.click(screen.getByRole("button", { name: "Like and save to closet" }));
    expect(onSwipe).toHaveBeenCalledWith(items[0], "like");

    // Card 2: toggle Info to access Style This, then click Buy
    expect(await screen.findByText("Item 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Toggle item details" }));
    expect(screen.getByText("Layer over ecru tee")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Style This/i }));
    await waitFor(() => expect(onStyleAround).toHaveBeenCalledWith(items[1]));

    // Up / Buy button
    fireEvent.click(screen.getByRole("button", { name: "Buy this item" }));
    expect(onBuy).toHaveBeenCalledWith(items[1]);
    expect(onSwipe).toHaveBeenCalledWith(items[1], "like");

    expect(await screen.findByText(/You've seen all 2 picks!/i)).toBeInTheDocument();
  });

  it("fires onNeedMore once at <=3 remaining cards and preserves index when items append with same deckId", async () => {
    const initial = [makeItem(1), makeItem(2), makeItem(3), makeItem(4)];
    const onNeedMore = vi.fn();
    const onSwipe = vi.fn(async () => ({ reaction: "ok" }));

    const { rerender } = render(
      <SwipeDeck
        items={initial}
        deckId="deck_same"
        onSwipe={onSwipe}
        onStyleAround={vi.fn()}
        onAskOpinion={vi.fn()}
        onOpenDetail={vi.fn()}
        onSwitchToGrid={vi.fn()}
        onFindMore={vi.fn()}
        onNeedMore={onNeedMore}
      />,
    );

    expect(onNeedMore).not.toHaveBeenCalled();

    // Advance 1 card -> 3 remain -> fires onNeedMore once
    fireEvent.click(screen.getByRole("button", { name: "Pass" }));
    expect(await screen.findByText("Item 2")).toBeInTheDocument();
    expect(onNeedMore).toHaveBeenCalledTimes(1);

    // Appending more items with the SAME deckId keeps current card at Item 2 (Card 2 of 6)
    const appended = [...initial, makeItem(5), makeItem(6)];
    rerender(
      <SwipeDeck
        items={appended}
        deckId="deck_same"
        onSwipe={onSwipe}
        onStyleAround={vi.fn()}
        onAskOpinion={vi.fn()}
        onOpenDetail={vi.fn()}
        onSwitchToGrid={vi.fn()}
        onFindMore={vi.fn()}
        onNeedMore={onNeedMore}
      />,
    );

    expect(screen.getByText("Item 2")).toBeInTheDocument();
    expect(screen.getByText(/Card 2 of 6/)).toBeInTheDocument();
    expect(onNeedMore).toHaveBeenCalledTimes(1);
  });
});
