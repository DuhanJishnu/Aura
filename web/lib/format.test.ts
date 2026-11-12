import { describe, expect, it } from "vitest";
import { contrastText, rupees, speakable } from "./format";

describe("format", () => {
  it("formats rupees with Indian grouping", () => {
    expect(rupees(12999)).toBe("₹12,999");
  });

  it("picks readable contrast text for light and dark swatches", () => {
    expect(contrastText("#EDE6D6")).toBe("#1c1917");
    expect(contrastText("#20314D")).toBe("#fafaf9");
  });

  it("cleans markdown and rupee symbols for speech synthesis", () => {
    expect(speakable("Try **this** at ₹2,490!")).toBe("Try this at 2,490 rupees!");
  });
});
