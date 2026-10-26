const COLORS = { black: "#26262a", white: "#ecebe8", navy: "#22345f", grey: "#8b9098", brown: "#6e4d36",
                 red: "#b5352f", olive: "#6e7544", tan: "#c9a87c" };
const LIGHT = new Set(["white", "grey", "tan"]);

const { sizeLabel, sizeText, drainSse, speakable } = window.ShopperUtil;
const $ = (id) => document.getElementById(id);
const log = $("log"), panel = $("panel"), input = $("input"), sendBtn = $("send");

function loadId(key, store) {
  try {
    let id = store.getItem(key);
    if (!id) { id = crypto.randomUUID(); store.setItem(key, id); }
    return id;
  } catch { return crypto.randomUUID(); }
}

const state = {
  sessionId: loadId("shopper_sid", sessionStorage),
  userId: loadId("shopper_uid", localStorage),   // stable across tabs so a saved size can be found again
  cart: { items: [], total: 0 }, focusedId: null, slots: {}, lastView: null,
};

const rupees = (n) => "₹" + Number(n).toLocaleString("en-IN");

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function addMsg(text, cls) {
  const m = el("div", "msg " + cls, text);
  log.appendChild(m);
  log.scrollTop = log.scrollHeight;
  return m;
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch {}
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}
const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function thumb(p) {
  const t = el("div", "thumb", p.brand.toUpperCase());
  t.style.background = COLORS[p.color] || "#888";
  t.style.color = LIGHT.has(p.color) ? "#222" : "#f4f4f4";
  return t;
}

function renderEmpty(text) { panel.replaceChildren(el("div", "empty", text)); }

function renderGrid(products) {
  state.focusedId = null;
  if (!products.length) return renderEmpty("Nothing matched. Try loosening a filter.");
  const grid = el("div", "grid");
  for (const p of products) {
    const card = el("button", "card");
    card.type = "button";
    card.appendChild(thumb(p));
    const body = el("div", "body");
    body.append(el("div", "name", p.name), el("div", "meta", `${p.color} · ${p.use_type} · ★ ${p.rating}`),
                el("div", "price", rupees(p.price)));
    card.appendChild(body);
    card.addEventListener("click", () => focusProduct(p.id));
    grid.appendChild(card);
  }
  panel.replaceChildren(grid);
}

function renderDetail(p) {
  state.focusedId = p.id;
  const cat = p.category || "shoes";
  let chosen = null;
  if (cat === "accessories") chosen = p.sizes_in_stock.length ? p.sizes_in_stock[0] : null;   // one size: nothing to pick
  else if ((state.slots.category || "shoes") === cat && p.sizes_in_stock.includes(state.slots.size)) chosen = state.slots.size;
  const wrap = el("div", "detail");
  const back = el("button", "ghost back", "← Back to results");
  back.addEventListener("click", () => (state.lastView ? showProducts(state.lastView) : renderEmpty("Products will appear here as we chat.")));
  wrap.append(back, thumb(p), el("h2", null, p.name),
              el("div", "meta", `${p.brand} · ${p.color} · ${p.use_type} · ★ ${p.rating}`),
              el("div", "price", rupees(p.price)), el("p", null, p.description));
  const sizes = el("div", "sizes");
  sizes.appendChild(el("div", "meta", !p.sizes_in_stock.length ? "Out of stock" : cat === "accessories" ? "One size" : "Pick a size:"));
  const buttons = [];
  for (const s of (cat === "accessories" ? [] : p.sizes_in_stock)) {
    const b = el("button", s === chosen ? "sel" : "", sizeLabel(cat, s));
    b.type = "button";
    b.addEventListener("click", () => { chosen = s; buttons.forEach((x) => x.classList.toggle("sel", x === b)); });
    buttons.push(b);
    sizes.appendChild(b);
  }
  const row = el("div", "row");
  const ask = el("button", "ghost", "Ask about this");
  ask.addEventListener("click", () => send(`What do you think of the ${p.name}?`));
  const add = el("button", null, "Add to cart");
  add.disabled = !p.sizes_in_stock.length;
  add.addEventListener("click", async () => {
    if (chosen === null) return addMsg("Pick a size first, then add it to your cart.", "err");
    try { state.cart = await post("/cart/add", { session_id: state.sessionId, user_id: state.userId, product_id: p.id, size: chosen }); renderCart(); $("drawer").hidden = false; }
    catch (e) { addMsg(e.message, "err"); }
  });
  row.append(ask, add);
  wrap.append(sizes, row);
  panel.replaceChildren(wrap);
}

/* view = { ids } from the assistant, or { filters } */
async function showProducts(view) {
  state.lastView = view;
  renderEmpty("Loading…");
  try {
    const q = new URLSearchParams();
    if (view.ids && view.ids.length) q.set("ids", view.ids.join(","));
    else for (const [k, v] of Object.entries(view.filters || {})) if (v !== null && v !== undefined && v !== "") q.set(k, v);
    renderGrid((await api("/products?" + q)).products);
  } catch (e) { renderEmpty("Couldn't load products: " + e.message); }
}

async function focusProduct(id) {
  try { renderDetail(await api("/products/" + id)); }
  catch (e) { renderEmpty("Couldn't load that product: " + e.message); }
}

async function showCompare(ids) {
  try {
    const ps = (await api("/products?ids=" + ids.join(","))).products;
    state.focusedId = null;
    const wrap = el("div", "compare");
    const back = el("button", "ghost back", "← Back to results");
    back.addEventListener("click", () => (state.lastView ? showProducts(state.lastView) : renderEmpty("Products will appear here as we chat.")));
    const table = el("table");
    const head = el("tr");
    head.appendChild(el("th"));
    for (const p of ps) {
      const th = el("th");
      const b = el("button", "ghost", p.name);
      b.addEventListener("click", () => focusProduct(p.id));
      th.appendChild(b);
      head.appendChild(th);
    }
    table.appendChild(head);
    const rows = [["Price", (p) => rupees(p.price)], ["Rating", (p) => "★ " + p.rating], ["Color", (p) => p.color],
                  ["Use", (p) => p.use_type], ["Sizes in stock", (p) => p.sizes_in_stock.map((s) => sizeLabel(p.category, s)).join(", ") || "none"]];
    for (const [label, fn] of rows) {
      const tr = el("tr");
      tr.appendChild(el("td", "lbl", label));
      for (const p of ps) tr.appendChild(el("td", null, fn(p)));
      table.appendChild(tr);
    }
    wrap.append(back, table);
    panel.replaceChildren(wrap);
  } catch (e) { renderEmpty("Couldn't load the comparison: " + e.message); }
}

/* ---------- profile and complexion ---------- */
const STATUS = { stated: "you told me", confirmed: "you confirmed it", inferred: "a guess, tell me if it's wrong" };
const TITLE = { undertone: "Undertone", skin_tone: "Skin tone", style: "Style", budget_min: "Budget from", budget_max: "Budget up to",
                liked_color: "Likes", rejected_color: "Avoids" };

async function refreshProfile() {
  const body = $("profileBody");
  body.replaceChildren();
  try {
    const p = await api(`/profile?session_id=${encodeURIComponent(state.sessionId)}&user_id=${encodeURIComponent(state.userId)}`);
    const rows = [];
    if (p.size !== null && p.size !== undefined) rows.push(["Size", String(p.size), "saved after a purchase for yourself"]);
    for (const f of p.facts) rows.push([TITLE[f.key] || f.key, f.value, STATUS[f.status] || f.status]);
    if (!rows.length) body.appendChild(el("div", "meta", "Nothing saved yet. I only save what you tell me or confirm, and I never store photos."));
    for (const [k, v, s] of rows) {
      const line = el("div", "cart-row");
      const left = el("div");
      left.append(el("div", null, `${k}: ${v}`), el("div", "meta", s));
      line.appendChild(left);
      body.appendChild(line);
    }
  } catch (e) { body.appendChild(el("div", "meta", "Couldn't load your profile: " + e.message)); }
}

function renderConsent() {
  const wrap = el("div", "order");
  wrap.append(el("h2", null, "Color advice from a photo"),
    el("p", null, "If you agree, you can upload one photo. I'll estimate your skin tone and undertone, show you the result to confirm or correct, and delete the photo right after it has been analysed. Only the result you confirm is saved, and you can clear it any time. This is a general styling guide, not a rule."),
    el("p", "note", "Prefer not to upload? Just tell me your undertone in the chat instead."));
  const row = el("div", "row");
  const yes = el("button", null, "I agree, continue");
  yes.addEventListener("click", async () => {
    try { await post("/complexion/consent", { session_id: state.sessionId, user_id: state.userId }); renderUpload(); }
    catch (e) { addMsg(e.message, "err"); }
  });
  const no = el("button", "ghost", "No thanks");
  no.addEventListener("click", () => renderEmpty("No problem. Nothing was uploaded."));
  row.append(yes, no);
  wrap.appendChild(row);
  panel.replaceChildren(wrap);
}

function renderUpload() {
  const wrap = el("div", "order");
  const file = el("input"); file.type = "file"; file.accept = "image/jpeg,image/png,image/webp";
  const go = el("button", null, "Analyse photo");
  const status = el("div", "note");
  wrap.append(el("h2", null, "Upload a photo"), el("p", null, "A clear, well-lit photo with your face or skin visible works best."), file, el("div", "row"), status);
  wrap.lastChild.previousSibling.appendChild(go);
  go.addEventListener("click", async () => {
    const f = file.files[0];
    if (!f) { status.textContent = "Choose a photo first."; return; }
    go.disabled = true; status.textContent = "Analysing…";
    try {
      const b64 = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result).split(",")[1]);
        r.onerror = () => reject(new Error("Couldn't read that file."));
        r.readAsDataURL(f);
      });
      const out = await post("/complexion/analyze", { session_id: state.sessionId, user_id: state.userId, image_base64: b64, mime_type: f.type });
      file.value = "";
      renderEstimate(out.estimate);
    } catch (e) { status.textContent = e.message; go.disabled = false; }
  });
  panel.replaceChildren(wrap);
}

function select(options, value) {
  const s = el("select");
  for (const o of options) { const op = el("option", null, o); op.value = o; op.selected = o === value; s.appendChild(op); }
  return s;
}

function renderEstimate(est) {
  const wrap = el("div", "order");
  const tone = select(["fair", "light", "medium", "tan", "deep"], est.skin_tone);
  const under = select(["warm", "cool", "neutral"], est.undertone);
  wrap.append(el("h2", null, "Here's my estimate"),
    el("p", null, est.confidence === "low" ? "I'm not confident about this one (lighting or the photo can mislead). Please set it yourself." : "Please check it and change anything that's off. Nothing is saved until you confirm."),
    el("label", null, "Skin tone "), tone, el("br"), el("label", null, "Undertone "), under);
  if (est.note) wrap.appendChild(el("div", "note", est.note));
  const row = el("div", "row");
  const ok = el("button", null, "Confirm and save");
  ok.addEventListener("click", async () => {
    try {
      const out = await post("/complexion/confirm", { session_id: state.sessionId, user_id: state.userId, skin_tone: tone.value, undertone: under.value });
      addMsg(out.message, "bot");
      renderEmpty("Saved. Ask me for shoes and I'll weigh your colors when ranking them.");
      refreshProfile();
    } catch (e) { addMsg(e.message, "err"); }
  });
  const cancel = el("button", "ghost", "Discard");
  cancel.addEventListener("click", async () => {
    await post("/complexion/cancel", { session_id: state.sessionId, user_id: state.userId }).catch(() => {});
    renderEmpty("Discarded. Nothing was saved.");
  });
  row.append(ok, cancel);
  wrap.style.marginTop = "12px";
  wrap.appendChild(row);
  panel.replaceChildren(wrap);
}

async function forgetProfile() {
  if (!confirm("Delete your saved size, preferences, skin tone and undertone?")) return;
  try {
    const out = await post("/profile/forget", { session_id: state.sessionId, user_id: state.userId });
    addMsg(out.message, "bot");
    refreshProfile();
  } catch (e) { addMsg(e.message, "err"); }
}

async function showOrder(orderId) {
  try {
    const o = await api("/orders/" + orderId);
    const wrap = el("div", "order");
    wrap.append(el("h2", null, "Order confirmed"), el("div", "meta", `Order ${o.order_id}`));
    for (const i of o.items) {
      const line = el("div", "line");
      line.append(el("span", null, `${i.name} · ${sizeText(i.category, i.size)}`), el("span", null, rupees(i.price)));
      wrap.appendChild(line);
    }
    const total = el("div", "line");
    total.append(el("strong", null, "Total"), el("strong", null, rupees(o.total)));
    wrap.append(total, el("div", "note", "This was a mock checkout. Nothing was charged."));
    const more = el("button", "ghost", "Keep shopping");
    more.addEventListener("click", () => (state.lastView ? showProducts(state.lastView) : renderEmpty("Tell me what else you're looking for.")));
    wrap.appendChild(more);
    panel.replaceChildren(wrap);
  } catch (e) { renderEmpty("Couldn't load the order: " + e.message); }
}

/* Cart lives on the server so chat and buttons stay in sync. */
async function refreshCart() {
  try { state.cart = await api("/cart?session_id=" + encodeURIComponent(state.sessionId)); } catch { /* keep last */ }
  renderCart();
}

function renderCart() {
  const { items, total } = state.cart;
  $("cartCount").textContent = items.length;
  const box = $("cartItems");
  box.replaceChildren();
  if (!items.length) box.appendChild(el("div", "meta", "Your cart is empty."));
  for (const c of items) {
    const row = el("div", "cart-row");
    const left = el("div");
    left.append(el("div", null, c.name), el("div", "meta", `${sizeText(c.category, c.size)} · ${rupees(c.price)}`));
    const rm = el("button", "ghost", "Remove");
    rm.addEventListener("click", async () => {
      try { state.cart = await post("/cart/remove", { session_id: state.sessionId, product_id: c.shoe_id, size: c.size }); renderCart(); }
      catch (e) { addMsg(e.message, "err"); }
    });
    row.append(left, rm);
    box.appendChild(row);
  }
  $("cartTotal").textContent = rupees(total);
  $("checkoutBtn").disabled = !items.length;
}

async function placeOrder() {
  $("checkoutBtn").disabled = true;
  try {
    const o = await post("/checkout", { session_id: state.sessionId, user_id: state.userId });
    $("drawer").hidden = true;
    addMsg(`Order ${o.order_id} confirmed. This was a mock checkout, so nothing was charged.`, "bot");
    await refreshCart();
    await showOrder(o.order_id);
  } catch (e) { addMsg(e.message, "err"); renderCart(); }
}

async function applyAction(a) {
  if (!a) return;
  if (a.type === "show_products") await showProducts({ ids: a.product_ids, filters: a.filters });
  else if (a.type === "focus_product" && a.product_id) await focusProduct(a.product_id);
  else if (a.type === "compare" && a.product_ids.length) await showCompare(a.product_ids);
  else if (a.type === "request_photo") renderUpload();
  else if (a.type === "checkout") {
    if (a.order_id) await showOrder(a.order_id); else $("drawer").hidden = false;
  } else if (a.type === "add_to_cart") $("drawer").hidden = false;
}

/* ---------- speech: output (read replies aloud) and input (microphone) ---------- */
const synth = window.speechSynthesis;
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const voiceStatus = $("voiceStatus");
const setStatus = (s) => { voiceStatus.textContent = s || ""; };

function storedFlag(key) { try { return localStorage.getItem(key) === "1"; } catch { return false; } }
function storeFlag(key, on) { try { localStorage.setItem(key, on ? "1" : "0"); } catch { /* private mode */ } }

state.speak = storedFlag("shopper_speak");
function renderSpeakBtn() {
  const b = $("speakBtn");
  b.textContent = "Speak replies: " + (state.speak ? "on" : "off");
  b.setAttribute("aria-pressed", String(state.speak));
}
function cancelSpeech() { if (synth) synth.cancel(); }
function speak(text) {
  if (!synth || !state.speak || !text) return;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(speakable(text));
  u.lang = "en-IN";
  const voices = synth.getVoices();
  u.voice = voices.find((v) => v.lang === "en-IN") || voices.find((v) => v.lang.startsWith("en")) || null;
  synth.speak(u);
}
if (synth) {
  $("speakBtn").hidden = false;
  renderSpeakBtn();
  $("speakBtn").addEventListener("click", () => {
    state.speak = !state.speak; storeFlag("shopper_speak", state.speak); renderSpeakBtn();
    if (!state.speak) cancelSpeech();
  });
}

if (SR) {
  const mic = $("mic");
  mic.hidden = false;
  const rec = new SR();
  rec.lang = "en-IN"; rec.interimResults = true; rec.continuous = false;
  let listening = false, heard = "";
  rec.onstart = () => { listening = true; heard = ""; mic.classList.add("on"); mic.setAttribute("aria-pressed", "true"); cancelSpeech(); setStatus("Listening… speak now."); };
  rec.onresult = (e) => {
    const text = Array.from(e.results).map((r) => r[0].transcript).join(" ").trim();
    input.value = text;
    if (e.results[e.results.length - 1].isFinal) heard = text;
  };
  rec.onerror = (e) => {
    const why = { "not-allowed": "Microphone permission is blocked for this site.", "service-not-allowed": "Speech recognition is not allowed here.",
                  "no-speech": "I didn't hear anything. Tap Mic and try again.", "network": "Speech recognition needs an internet connection.",
                  "audio-capture": "No microphone found." }[e.error];
    setStatus(why || "Voice input stopped (" + e.error + ").");
  };
  rec.onend = () => {
    listening = false; mic.classList.remove("on"); mic.setAttribute("aria-pressed", "false");
    if (heard) { input.value = ""; setStatus(""); send(heard); heard = ""; }
  };
  mic.addEventListener("click", () => {
    try { if (listening) rec.stop(); else rec.start(); } catch { /* already started */ }
  });
}

/* ---------- sending a message ---------- */
function detailText(body) {
  const d = body && body.detail;
  return typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join("; ") : "Request failed";
}

/* Streamed turn: the product panel updates as soon as the server knows the products, the words follow. */
async function sendStreamed(text, typing) {
  const res = await fetch("/chat/stream", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.sessionId, user_id: state.userId, message: text, focus_product_id: state.focusedId }),
  });
  if (!res.ok) { let b = null; try { b = await res.json(); } catch { /* not json */ } throw new Error(detailText(b)); }
  const reader = res.body.getReader(), decoder = new TextDecoder();
  let buffer = "", bubble = null, uiApplied = false, reply = "";
  const open = () => { if (!bubble) { typing.remove(); bubble = addMsg("", "bot"); } return bubble; };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const out = drainSse(buffer);
    buffer = out.rest;
    for (const ev of out.events) {
      if (ev.event === "ui" && ev.data) {
        state.slots = ev.data.slots || state.slots;
        uiApplied = true;
        applyAction(ev.data.ui_action);           // not awaited: the words keep arriving meanwhile
      } else if (ev.event === "text" && ev.data) {
        open().textContent += ev.data.delta;
        log.scrollTop = log.scrollHeight;
      } else if (ev.event === "error") {
        typing.remove();
        throw new Error(ev.data ? ev.data.message : "Something went wrong.");
      } else if (ev.event === "done" && ev.data) {
        reply = ev.data.reply;
        open().textContent = reply;
        state.slots = ev.data.slots || state.slots;
        await refreshCart();
        if (!uiApplied) await applyAction(ev.data.ui_action);
        refreshProfile();
      }
    }
  }
  if (!bubble) typing.remove();
  return reply;
}

async function sendPlain(text, typing) {
  const data = await post("/chat", { session_id: state.sessionId, user_id: state.userId, message: text, focus_product_id: state.focusedId });
  typing.remove();
  state.slots = data.slots || {};
  addMsg(data.reply, "bot");
  await refreshCart();
  await applyAction(data.ui_action);
  refreshProfile();
  return data.reply;
}

let busy = false;
async function send(text) {
  if (busy) return;
  busy = true;
  cancelSpeech();
  addMsg(text, "user");
  const typing = addMsg("Thinking…", "bot typing");
  sendBtn.disabled = true;
  try {
    const reply = window.ReadableStream && window.TextDecoder ? await sendStreamed(text, typing) : await sendPlain(text, typing);
    speak(reply);
  } catch (e) {
    typing.remove();
    addMsg("Something went wrong: " + e.message, "err");
  } finally {
    busy = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => send(c.dataset.q)));

$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  send(text);
});
$("cartBtn").addEventListener("click", () => { $("drawer").hidden = !$("drawer").hidden; });
$("closeCart").addEventListener("click", () => { $("drawer").hidden = true; });
$("checkoutBtn").addEventListener("click", placeOrder);
$("profileBtn").addEventListener("click", () => { $("profileDrawer").hidden = !$("profileDrawer").hidden; if (!$("profileDrawer").hidden) refreshProfile(); });
$("closeProfile").addEventListener("click", () => { $("profileDrawer").hidden = true; });
$("photoBtn").addEventListener("click", () => { $("profileDrawer").hidden = true; renderConsent(); });
$("forgetBtn").addEventListener("click", forgetProfile);

renderEmpty("Products will appear here as we chat.");
renderCart();
refreshCart();
addMsg("Hi! I'm your shoe-shopping buddy. Tell me what you're after, like “sports shoes, size 9”.", "bot");
