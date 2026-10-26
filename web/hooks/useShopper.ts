"use client";

import { useCallback, useRef, useState } from "react";
import { api, errorText, post } from "@/lib/api";
import { streamChat } from "@/lib/stream";
import type { Cart, ChatResponse, ListView, Message, PanelView, Product, ProfileView, Slots, UIAction } from "@/lib/types";
import { useIds } from "./useIds";

const WELCOME = "Hi! I'm your shopping buddy for shoes, clothes and accessories. Tell me what you're after, like “sports shoes, size 9”.";
const EMPTY: PanelView = { kind: "empty", text: "Products will appear here as we chat." };

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("I couldn't read that file."));
    reader.readAsDataURL(file);
  });
}

interface Options {
  onReply?: (text: string) => void;   // e.g. read it aloud
  onSend?: () => void;                // e.g. stop reading
}

/** All shopping state and actions: chat (streamed), the product panel, cart, profile and the photo flow. */
export function useShopper({ onReply, onSend }: Options = {}) {
  const ids = useIds();
  const [messages, setMessages] = useState<Message[]>([{ id: 0, role: "bot", text: WELCOME }]);
  const [thinking, setThinking] = useState(false);
  const [panel, setPanel] = useState<PanelView>(EMPTY);
  const [slots, setSlots] = useState<Slots>({});
  const [cart, setCart] = useState<Cart>({ items: [], total: 0 });
  const [profile, setProfile] = useState<ProfileView | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const nextId = useRef(1);
  const busy = useRef(false);
  const focusedId = useRef<number | null>(null);
  const lastView = useRef<ListView | null>(null);

  const addMessage = useCallback((role: Message["role"], text: string): number => {
    const id = nextId.current++;
    setMessages((m) => [...m, { id, role, text }]);
    return id;
  }, []);
  const patchMessage = useCallback((id: number, text: string) => {
    setMessages((m) => m.map((x) => (x.id === id ? { ...x, text } : x)));
  }, []);

  // ----- product panel -----
  const showProducts = useCallback(async (view: ListView) => {
    lastView.current = view;
    focusedId.current = null;
    setPanel({ kind: "loading" });
    try {
      const q = new URLSearchParams();
      if (view.ids?.length) q.set("ids", view.ids.join(","));
      else for (const [k, v] of Object.entries(view.filters ?? {})) if (v !== null && v !== undefined && v !== "") q.set(k, String(v));
      const { products } = await api.products(q);
      setPanel(products.length ? { kind: "grid", products } : { kind: "empty", text: "Nothing matched. Try loosening a filter." });
    } catch (e) {
      setPanel({ kind: "error", text: `Couldn't load products: ${errorText(e)}` });
    }
  }, []);

  const goBack = useCallback(() => {
    if (lastView.current) void showProducts(lastView.current);
    else setPanel(EMPTY);
  }, [showProducts]);

  const focusProduct = useCallback(async (id: number) => {
    try {
      const product = await api.product(id);
      focusedId.current = id;
      setPanel({ kind: "detail", product });
    } catch (e) {
      setPanel({ kind: "error", text: `Couldn't load that product: ${errorText(e)}` });
    }
  }, []);

  const showCompare = useCallback(async (productIds: number[]) => {
    try {
      const { products } = await api.products(new URLSearchParams({ ids: productIds.join(",") }));
      focusedId.current = null;
      setPanel({ kind: "compare", products });
    } catch (e) {
      setPanel({ kind: "error", text: `Couldn't load the comparison: ${errorText(e)}` });
    }
  }, []);

  const showOrder = useCallback(async (orderId: string) => {
    try {
      setPanel({ kind: "order", order: await api.order(orderId) });
    } catch (e) {
      setPanel({ kind: "error", text: `Couldn't load the order: ${errorText(e)}` });
    }
  }, []);

  const applyAction = useCallback(async (a: UIAction | undefined) => {
    if (!a) return;
    if (a.type === "show_products") await showProducts({ ids: a.product_ids, filters: a.filters });
    else if (a.type === "focus_product" && a.product_id) await focusProduct(a.product_id);
    else if (a.type === "compare" && a.product_ids.length) await showCompare(a.product_ids);
    else if (a.type === "request_photo") setPanel({ kind: "upload" });
    else if (a.type === "checkout") {
      if (a.order_id) await showOrder(a.order_id);
      else setCartOpen(true);
    } else if (a.type === "add_to_cart") setCartOpen(true);
  }, [showProducts, focusProduct, showCompare, showOrder]);

  // ----- cart and profile -----
  const refreshCart = useCallback(async () => {
    if (!ids) return;
    try { setCart(await api.cart(ids)); } catch { /* keep the last cart */ }
  }, [ids]);

  const refreshProfile = useCallback(async () => {
    if (!ids) return;
    try { setProfile(await api.profile(ids)); } catch { /* shown as empty */ }
  }, [ids]);

  const addToCart = useCallback(async (product: Product, size: number) => {
    if (!ids) return;
    try {
      setCart(await api.cartAdd(ids, product.id, size));
      setCartOpen(true);
    } catch (e) {
      addMessage("err", errorText(e));
    }
  }, [ids, addMessage]);

  const removeFromCart = useCallback(async (productId: number, size: number) => {
    if (!ids) return;
    try { setCart(await api.cartRemove(ids, productId, size)); } catch (e) { addMessage("err", errorText(e)); }
  }, [ids, addMessage]);

  const placeOrder = useCallback(async () => {
    if (!ids) return;
    try {
      const order = await api.checkout(ids);
      setCartOpen(false);
      addMessage("bot", `Order ${order.order_id} confirmed. This was a mock checkout, so nothing was charged.`);
      await refreshCart();
      await showOrder(order.order_id);
    } catch (e) {
      addMessage("err", errorText(e));
      await refreshCart();
    }
  }, [ids, addMessage, refreshCart, showOrder]);

  const forgetProfile = useCallback(async () => {
    if (!ids) return;
    try {
      const out = await api.forget(ids);
      addMessage("bot", out.message);
      setProfile(out.profile);
    } catch (e) {
      addMessage("err", errorText(e));
    }
  }, [ids, addMessage]);

  // ----- complexion (photo) flow: consent -> upload -> confirm or correct -----
  const startPhotoFlow = useCallback(() => {
    setProfileOpen(false);
    setPanel({ kind: "consent" });
  }, []);
  const declinePhoto = useCallback(() => setPanel({ kind: "empty", text: "No problem. Nothing was uploaded." }), []);
  const grantConsent = useCallback(async () => {
    if (!ids) return;
    await api.consent(ids);
    setPanel({ kind: "upload" });
  }, [ids]);
  const analyzePhoto = useCallback(async (file: File) => {
    if (!ids) return;
    const estimate = (await api.analyze(ids, await readBase64(file), file.type)).estimate;
    setPanel({ kind: "estimate", estimate });
  }, [ids]);
  const confirmEstimate = useCallback(async (skinTone: string, undertone: string) => {
    if (!ids) return;
    const out = await api.confirm(ids, skinTone, undertone);
    addMessage("bot", out.message);
    setProfile(out.profile);
    setPanel({ kind: "empty", text: "Saved. Ask me for something and I'll weigh your colors when ranking." });
  }, [ids, addMessage]);
  const discardEstimate = useCallback(async () => {
    if (ids) await api.cancel(ids).catch(() => undefined);
    setPanel({ kind: "empty", text: "Discarded. Nothing was saved." });
  }, [ids]);

  // ----- chat -----
  const send = useCallback(async (text: string) => {
    const clean = text.trim();
    if (!clean || busy.current || !ids) return;
    busy.current = true;
    onSend?.();
    addMessage("user", clean);
    setThinking(true);
    let bubble: number | null = null;
    let streamed = "";
    let uiApplied = false;
    try {
      const body = { session_id: ids.sessionId, user_id: ids.userId, message: clean, focus_product_id: focusedId.current };
      let response: ChatResponse;
      if (typeof ReadableStream !== "undefined") {
        response = await streamChat(body, {
          onUi: (ui, s) => { uiApplied = true; setSlots(s); void applyAction(ui); },   // the grid can appear before the words
          onText: (delta) => {
            streamed += delta;
            if (bubble === null) { bubble = addMessage("bot", streamed); setThinking(false); }
            else patchMessage(bubble, streamed);
          },
        });
      } else {
        response = await post<ChatResponse>("/api/chat", body);
      }
      setSlots(response.slots);
      if (bubble === null) addMessage("bot", response.reply);
      else patchMessage(bubble, response.reply);
      await refreshCart();
      if (!uiApplied) await applyAction(response.ui_action);
      void refreshProfile();
      onReply?.(response.reply);
    } catch (e) {
      addMessage("err", `Something went wrong: ${errorText(e)}`);
    } finally {
      setThinking(false);
      busy.current = false;
    }
  }, [ids, onSend, onReply, addMessage, patchMessage, applyAction, refreshCart, refreshProfile]);

  return {
    ready: ids !== null, messages, thinking, panel, slots, cart, profile, cartOpen, profileOpen,
    setCartOpen, setProfileOpen, send, goBack, focusProduct, addToCart, removeFromCart, placeOrder,
    refreshCart, refreshProfile, forgetProfile, startPhotoFlow, declinePhoto, grantConsent, analyzePhoto, confirmEstimate, discardEstimate,
  };
}

export type Shopper = ReturnType<typeof useShopper>;
