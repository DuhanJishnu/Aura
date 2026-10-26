import type { NextRequest } from "next/server";

/**
 * Same-origin proxy to the FastAPI backend, so the browser never needs CORS or the backend's address.
 * Streams the response body, which is what makes server-sent events (/api/chat/stream) work.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const PASS_THROUGH = ["content-type", "cache-control"];

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const target = `${BACKEND}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  // so the backend's per-client rate limit sees the real client (run it with TRUST_PROXY=1)
  const client = req.headers.get("x-forwarded-for") ?? req.headers.get("x-real-ip");
  if (client) headers.set("x-forwarded-for", client);

  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.text(),
      cache: "no-store",
      signal: req.signal,
    });
    const out = new Headers();
    for (const name of PASS_THROUGH) {
      const value = upstream.headers.get(name);
      if (value) out.set(name, value);
    }
    out.set("X-Accel-Buffering", "no");   // do not let a reverse proxy buffer the event stream
    return new Response(upstream.body, { status: upstream.status, headers: out });
  } catch {
    return Response.json({ detail: "The shopping service is not reachable right now. Please try again shortly." }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST };
