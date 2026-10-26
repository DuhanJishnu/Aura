import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./api";
import { drainSse, parseSse, streamChat } from "./stream";
import type { ChatRequestBody } from "./types";

const body: ChatRequestBody = { session_id: "s", user_id: "u", message: "hi", focus_product_id: null };

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}
/** A fetch that answers with the given text, delivered in chunks of `size` characters. */
function fakeFetch(text: string, size = 7, status = 200): typeof fetch {
  const enc = new TextEncoder();
  return vi.fn(async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        for (let i = 0; i < text.length; i += size) c.enqueue(enc.encode(text.slice(i, i + size)));
        c.close();
      },
    });
    return new Response(stream, { status, headers: { "content-type": "text/event-stream" } });
  }) as unknown as typeof fetch;
}

const ui = { type: "show_products", filters: {}, product_id: null, product_ids: [3, 1, 2], order_id: null };
const done = { reply: "Here you go", slots: { use: "sports" }, ui_action: ui, policy: { action: "retrieve", rule: "retrieve", fast: false } };

describe("sse parsing", () => {
  it("parses one event and tolerates bad json", () => {
    expect(parseSse('event: ui\ndata: {"a": 1}')).toEqual({ event: "ui", data: { a: 1 } });
    expect(parseSse("event: x\ndata: not json").data).toBeNull();
  });
  it("reassembles events however the network splits them", () => {
    const wire = sse("status", { state: "thinking" }) + sse("text", { delta: "Hi " }) + sse("done", done);
    for (let cut = 1; cut < wire.length; cut += 5) {
      const first = drainSse(wire.slice(0, cut));
      const second = drainSse(first.rest + wire.slice(cut));
      expect([...first.events, ...second.events].map((e) => e.event)).toEqual(["status", "text", "done"]);
      expect(second.rest).toBe("");
    }
  });
});

describe("streamChat", () => {
  it("shows the panel before the words and returns the final response", async () => {
    const order: string[] = [];
    const wire = sse("status", { state: "thinking" }) + sse("ui", { ui_action: ui, slots: { use: "sports" } })
      + sse("text", { delta: "Here you " }) + sse("text", { delta: "go" }) + sse("done", done);
    const result = await streamChat(body, {
      onUi: (a, slots) => order.push(`ui:${a.product_ids.join(",")}:${slots.use}`),
      onText: (d) => order.push(`text:${d}`),
      onDone: (_r, applied) => order.push(`done:${applied}`),
    }, fakeFetch(wire));
    expect(order).toEqual(["ui:3,1,2:sports", "text:Here you ", "text:go", "done:true"]);
    expect(result.reply).toBe("Here you go");
  });

  it("says when no ui event came (so the caller applies the action itself)", async () => {
    const seen: boolean[] = [];
    await streamChat(body, { onDone: (_r, applied) => seen.push(applied) }, fakeFetch(sse("text", { delta: "Hi" }) + sse("done", { ...done, ui_action: { ...ui, type: "none", product_ids: [] } })));
    expect(seen).toEqual([false]);
  });

  it("turns an error event into an ApiError", async () => {
    await expect(streamChat(body, {}, fakeFetch(sse("error", { message: "Something went wrong. Please try again." }))))
      .rejects.toMatchObject({ message: "Something went wrong. Please try again." });
  });

  it("reports a bad status using the server's detail", async () => {
    const f = vi.fn(async () => new Response(JSON.stringify({ detail: "Too many requests. Please slow down a little." }), { status: 429 })) as unknown as typeof fetch;
    await expect(streamChat(body, {}, f)).rejects.toMatchObject({ status: 429, message: "Too many requests. Please slow down a little." });
  });

  it("explains an unreachable server and a cut-off stream", async () => {
    const down = vi.fn(async () => { throw new TypeError("fetch failed"); }) as unknown as typeof fetch;
    await expect(streamChat(body, {}, down)).rejects.toBeInstanceOf(ApiError);
    await expect(streamChat(body, {}, fakeFetch(sse("text", { delta: "Hi" })))).rejects.toThrow(/cut off/);
  });
});
