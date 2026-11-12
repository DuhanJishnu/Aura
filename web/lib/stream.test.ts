import { describe, expect, it, vi } from "vitest";
import { drainSse, parseSse, streamChat } from "./stream";

const enc = new TextEncoder();

describe("stream", () => {
  it("parses SSE blocks and handles partial chunks", () => {
    const out = drainSse("event: ui\ndata: {\"a\":1}\n\nevent: text\n");
    expect(out.events).toHaveLength(1);
    expect(out.events[0]).toEqual({ event: "ui", data: { a: 1 } });
    expect(out.rest).toBe("event: text\n");
    expect(parseSse("event: done\ndata: {\"reply\":\"hi\"}").data).toEqual({ reply: "hi" });
  });

  it("streams ui, text deltas, and done", async () => {
    const body = [
      'event: ui\ndata: {"ui_action":{"type":"swipe_deck","items":[]}}\n\n',
      'event: text\ndata: {"delta":"Hey "}\n\n',
      'event: text\ndata: {"delta":"bestie!"}\n\n',
      'event: done\ndata: {"reply":"Hey bestie!","ui_action":{"type":"swipe_deck","items":[]},"style_dna":{"user_id":"u1","sizes":{},"aesthetics":{},"liked_colors":[],"disliked_colors":[],"liked_brands":[],"disliked_brands":[],"saved_closet":[],"saved_outfits":[],"disliked_item_keys":[],"swipe_history":[],"facts":[],"declined":false},"tools_used":[]}\n\n',
    ].join("");

    const mockFetch = vi.fn(async () => new Response(new ReadableStream({
      start(c) {
        c.enqueue(enc.encode(body));
        c.close();
      },
    })));

    const events: string[] = [];
    const resp = await streamChat(
      { session_id: "s1", user_id: "u1", message: "hi" },
      {
        onUi: (ui) => events.push(`ui:${ui.type}`),
        onText: (d) => events.push(`text:${d}`),
        onDone: () => events.push("done"),
      },
      mockFetch as unknown as typeof fetch,
    );

    expect(resp.reply).toBe("Hey bestie!");
    expect(events).toEqual(["ui:swipe_deck", "text:Hey ", "text:bestie!", "done"]);
  });
});
