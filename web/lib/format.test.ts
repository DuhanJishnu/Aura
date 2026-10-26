import { describe, expect, it } from "vitest";
import { categoryOf, rupees, sizeLabel, sizeText, speakable, swatch } from "./format";

describe("sizes", () => {
  it("labels shoes by number, apparel by letter, accessories as one size", () => {
    expect(sizeLabel("shoes", 9)).toBe("9");
    expect(sizeLabel(undefined, 9.5)).toBe("9.5");
    expect(sizeLabel("apparel", 3)).toBe("M");
    expect(sizeLabel("apparel", 6)).toBe("XXL");
    expect(sizeLabel("accessories", 0)).toBe("one size");
  });
  it("builds the phrase used in cart lines and order lines", () => {
    expect(sizeText("shoes", 9)).toBe("size 9");
    expect(sizeText("apparel", 4)).toBe("size L");
    expect(sizeText("accessories", 0)).toBe("one size");
  });
  it("defaults to shoes", () => {
    expect(categoryOf({})).toBe("shoes");
    expect(categoryOf({ category: "apparel" })).toBe("apparel");
  });
});

describe("text", () => {
  it("formats rupees the Indian way", () => {
    expect(rupees(1999)).toBe("₹1,999");
    expect(rupees(123456)).toBe("₹1,23,456");
  });
  it("makes replies easier to listen to", () => {
    expect(speakable("Added it (₹4,199). Order ORD-1A2B3C4D is confirmed.")).toBe("Added it (4,199 rupees). Order your order is confirmed.");
    expect(speakable("Say “place order”")).toBe('Say "place order"');
  });
  it("picks readable text colors for swatches", () => {
    expect(swatch("white").color).toBe("#222222");
    expect(swatch("black").color).toBe("#f4f4f4");
    expect(swatch("purple").background).toBe("#888888");
  });
});
