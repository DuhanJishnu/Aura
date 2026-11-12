import { ApiError, authHeaders, detailText } from "./api";
import type { ChatRequestBody, ChatResponse, OutfitLook, StyleDNA, UIAction } from "./types";

export interface SseEvent {
  event: string;
  data: unknown;
}

export function parseSse(block: string): SseEvent {
  let event = "message";
  let raw = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) raw += line.slice(5).trim();
  }
  let data: unknown = null;
  try { data = raw ? JSON.parse(raw) : null; } catch { data = null; }
  return { event, data };
}

export function drainSse(buffer: string): { events: SseEvent[]; rest: string } {
  const events: SseEvent[] = [];
  let rest = buffer;
  for (let i = rest.indexOf("\n\n"); i >= 0; i = rest.indexOf("\n\n")) {
    const block = rest.slice(0, i);
    rest = rest.slice(i + 2);
    if (block.trim()) events.push(parseSse(block));
  }
  return { events, rest };
}

export interface StreamHandlers {
  onUi?: (ui: UIAction, styleDna?: StyleDNA) => void;
  onText?: (delta: string) => void;
  onDone?: (response: ChatResponse, uiAlreadyApplied: boolean) => void;
}

export async function streamChat(
  body: ChatRequestBody,
  handlers: StreamHandlers,
  fetchImpl: typeof fetch = fetch,
  url = "/api/chat/stream",
  token?: string,
): Promise<ChatResponse> {
  let res: Response;
  try {
    res = await fetchImpl(url, {
      method: "POST",
      headers: authHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("I can't reach the stylist right now. Please try again in a moment.", 0);
  }
  if (!res.ok || !res.body) {
    let payload: unknown = null;
    try { payload = await res.json(); } catch { /* not json */ }
    throw new ApiError(detailText(payload), res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let uiApplied = false;
  let final: ChatResponse | null = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const out = drainSse(buffer);
    buffer = out.rest;
    for (const ev of out.events) {
      const data = ev.data as Record<string, unknown> | null;
      if (ev.event === "ui" && data) {
        uiApplied = true;
        handlers.onUi?.(data.ui_action as UIAction, data.style_dna as StyleDNA | undefined);
      } else if (ev.event === "text" && data) {
        handlers.onText?.(String(data.delta ?? ""));
      } else if (ev.event === "error") {
        throw new ApiError(String(data?.message ?? "Something went wrong."), 500);
      } else if (ev.event === "done" && data) {
        final = data as unknown as ChatResponse;
        handlers.onDone?.(final, uiApplied);
      }
    }
  }
  if (!final) throw new ApiError("The reply was cut off. Please try again.", 0);
  return final;
}

export async function streamLooksSearch(
  body: {
    session_id: string;
    user_id: string;
    occasion: string;
    vibe?: string;
    budget_inr?: number | null;
    exclude_look_ids?: string[];
  },
  handlers: { onLook?: (look: OutfitLook) => void },
  token?: string,
): Promise<{ looks: OutfitLook[]; style_dna?: StyleDNA }> {
  let res: Response;
  try {
    res = await fetch("/api/looks/search/stream", {
      method: "POST",
      headers: authHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("I can't reach the stylist right now. Please try again in a moment.", 0);
  }
  if (!res.ok || !res.body) {
    let payload: unknown = null;
    try { payload = await res.json(); } catch { /* not json */ }
    throw new ApiError(detailText(payload), res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let donePayload: { looks: OutfitLook[]; style_dna?: StyleDNA } | null = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const out = drainSse(buffer);
    buffer = out.rest;
    for (const ev of out.events) {
      const data = ev.data as Record<string, unknown> | null;
      if (ev.event === "look" && data?.look) {
        handlers.onLook?.(data.look as OutfitLook);
      } else if (ev.event === "error") {
        throw new ApiError(String(data?.message ?? "Could not load looks."), 500);
      } else if (ev.event === "done" && data) {
        donePayload = data as unknown as { looks: OutfitLook[]; style_dna?: StyleDNA };
      }
    }
  }
  if (!donePayload) throw new ApiError("Look stream ended unexpectedly.", 0);
  return donePayload;
}
