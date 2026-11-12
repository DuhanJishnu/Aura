import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FashionItem, StyleDNA } from "@/lib/types";
import { useShopper } from "./useShopper";

const enc = new TextEncoder();
const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

const sampleItem: FashionItem = {
  id: "item_1",
  name: "Relaxed Olive Linen Overshirt",
  brand: "Uniqlo",
  category: "tops",
  price_text: "₹2,490",
  color: "olive",
  color_hex: "#556B2F",
  aesthetic_tags: ["minimalist", "linen"],
  fit_note: "Relaxed drape",
  why_it_suits_you: "Great for warm undertones",
  styling_tip: "Layer over cream tee",
  url: "https://example.com/overshirt",
  url_verified: true,
  source_domain: "uniqlo.com",
  match_score: 92,
  match_reasons: ["Matches minimalist taste"],
};

const emptyDna: StyleDNA = {
  user_id: "u1",
  sizes: {},
  aesthetics: {},
  liked_colors: [],
  disliked_colors: [],
  liked_brands: [],
  disliked_brands: [],
  saved_closet: [],
  saved_outfits: [],
  disliked_item_keys: [],
  swipe_history: [],
  facts: [],
  declined: false,
};

const deckUi = { type: "swipe_deck", items: [sampleItem], outfit: null, focus_item: null, photo_mode: null };
const noneUi = { type: "none", items: [], outfit: null, focus_item: null, photo_mode: null };

interface Call {
  url: string;
  body?: Record<string, unknown>;
}

function install(chatStream: string | (() => Response)): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url, body });
      const json = (d: unknown) => new Response(JSON.stringify(d), { headers: { "content-type": "application/json" } });
      if (url === "/api/chat/stream") {
        if (typeof chatStream !== "string") return chatStream();
        return new Response(
          new ReadableStream({
            start(c) {
              for (let i = 0; i < chatStream.length; i += 15) c.enqueue(enc.encode(chatStream.slice(i, i + 15)));
              c.close();
            },
          }),
        );
      }
      if (url.startsWith("/api/profile/sync")) return json(emptyDna);
      if (url.startsWith("/api/profile")) return json(emptyDna);
      if (url === "/api/swipe") {
        return json({
          style_dna: { ...emptyDna, saved_closet: [sampleItem] },
          reaction: "Saved Relaxed Olive Linen Overshirt to your closet!",
          stats: { liked: 1, passed: 0, closet: 1 },
        });
      }
      return new Response("{}", { status: 404 });
    }),
  );
  return calls;
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

const fullStream =
  sse("status", { state: "thinking" }) +
  sse("ui", { ui_action: deckUi, style_dna: emptyDna }) +
  sse("text", { delta: "Pulled fresh picks " }) +
  sse("text", { delta: "into your Swipe Deck!" }) +
  sse("done", {
    reply: "Pulled fresh picks into your Swipe Deck!",
    ui_action: deckUi,
    style_dna: emptyDna,
    tools_used: ["search_fashion_online"],
  });

describe("useShopper", () => {
  it("streams chat and loads Swipe Deck on ui event", async () => {
    const calls = install(fullStream);
    const { result } = renderHook(() => useShopper());
    await waitFor(() => expect(result.current.ready).toBe(true));

    await act(async () => {
      await result.current.send("find me olive linen overshirts");
    });

    expect(result.current.panel.kind).toBe("swipe_deck");
    expect(result.current.messages.at(-1)).toMatchObject({
      role: "bot",
      text: "Pulled fresh picks into your Swipe Deck!",
    });
    expect(calls.some((c) => c.url === "/api/chat/stream")).toBe(true);
  });

  it("saves liked swipes to Style DNA and localStorage", async () => {
    install(fullStream);
    const { result } = renderHook(() => useShopper());
    await waitFor(() => expect(result.current.ready).toBe(true));

    await act(async () => {
      const res = await result.current.swipe(sampleItem, "like");
      expect(res?.stats.closet).toBe(1);
    });

    expect(result.current.styleDna?.saved_closet).toHaveLength(1);
    expect(localStorage.getItem("shopper_style_dna_v1")).toContain("Relaxed Olive Linen Overshirt");
  });

  it("surfaces 429 rate-limit messages cleanly and recovers", async () => {
    install(() => new Response(JSON.stringify({ detail: "Too many requests." }), { status: 429 }));
    const { result } = renderHook(() => useShopper());
    await waitFor(() => expect(result.current.ready).toBe(true));
    await act(async () => {
      await result.current.send("hi");
    });
    expect(result.current.messages.at(-1)).toMatchObject({ role: "err", text: expect.stringContaining("Too many requests") });

    install(
      sse("text", { delta: "Hey!" }) +
        sse("done", { reply: "Hey!", ui_action: noneUi, style_dna: emptyDna, tools_used: [] }),
    );
    await act(async () => {
      await result.current.send("hi again");
    });
    expect(result.current.messages.at(-1)).toMatchObject({ role: "bot", text: "Hey!" });
  });
});
