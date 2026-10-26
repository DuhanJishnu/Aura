import type { Cart, Estimate, Order, Product, ProfileView } from "./types";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

/** FastAPI returns {detail: "..."} or, for validation errors, {detail: [{msg: "..."}]}. */
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

async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(path, { cache: "no-store", ...init });
  } catch {
    throw new ApiError("I can't reach the shop right now. Please try again in a moment.", 0);
  }
}

export const get = async <T,>(path: string): Promise<T> => parse<T>(await send(path, {}));
export const post = async <T,>(path: string, body: unknown): Promise<T> =>
  parse<T>(await send(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }));

export const errorText = (e: unknown): string => (e instanceof Error ? e.message : "Something went wrong.");

/** Typed wrappers for the backend (reached through this app's /api proxy). */
export interface Ids { sessionId: string; userId: string }

export const api = {
  products: (query: URLSearchParams) => get<{ products: Product[] }>(`/api/products?${query}`),
  product: (id: number) => get<Product>(`/api/products/${id}`),
  cart: (i: Ids) => get<Cart>(`/api/cart?session_id=${encodeURIComponent(i.sessionId)}`),
  cartAdd: (i: Ids, productId: number, size: number) =>
    post<Cart>("/api/cart/add", { session_id: i.sessionId, user_id: i.userId, product_id: productId, size }),
  cartRemove: (i: Ids, productId: number, size: number) =>
    post<Cart>("/api/cart/remove", { session_id: i.sessionId, product_id: productId, size }),
  checkout: (i: Ids) => post<Order & { saved_size: number | null }>("/api/checkout", { session_id: i.sessionId, user_id: i.userId }),
  order: (id: string) => get<Order>(`/api/orders/${encodeURIComponent(id)}`),
  profile: (i: Ids) => get<ProfileView>(`/api/profile?session_id=${encodeURIComponent(i.sessionId)}&user_id=${encodeURIComponent(i.userId)}`),
  forget: (i: Ids) => post<{ message: string; profile: ProfileView }>("/api/profile/forget", { session_id: i.sessionId, user_id: i.userId }),
  consent: (i: Ids) => post<{ ok: boolean }>("/api/complexion/consent", { session_id: i.sessionId, user_id: i.userId }),
  analyze: (i: Ids, imageBase64: string, mimeType: string) =>
    post<{ estimate: Estimate }>("/api/complexion/analyze", { session_id: i.sessionId, user_id: i.userId, image_base64: imageBase64, mime_type: mimeType }),
  confirm: (i: Ids, skinTone: string, undertone: string) =>
    post<{ message: string; profile: ProfileView }>("/api/complexion/confirm", { session_id: i.sessionId, user_id: i.userId, skin_tone: skinTone, undertone }),
  cancel: (i: Ids) => post<{ ok: boolean }>("/api/complexion/cancel", { session_id: i.sessionId, user_id: i.userId }),
};
