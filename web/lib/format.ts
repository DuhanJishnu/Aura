export const rupees = (n: number): string => "₹" + n.toLocaleString("en-IN");

/** Make a reply easier on the ear for Web Speech synthesis fallback. */
export function speakable(text: string): string {
  return text
    .replace(/₹\s?([\d,]+)/g, "$1 rupees")
    .replace(/[“”]/g, '"')
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

export function contrastText(hex: string): string {
  const clean = hex.replace("#", "");
  if (!/^[0-9a-fA-F]{6}$/.test(clean)) return "#ffffff";
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.65 ? "#1c1917" : "#fafaf9";
}

export const FACT_TITLE: Record<string, string> = {
  shoes_size: "Shoe size",
  tops_size: "Top size",
  bottoms_size: "Bottom size",
  undertone: "Undertone",
  skin_tone: "Skin tone",
  color_season: "Color season",
  aesthetic: "Aesthetic",
  fit_preference: "Preferred fit",
  budget_max: "Budget comfort",
  liked_color: "Likes color",
  disliked_color: "Avoids color",
};

export const STATUS_TEXT: Record<string, string> = {
  stated: "you told me",
  confirmed: "you confirmed it",
  swiped: "learned from your swipes",
  inferred: "inferred — correct me anytime",
};
