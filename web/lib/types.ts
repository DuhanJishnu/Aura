export interface FashionItem {
  id: string;
  name: string;
  brand: string;
  category: string;
  price_text: string;
  price_estimate_inr?: number | null;
  color: string;
  color_hex: string;
  aesthetic_tags: string[];
  fit_note: string;
  why_it_suits_you: string;
  styling_tip: string;
  url: string;
  url_verified: boolean;
  source_domain: string;
  image_url?: string;
  image_source?: "retailer" | "ai_generated" | "none";
  match_score: number;
  match_reasons: string[];
}

export interface OutfitPiece {
  slot: string;
  name: string;
  brand?: string;
  store?: string;
  color: string;
  color_hex: string;
  fit_guidance: string;
  from_closet: boolean;
  item_id?: string | null;
  search_query: string;
  url: string;
  url_verified?: boolean;
  price_text: string;
  price_estimate_inr?: number | null;
  image_url?: string;
  image_source?: "retailer" | "ai_generated" | "none";
}

export interface OutfitLook {
  id: string;
  title: string;
  occasion: string;
  vibe: string;
  tags?: string[];
  color_story: string;
  proportion_tip: string;
  styling_hacks: string[];
  pieces: OutfitPiece[];
  total_estimate_text: string;
  total_estimate_inr?: number | null;
  saved_at?: string;
  image_url?: string;
  image_source?: "retailer" | "ai_generated" | "none";
  look_fingerprint?: string;
}

export type FactSource = "stated" | "confirmed" | "swiped" | "inferred";

export interface FactEntry {
  key: string;
  value: string;
  source: FactSource;
}

export interface SwipeRecord {
  item_id: string;
  item_name: string;
  direction: "like" | "dislike" | "super_like";
  tags: string[];
  color: string;
  brand: string;
  price_estimate_inr?: number | null;
  timestamp: string;
}

export interface StyleDNA {
  user_id: string;
  sizes: Record<string, string>;
  aesthetics: Record<string, number>;
  liked_colors: string[];
  disliked_colors: string[];
  liked_brands: string[];
  disliked_brands: string[];
  budget_min?: number | null;
  budget_max?: number | null;
  skin_tone?: string | null;
  undertone?: string | null;
  color_season?: string | null;
  fit_preference?: string | null;
  saved_closet: FashionItem[];
  saved_outfits: OutfitLook[];
  disliked_item_keys: string[];
  seen_look_ids?: string[];
  seen_item_ids?: string[];
  tutorial_seen?: boolean;
  swipe_history: SwipeRecord[];
  facts: FactEntry[];
  declined: boolean;
}

export type UIActionType =
  | "none"
  | "swipe_deck"
  | "grid"
  | "focus_item"
  | "outfit_board"
  | "compare"
  | "closet"
  | "request_photo"
  | "confirm_forget";

export interface SearchMeta {
  query: string;
  category: string;
  max_budget_inr?: number | null;
}

export interface UIAction {
  type: UIActionType;
  items: FashionItem[];
  outfit?: OutfitLook | null;
  looks?: OutfitLook[];
  focus_item?: FashionItem | null;
  photo_mode?: "complexion" | "outfit_check" | null;
  search_meta?: SearchMeta | null;
}

export interface ChatRequestBody {
  session_id: string;
  user_id: string;
  message: string;
  focus_item_id?: string | null;
  style_dna?: StyleDNA | null;
}

export interface ChatResponse {
  reply: string;
  ui_action: UIAction;
  style_dna: StyleDNA;
  tools_used: string[];
}

export interface SwipeResponse {
  style_dna: StyleDNA;
  reaction: string;
  stats: { liked: number; passed: number; closet: number; wishlist?: number };
}

export interface ComplexionEstimate {
  skin_tone: string;
  undertone: string;
  color_season: string;
  confidence: "low" | "medium" | "high";
  recommended_colors: string[];
  note: string;
}

export interface OutfitCheckResult {
  overall_vibe: string;
  what_works: string[];
  elevation_tips: string[];
  suggested_additions: string[];
  rating_out_of_10: number;
  honest_bestie_summary: string;
}

export interface Message {
  id: number;
  role: "user" | "bot" | "err";
  text: string;
}

export type PanelView =
  | { kind: "empty"; text: string }
  | { kind: "loading" }
  | { kind: "error"; text: string }
  | { kind: "looks_deck"; looks: OutfitLook[] }
  | { kind: "swipe_deck"; items: FashionItem[] }
  | { kind: "grid"; items: FashionItem[] }
  | { kind: "detail"; item: FashionItem }
  | { kind: "outfit"; outfit: OutfitLook }
  | { kind: "compare"; items: FashionItem[] }
  | { kind: "wishlist" }
  | { kind: "closet" }
  | { kind: "consent"; mode: "complexion" | "outfit_check" }
  | { kind: "upload"; mode: "complexion" | "outfit_check" }
  | { kind: "estimate"; estimate: ComplexionEstimate }
  | { kind: "outfit_check"; result: OutfitCheckResult };
