export type Category = "shoes" | "apparel" | "accessories";

export interface Product {
  id: number;
  name: string;
  brand: string;
  price: number;
  use_type: string;
  color: string;
  rating: number;
  image?: string | null;
  description: string;
  category?: Category;
  sizes_in_stock?: number[];
}

export interface Slots {
  category?: Category | null;
  for_whom?: "self" | "other" | null;
  size?: number | null;
  use?: string | null;
  budget?: number | null;
  color?: string | null;
}

export type UIActionType = "show_products" | "focus_product" | "compare" | "add_to_cart" | "checkout" | "request_photo" | "none";

export interface UIAction {
  type: UIActionType;
  filters: Record<string, unknown>;
  product_id: number | null;
  product_ids: number[];
  order_id: string | null;
}

export interface ChatResponse {
  reply: string;
  slots: Slots;
  ui_action: UIAction;
  policy?: { action: string; rule: string; fast?: boolean } | null;
}

export interface ChatRequestBody {
  session_id: string;
  user_id: string;
  message: string;
  focus_product_id: number | null;
}

export interface CartLine {
  shoe_id: number;
  name: string;
  price: number;
  size: number;
  category?: Category;
}
export interface Cart {
  items: CartLine[];
  total: number;
}

export interface OrderLine {
  shoe_id: number;
  name: string;
  size: number;
  price: number;
  category?: Category;
}
export interface Order {
  order_id: string;
  total: number;
  created_at: string;
  items: OrderLine[];
}

export type FactStatus = "stated" | "confirmed" | "inferred";
export interface ProfileFact {
  key: string;
  value: string;
  status: FactStatus;
}
export interface Estimate {
  skin_tone: string;
  undertone: string;
  confidence: "low" | "medium" | "high";
  note: string;
}
export interface ProfileView {
  size: number | null;
  facts: ProfileFact[];
  pending_estimate: Estimate | null;
}

export interface Message {
  id: number;
  role: "user" | "bot" | "err";
  text: string;
}

/** What the right-hand panel is showing. */
export type PanelView =
  | { kind: "empty"; text: string }
  | { kind: "loading" }
  | { kind: "error"; text: string }
  | { kind: "grid"; products: Product[] }
  | { kind: "detail"; product: Product }
  | { kind: "compare"; products: Product[] }
  | { kind: "order"; order: Order }
  | { kind: "consent" }
  | { kind: "upload" }
  | { kind: "estimate"; estimate: Estimate };

/** How to reload the list the shopper was looking at ("Back to results"). */
export interface ListView {
  ids?: number[];
  filters?: Record<string, unknown>;
}
