// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "./route";

const ctx = (...path: string[]) => ({ params: Promise.resolve({ path }) });
afterEach(() => vi.unstubAllGlobals());

describe("/api proxy", () => {
  it("forwards path, query, body and content type, and the client address for rate limiting", async () => {
    const f = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 201, headers: { "content-type": "application/json", "set-cookie": "x=1" } }));
    vi.stubGlobal("fetch", f);
    const req = new NextRequest("http://localhost/api/cart/add?x=1", {
      method: "POST", body: JSON.stringify({ a: 1 }), headers: { "content-type": "application/json", "x-forwarded-for": "1.2.3.4", cookie: "secret=1" },
    });
    const res = await POST(req, ctx("cart", "add"));
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/cart/add?x=1");
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"a":1}');
    const sent = init.headers as Headers;
    expect(sent.get("content-type")).toBe("application/json");
    expect(sent.get("x-forwarded-for")).toBe("1.2.3.4");
    expect(sent.get("cookie")).toBeNull();            // nothing else leaks to the backend
    expect(res.status).toBe(201);
    expect(res.headers.get("set-cookie")).toBeNull();  // and nothing else leaks back
    expect(await res.json()).toEqual({ ok: true });
  });

  it("streams the response instead of buffering it, and asks proxies not to buffer either", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => { release = r; });
    const enc = new TextEncoder();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new ReadableStream({
      async start(c) { c.enqueue(enc.encode("event: ui\ndata: {}\n\n")); await gate; c.enqueue(enc.encode("event: done\ndata: {}\n\n")); c.close(); },
    }), { headers: { "content-type": "text/event-stream" } })));
    const res = await POST(new NextRequest("http://localhost/api/chat/stream", { method: "POST", body: "{}" }), ctx("chat", "stream"));
    expect(res.headers.get("content-type")).toBe("text/event-stream");
    expect(res.headers.get("x-accel-buffering")).toBe("no");
    const reader = res.body!.getReader();
    const first = await reader.read();                 // arrives while the upstream is still open
    expect(new TextDecoder().decode(first.value)).toContain("event: ui");
    release();
    expect(new TextDecoder().decode((await reader.read()).value)).toContain("event: done");
  });

  it("passes a backend error through, and answers 502 when the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Catalog missing." }), { status: 503, headers: { "content-type": "application/json" } })));
    const bad = await GET(new NextRequest("http://localhost/api/products"), ctx("products"));
    expect(bad.status).toBe(503);
    expect(await bad.json()).toEqual({ detail: "Catalog missing." });

    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    const down = await GET(new NextRequest("http://localhost/api/products"), ctx("products"));
    expect(down.status).toBe(502);
    expect((await down.json()).detail).toMatch(/not reachable/);
  });
});
