import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { OutfitLook } from "@/lib/types";
import LookDeck from "./LookDeck";

const looks: OutfitLook[] = [
  {
    id: "look_1",
    title: "Olive Linen & Ecru Ease",
    occasion: "Date night",
    vibe: "quiet luxury",
    tags: ["minimalist", "linen"],
    color_story: "Warm cream + earthy olive",
    proportion_tip: "Boxy top over relaxed trousers",
    styling_hacks: ["Leave top 2 buttons open"],
    total_estimate_text: "~₹8,900",
    pieces: [
      {
        slot: "Top",
        name: "Olive Overshirt",
        brand: "Uniqlo",
        store: "uniqlo.com",
        color: "olive",
        color_hex: "#556B2F",
        fit_guidance: "Relaxed",
        from_closet: false,
        search_query: "Uniqlo olive overshirt",
        url: "https://example.com/1",
        price_text: "₹2,490",
      },
    ],
  },
  {
    id: "look_2",
    title: "Midnight Monochrome Sharp",
    occasion: "Date night",
    vibe: "tailored",
    tags: ["monochrome"],
    color_story: "Charcoal + black tones",
    proportion_tip: "Clean tapered leg",
    styling_hacks: ["Push blazer sleeves to forearm"],
    total_estimate_text: "~₹9,800",
    pieces: [
      {
        slot: "Outerwear",
        name: "Charcoal Knit Blazer",
        brand: "M&S",
        store: "myntra.com",
        color: "charcoal",
        color_hex: "#36393F",
        fit_guidance: "Soft shoulder",
        from_closet: false,
        search_query: "charcoal knit blazer",
        url: "https://example.com/2",
        price_text: "₹4,999",
      },
    ],
  },
];

describe("LookDeck", () => {
  it("supports Save, Skip, Undo, breakdown toggle, and Want More", async () => {
    const onSwipe = vi.fn(async () => ({}));
    const onLoadMore = vi.fn();

    render(<LookDeck looks={looks} onSwipe={onSwipe} onLoadMore={onLoadMore} />);

    expect(screen.getByText("Olive Linen & Ecru Ease")).toBeInTheDocument();
    expect(screen.getByText("Look 1 of 2")).toBeInTheDocument();

    // Expand details via Info button
    fireEvent.click(screen.getByRole("button", { name: "Toggle look breakdown" }));
    expect(screen.getByText("Olive Overshirt")).toBeInTheDocument();

    // Save first look -> moves to look 2
    fireEvent.click(screen.getByRole("button", { name: "Save look to wishlist" }));
    expect(onSwipe).toHaveBeenCalledWith(looks[0], "save");
    expect(await screen.findByText("Midnight Monochrome Sharp")).toBeInTheDocument();

    // Undo restores look 1
    fireEvent.click(screen.getByRole("button", { name: "Undo last swipe" }));
    expect(await screen.findByText("Olive Linen & Ecru Ease")).toBeInTheDocument();

    // Swipe through both looks -> Want more
    fireEvent.click(screen.getByRole("button", { name: "Skip look" }));
    fireEvent.click(screen.getByRole("button", { name: "Buy this look" }));
    expect(onSwipe).toHaveBeenCalledWith(looks[1], "buy_intent");

    fireEvent.click(await screen.findByRole("button", { name: "Want more looks?" }));
    expect(onLoadMore).toHaveBeenCalled();
  });
});
