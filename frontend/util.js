/* Pure helpers (no DOM), shared by the page and by the Node test in util.test.js. */
(function (root) {
  const APPAREL = { 1: "XS", 2: "S", 3: "M", 4: "L", 5: "XL", 6: "XXL" };

  function sizeLabel(category, s) {
    if (category === "accessories") return "one size";
    if (category === "apparel") return APPAREL[Math.round(s)] || String(s);
    return String(s);
  }
  function sizeText(category, s) {
    return category === "accessories" ? "one size" : "size " + sizeLabel(category, s);
  }

  /* One server-sent event ("event: x\ndata: {...}") -> { event, data }. */
  function parseSse(block) {
    const ev = { event: "message", data: null };
    let raw = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) ev.event = line.slice(6).trim();
      else if (line.startsWith("data:")) raw += line.slice(5).trim();
    }
    try { ev.data = raw ? JSON.parse(raw) : null; } catch { ev.data = null; }
    return ev;
  }
  /* Split a growing text buffer into complete events plus the unfinished rest. */
  function drainSse(buffer) {
    const events = [];
    let rest = buffer, i;
    while ((i = rest.indexOf("\n\n")) >= 0) {
      const block = rest.slice(0, i);
      rest = rest.slice(i + 2);
      if (block.trim()) events.push(parseSse(block));
    }
    return { events, rest };
  }

  /* Make a reply easier on the ear: "₹4,999" -> "4,999 rupees", drop order-id noise. */
  function speakable(text) {
    return text
      .replace(/₹\s?([\d,]+)/g, "$1 rupees")
      .replace(/\bORD-[0-9A-Z]{8}\b/g, "your order")
      .replace(/[“”]/g, '"')
      .replace(/\s+/g, " ")
      .trim();
  }

  const api = { sizeLabel, sizeText, parseSse, drainSse, speakable };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ShopperUtil = api;
})(typeof window !== "undefined" ? window : globalThis);
