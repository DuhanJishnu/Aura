import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { FashionItem } from "@/lib/types";
import SwipeDeck from "./SwipeDeck";

const items: FashionItem[] = [
  {
    id: "i1",
    name: "Olive Linen Overshirt",
    brand: "Uniqlo",
    category: "tops",
    price_text: "₹2,490",
    color: "olive",
    color_hex: "#556B2F",
    aesthetic_tags: ["minimalist", "linen"],
    fit_note: "Boxy relaxed drape",
    why_it_suits_you: "Great for earthy styling",
    styling_tip: "Layer over ecru tee",
    url: "https://example.com/1",
    url_verified: true,
    source_domain: "uniqlo.com",
    match_score: 94,
    match_reasons: ["Matches minimalist taste"],
  },
  {
    id: "i2",
    name: "Retro Gum Sneakers",
    brand: "Puma",
    category: "shoes",
    price_text: "₹5,499",
    color: "navy",
    color_hex: "#20314D",
    aesthetic_tags: ["retro", "casual"],
    fit_note: "True to UK size",
    why_it_suits_you: "Sharp low-profile silhouette",
    styling_tip: "Pair with pleated trousers",
    url: "https://example.com/2",
    url_verified: false,
    source_domain: "google.com",
    match_score: 88,
    match_reasons: [],
  },
];

describe("SwipeDeck", () => {
  it("renders cards and handles Save / Pass / Style This actions", async () => {
    const onSwipe = vi.fn(async () => ({ reaction: "Saved to closet!" }));
    const onStyleAround = vi.fn();

    render(
      <SwipeDeck
        items={items}
        onSwipe={onSwipe}
        onStyleAround={onStyleAround}
        onAskOpinion={vi.fn()}
        onOpenDetail={vi.fn()}
        onSwitchToGrid={vi.fn()}
        onFindMore={vi.fn()}
      />,
    );

    expect(screen.getByText("Olive Linen Overshirt")).toBeInTheDocument();
    expect(screen.getByText(/Card 1 of 2/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Like and save to closet" }));
    expect(onSwipe).toHaveBeenCalledWith(items[0], "like");

    expect(await screen.findByText("Retro Gum Sneakers")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Style outfit around this" }));
    expect(onSwipe).toHaveBeenCalledWith(items[1], "super_like");
    await waitFor(() => expect(onStyleAround).toHaveBeenCalledWith(items[1]));

    expect(await screen.findByText("Deck complete!")).toBeInTheDocument();
  });
});
