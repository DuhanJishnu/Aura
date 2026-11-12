import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { StyleDNA } from "@/lib/types";
import ProfileDrawer from "./ProfileDrawer";

const facts = Array.from({ length: 12 }, (_, idx) => ({
  key: "aesthetic",
  value: `pref-${idx + 1}`,
  source: "stated" as const,
}));

const profile: StyleDNA = {
  user_id: "u1",
  sizes: {},
  aesthetics: { minimalist: 5 },
  liked_colors: [],
  disliked_colors: [],
  liked_brands: [],
  disliked_brands: [],
  saved_closet: [],
  saved_outfits: [],
  disliked_item_keys: [],
  swipe_history: [
    { item_id: "k1", item_name: "Linen Shirt", direction: "like", tags: [], color: "olive", brand: "Uniqlo", timestamp: "2026-11-12T00:00:00Z" },
    { item_id: "k2", item_name: "Neon Tee", direction: "dislike", tags: [], color: "neon", brand: "Zara", timestamp: "2026-11-12T00:01:00Z" },
  ],
  facts,
  declined: false,
};

describe("ProfileDrawer", () => {
  it("renders thumbs-up icon in Liked stat and paginates collapsed Saved Preferences in sets of 5 latest items", () => {
    const { container } = render(
      <ProfileDrawer open profile={profile} onClose={vi.fn()} onPhoto={vi.fn()} onForget={vi.fn()} />
    );

    // Thumbs-up icon replaces Sparkles next to Liked count
    expect(container.querySelector(".lucide-thumbs-up")).toBeTruthy();
    expect(container.querySelector(".lucide-sparkles")).toBeNull();

    // Saved Preferences starts collapsed
    const toggle = screen.getByRole("button", { name: /Saved Preferences \(12\)/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("pref-12")).not.toBeInTheDocument();

    // Expanding shows the 5 latest entries (pref-12 down to pref-8)
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("pref-12")).toBeInTheDocument();
    expect(screen.getByText("pref-8")).toBeInTheDocument();
    expect(screen.queryByText("pref-7")).not.toBeInTheDocument();

    // First View more adds 5 more (down to pref-3)
    fireEvent.click(screen.getByRole("button", { name: /View 5 more \(7 remaining\)/i }));
    expect(screen.getByText("pref-7")).toBeInTheDocument();
    expect(screen.getByText("pref-3")).toBeInTheDocument();
    expect(screen.queryByText("pref-2")).not.toBeInTheDocument();

    // Second View more reveals the remaining 2 (pref-2 and pref-1)
    fireEvent.click(screen.getByRole("button", { name: /View 2 more \(2 remaining\)/i }));
    expect(screen.getByText("pref-2")).toBeInTheDocument();
    expect(screen.getByText("pref-1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /View .* more/i })).not.toBeInTheDocument();
  });
});
