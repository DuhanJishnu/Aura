import type { Category } from "./types";

export const rupees = (n: number): string => "₹" + n.toLocaleString("en-IN");

const APPAREL: Record<number, string> = { 1: "XS", 2: "S", 3: "M", 4: "L", 5: "XL", 6: "XXL" };

/** 9 -> "9" for shoes, 3 -> "M" for apparel, anything -> "one size" for accessories. */
export function sizeLabel(category: Category | null | undefined, size: number): string {
  if (category === "accessories") return "one size";
  if (category === "apparel") return APPAREL[Math.round(size)] ?? String(size);
  return String(size);
}

export function sizeText(category: Category | null | undefined, size: number): string {
  return category === "accessories" ? "one size" : `size ${sizeLabel(category, size)}`;
}

/** Make a reply easier on the ear: "₹4,999" -> "4,999 rupees", drop order-id noise. */
export function speakable(text: string): string {
  return text
    .replace(/₹\s?([\d,]+)/g, "$1 rupees")
    .replace(/\bORD-[0-9A-Z]{8}\b/g, "your order")
    .replace(/[“”]/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

export const COLOR_HEX: Record<string, string> = {
  black: "#26262a", white: "#ecebe8", navy: "#22345f", grey: "#8b9098",
  brown: "#6e4d36", red: "#b5352f", olive: "#6e7544", tan: "#c9a87c",
};
const LIGHT = new Set(["white", "grey", "tan"]);

/** Placeholder "photo": the product's color with its brand on it (the demo catalog has no images). */
export function swatch(color: string): { background: string; color: string } {
  return { background: COLOR_HEX[color] ?? "#888888", color: LIGHT.has(color) ? "#222222" : "#f4f4f4" };
}

export function categoryOf(p: { category?: Category | null }): Category {
  return p.category ?? "shoes";
}

export const FACT_TITLE: Record<string, string> = {
  undertone: "Undertone", skin_tone: "Skin tone", style: "Style", budget_min: "Budget from", budget_max: "Budget up to",
  liked_color: "Likes", rejected_color: "Avoids",
};
export const STATUS_TEXT: Record<string, string> = {
  stated: "you told me", confirmed: "you confirmed it", inferred: "a guess, tell me if it's wrong",
};
