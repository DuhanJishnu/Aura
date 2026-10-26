import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useShopper } from "./useShopper";

const enc = new TextEncoder();
const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const ui = { type: "show_products", filters: { use: "sports" }, product_id: null, product_ids: [3, 1], order_id: null };
const none = { type: "none", filters: {}, product_id: null, product_ids: [], order_id: null };
const shoe = (id: number) => ({ id, name: `Shoe ${id}`, brand: "Nike", price: 1000 + id, use_type: "sports", color: "black", rating: 4.5, description: "d", category: "shoes", sizes_in_stock: [9] });

interface Call { url: string; body?: Record<string, unknown> }

/** A fake backend behind /api/*; `chat` is the text of the event stream (or a Response) for /api/chat/stream. */
function install(chat: string | (() => Response)): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ url, body });
    const json = (d: unknown) => new Response(JSON.stringify(d), { headers: { "content-type": "application/json" } });
    if (url === "/api/chat/stream") {
      if (typeof chat !== "string") return chat();
      return new Response(new ReadableStream({ start(c) { for (let i = 0; i < chat.length; i += 11) c.enqueue(enc.encode(chat.slice(i, i + 11))); c.close(); } }));
    }
    if (url.startsWith("/api/products?")) return json({ products: new URLSearchParams(url.split("?")[1]).get("ids")!.split(",").map((i) => shoe(Number(i))) });
    if (url.startsWith("/api/products/")) return json(shoe(Number(url.split("/").pop())));
    if (url.startsWith("/api/cart")) return json({ items: [], total: 0 });
    if (url.startsWith("/api/profile")) return json({ size: null, facts: [], pending_estimate: null });
    return new Response("{}", { status: 404 });
  }));
  return calls;
}

beforeEach(() => { sessionStorage.clear(); localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());

const full = sse("status", { state: "thinking" }) + sse("ui", { ui_action: ui, slots: { use: "sports", size: 9 } })
  + sse("text", { delta: "Here are some " }) + sse("text", { delta: "options." })
  + sse("done", { reply: "Here are some options.", slots: { use: "sports", size: 9 }, ui_action: ui });

describe("useShopper", () => {
  it("runs a streamed turn: the products load as soon as the ui event arrives, then the reply lands", async () => {
    const calls = install(full);
    const { result } = renderHook(() => useShopper());
    await waitFor(() => expect(result.current.ready).toBe(true));

    await act(async () => { await result.current.send("sports shoes, size 9"); });

    expect(result.current.messages.map((m) => [m.role, m.text])).toEqual([
      ["bot", expect.stringContaining("shopping buddy")], ["user", "sports shoes, size 9"], ["bot", "Here are some options."],
    ]);
    expect(result.current.panel.kind).toBe("grid");
    expect(result.current.panel.kind === "grid" && result.current.panel.products.map((p) => p.id)).toEqual([3, 1]);
    expect(result.current.slots).toMatchObject({ use: "sports", size: 9 });
    expect(result.current.thinking).toBe(false);
    // the grid was fetched once (from the ui event), not a second time when "done" arrived
    expect(calls.filter((c) => c.url.startsWith("/api/products?")).length).toBe(1);
    expect(calls.find((c) => c.url === "/api/chat/stream")!.body).toMatchObject({ message: "sports shoes, size 9", focus_product_id: null });
  });

  it("applies the action from `done` when the server sent no ui event, and tells the server which shoe is open", async () => {
    const focus = { ...none, type: "focus_product", product_id: 5 };
    const calls = install(sse("text", { delta: "Here's it." }) + sse("done", { reply: "Here's it.", slots: {}, ui_action: focus }));
    const { result } = renderHook(() => useShopper());
    await waitFor(() => expect(result.current.ready).toBe(true));
    await act(async () => { await result.current.send("show me the second one"); });
    expect(result.current.panel).toMatchObject({ kind: "detail", product: { id: 5 } });

    const calls2 = install(sse("done", { reply: "ok", slots: {}, ui_action: none }));
    await act(async () => { await result.current.send("what do you think of it?"); });
    expect(calls2.find((c) => c.url === "/api/chat/stream")!.body).toMatchObject({ focus_product_id: 5 });
    expect(calls.some((c) => c.url === "/api/products/5")).toBe(true);
  });

  it("shows the server's message on a rate limit and lets the shopper try again", async () => {
    install(() => new Response(JSON.stringify({ detail: "Too many requests. Please slow down a little." }), { status: 429 }));
    const { result } = renderHook(() => useShopper());
    await waitFor(() => expect(result.current.ready).toBe(true));
    await act(async () => { await result.current.send("hi"); });
    expect(result.current.messages.at(-1)).toMatchObject({ role: "err", text: expect.stringContaining("Too many requests") });
    expect(result.current.thinking).toBe(false);

    install(sse("text", { delta: "Hi!" }) + sse("done", { reply: "Hi!", slots: {}, ui_action: none }));
    await act(async () => { await result.current.send("hi again"); });
    expect(result.current.messages.at(-1)).toMatchObject({ role: "bot", text: "Hi!" });
  });

  it("ignores empty messages and does nothing before ids are ready", async () => {
    const calls = install(full);
    const { result } = renderHook(() => useShopper());
    await act(async () => { await result.current.send("   "); });
    expect(calls.filter((c) => c.url === "/api/chat/stream")).toHaveLength(0);
  });

  it("goes back to the list the shopper was looking at", async () => {
    install(full);
    const { result } = renderHook(() => useShopper());
    await waitFor(() => expect(result.current.ready).toBe(true));
    await act(async () => { await result.current.send("sports shoes"); });
    await act(async () => { await result.current.focusProduct(3); });
    expect(result.current.panel.kind).toBe("detail");
    await act(async () => { result.current.goBack(); });
    await waitFor(() => expect(result.current.panel.kind).toBe("grid"));
  });
});
