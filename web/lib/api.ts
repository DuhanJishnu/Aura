import type {
  ComplexionEstimate,
  FashionItem,
  OutfitCheckResult,
  OutfitLook,
  StyleDNA,
  SwipeResponse,
} from "./types";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

export function detailText(body: unknown): string {
  const d = (body as { detail?: unknown } | null)?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (x as { msg?: string }).msg ?? "invalid input").join("; ");
  return "Request failed";
}

export async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown = null;
    try { body = await res.json(); } catch { /* not json */ }
    throw new ApiError(detailText(body), res.status);
  }
  return (await res.json()) as T;
}

export interface Ids {
  sessionId: string;
  userId: string;
  token?: string;
}

export function authHeaders(token?: string, base: Record<string, string> = {}): Record<string, string> {
  if (!token) return base;
  return { ...base, "X-Aura-Token": token };
}

function newIdempotencyKey(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  }
}

async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(path, { cache: "no-store", ...init });
  } catch {
    throw new ApiError("I can't reach the stylist right now. Please try again in a moment.", 0);
  }
}

export const get = async <T,>(path: string, token?: string): Promise<T> =>
  parse<T>(await send(path, { headers: authHeaders(token) }));

export const post = async <T,>(path: string, body: unknown, token?: string): Promise<T> =>
  parse<T>(
    await send(path, {
      method: "POST",
      headers: authHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    }),
  );

export const put = async <T,>(path: string, body: unknown, token?: string): Promise<T> =>
  parse<T>(
    await send(path, {
      method: "PUT",
      headers: authHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    }),
  );

export const del = async <T,>(path: string, token?: string): Promise<T> =>
  parse<T>(await send(path, { method: "DELETE", headers: authHeaders(token) }));

export const errorText = (e: unknown): string => (e instanceof Error ? e.message : "Something went wrong.");

export const api = {
  ready: () => get<{ adk: boolean; llm_key: boolean; live_model?: string }>("/api/ready"),
  profile: (i: Ids) => get<StyleDNA>(`/api/profile?user_id=${encodeURIComponent(i.userId)}`, i.token),
  syncProfile: (i: Ids, styleDna: StyleDNA) =>
    post<StyleDNA>("/api/profile/sync", { user_id: i.userId, style_dna: styleDna }, i.token),
  forget: (i: Ids) =>
    post<{ message: string; style_dna: StyleDNA }>(
      "/api/profile/forget",
      { session_id: i.sessionId, user_id: i.userId },
      i.token,
    ),
  swipe: (i: Ids, item: FashionItem, direction: "like" | "dislike" | "super_like", idempotencyKey = newIdempotencyKey()) =>
    post<SwipeResponse>(
      "/api/swipe",
      { session_id: i.sessionId, user_id: i.userId, item, direction, idempotency_key: idempotencyKey },
      i.token,
    ),
  swipeLook: (
    i: Ids,
    look: OutfitLook | null,
    action: "save" | "skip" | "buy_intent" | "undo",
    idempotencyKey = newIdempotencyKey(),
  ) =>
    post<SwipeResponse>(
      "/api/swipes",
      { session_id: i.sessionId, user_id: i.userId, look, action, idempotency_key: idempotencyKey },
      i.token,
    ),
  searchLooks: (
    i: Ids,
    occasion: string,
    opts?: { vibe?: string; budgetInr?: number; excludeLookIds?: string[] },
  ) =>
    post<{ looks: OutfitLook[]; style_dna: StyleDNA }>(
      "/api/looks/search",
      {
        session_id: i.sessionId,
        user_id: i.userId,
        occasion,
        vibe: opts?.vibe ?? "effortless modern",
        budget_inr: opts?.budgetInr ?? null,
        exclude_look_ids: opts?.excludeLookIds ?? [],
      },
      i.token,
    ),
  searchItems: (
    i: Ids,
    opts: { query: string; category?: string; max_budget_inr?: number | null; excludeItemIds?: string[] },
  ) =>
    post<{ items: FashionItem[]; style_dna: StyleDNA }>(
      "/api/items/search",
      {
        session_id: i.sessionId,
        user_id: i.userId,
        query: opts.query,
        category: opts.category ?? "apparel",
        max_budget_inr: opts.max_budget_inr ?? null,
        exclude_item_ids: opts.excludeItemIds ?? [],
      },
      i.token,
    ),
  wishlist: (i: Ids) => get<{ wishlist: OutfitLook[]; style_dna: StyleDNA }>(`/api/wishlist?user_id=${encodeURIComponent(i.userId)}`, i.token),
  removeWishlistLook: (i: Ids, lookId: string) =>
    del<StyleDNA>(`/api/wishlist/${encodeURIComponent(lookId)}?user_id=${encodeURIComponent(i.userId)}`, i.token),
  updatePreferences: (
    i: Ids,
    patch: Partial<{
      tutorial_seen: boolean;
      fit_preference: string;
      budget_max: number;
      sizes: Record<string, string>;
      liked_colors: string[];
    }>,
  ) => put<StyleDNA>("/api/preferences", { user_id: i.userId, ...patch }, i.token),
  removeClosetItem: (i: Ids, itemId: string) =>
    del<StyleDNA>(`/api/closet/${encodeURIComponent(itemId)}?user_id=${encodeURIComponent(i.userId)}`, i.token),
  saveOutfit: (i: Ids, outfit: OutfitLook) =>
    post<StyleDNA>(`/api/outfit/save?user_id=${encodeURIComponent(i.userId)}`, outfit, i.token),
  consent: (i: Ids) => post<{ ok: boolean }>("/api/complexion/consent", { session_id: i.sessionId, user_id: i.userId }, i.token),
  analyzeComplexion: (i: Ids, imageBase64: string, mimeType: string) =>
    post<{ estimate: ComplexionEstimate }>(
      "/api/complexion/analyze",
      { session_id: i.sessionId, user_id: i.userId, image_base64: imageBase64, mime_type: mimeType },
      i.token,
    ),
  confirmComplexion: (i: Ids, skinTone: string, undertone: string, colorSeason?: string) =>
    post<{ message: string; style_dna: StyleDNA }>(
      "/api/complexion/confirm",
      { session_id: i.sessionId, user_id: i.userId, skin_tone: skinTone, undertone, color_season: colorSeason },
      i.token,
    ),
  cancelPhoto: (i: Ids) => post<{ ok: boolean }>("/api/complexion/cancel", { session_id: i.sessionId, user_id: i.userId }, i.token),
  analyzeOutfitPhoto: (i: Ids, imageBase64: string, mimeType: string, note = "") =>
    post<{ result: OutfitCheckResult }>(
      "/api/outfit-check/analyze",
      { session_id: i.sessionId, user_id: i.userId, image_base64: imageBase64, mime_type: mimeType, note },
      i.token,
    ),
};
