import type { NextRequest } from "next/server";

/**
 * Same-origin proxy to the FastAPI backend, so the browser never needs CORS or the backend's address.
 * Streams the response body, which is what makes server-sent events (/api/chat/stream) work.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const PASS_THROUGH = ["content-type", "cache-control", "x-request-id", "x-response-time-ms"];

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const target = `${BACKEND}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const client = req.headers.get("x-forwarded-for") ?? req.headers.get("x-real-ip");
  if (client) headers.set("x-forwarded-for", client);
  const token = req.headers.get("x-aura-token");
  if (token) headers.set("x-aura-token", token);
  const auth = req.headers.get("authorization");
  if (auth) headers.set("authorization", auth);
  const rid = req.headers.get("x-request-id");
  if (rid) headers.set("x-request-id", rid);

  try {
    const body =
      req.method === "GET" || req.method === "HEAD" || req.method === "DELETE"
        ? undefined
        : await req.text();
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      cache: "no-store",
      signal: req.signal,
    });
    const out = new Headers();
    for (const name of PASS_THROUGH) {
      const value = upstream.headers.get(name);
      if (value) out.set(name, value);
    }
    out.set("X-Accel-Buffering", "no");
    return new Response(upstream.body, { status: upstream.status, headers: out });
  } catch {
    return Response.json({ detail: "The stylist service is not reachable right now. Please try again shortly." }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE };
