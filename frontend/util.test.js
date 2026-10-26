const assert = require("assert");
const { sizeLabel, sizeText, parseSse, drainSse, speakable } = require("./util.js");

assert.strictEqual(sizeLabel("shoes", 9), "9");
assert.strictEqual(sizeLabel(undefined, 9.5), "9.5");
assert.strictEqual(sizeLabel("apparel", 3), "M");
assert.strictEqual(sizeLabel("apparel", 6), "XXL");
assert.strictEqual(sizeLabel("accessories", 0), "one size");
assert.strictEqual(sizeText("shoes", 9), "size 9");
assert.strictEqual(sizeText("apparel", 4), "size L");
assert.strictEqual(sizeText("accessories", 0), "one size");

const ev = parseSse('event: ui\ndata: {"ui_action": {"type": "show_products"}, "slots": {"use": "sports"}}');
assert.strictEqual(ev.event, "ui");
assert.strictEqual(ev.data.slots.use, "sports");
assert.strictEqual(parseSse("event: x\ndata: not json").data, null);

// events can arrive split anywhere across network chunks
const wire = 'event: status\ndata: {"state": "thinking"}\n\nevent: text\ndata: {"delta": "Hi "}\n\nevent: done\ndata: {"reply": "Hi there"}\n\n';
for (let cut = 1; cut < wire.length; cut += 7) {
  let { events, rest } = drainSse(wire.slice(0, cut));
  const second = drainSse(rest + wire.slice(cut));
  events = events.concat(second.events);
  assert.deepStrictEqual(events.map((e) => e.event), ["status", "text", "done"]);
  assert.strictEqual(second.rest, "");
}

assert.strictEqual(speakable("Added it (₹4,199). Order ORD-1A2B3C4D is confirmed."), "Added it (4,199 rupees). Order your order is confirmed.");
assert.strictEqual(speakable("Say “place order”"), 'Say "place order"');
console.log("frontend util tests passed");
