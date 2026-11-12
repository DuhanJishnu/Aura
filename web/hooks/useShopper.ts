"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, authHeaders, errorText, post } from "@/lib/api";
import { streamChat, streamLooksSearch } from "@/lib/stream";
import type {
  ChatResponse,
  FashionItem,
  Message,
  OutfitLook,
  PanelView,
  StyleDNA,
  UIAction,
} from "@/lib/types";
import { useIds } from "./useIds";

const WELCOME =
  "Hey bestie! I'm Aura, your AI fashion stylist. Tell me an occasion, a vibe, or something you're hunting for — I'll search real finds online so you can swipe right on what you love!";
const EMPTY: PanelView = {
  kind: "empty",
  text: "Your Swipe Deck, head-to-toe Outfit Boards, and Saved Closet will appear here as we chat.",
};
const DNA_STORAGE_KEY = "shopper_style_dna_v1";

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("I couldn't read that file."));
    reader.readAsDataURL(file);
  });
}

function loadCachedDna(): StyleDNA | null {
  try {
    const raw = window.localStorage.getItem(DNA_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StyleDNA) : null;
  } catch {
    return null;
  }
}

function saveCachedDna(dna: StyleDNA | null): void {
  try {
    if (!dna) window.localStorage.removeItem(DNA_STORAGE_KEY);
    else window.localStorage.setItem(DNA_STORAGE_KEY, JSON.stringify(dna));
  } catch { /* storage blocked */ }
}

function isProfileEmpty(dna: StyleDNA | null | undefined): boolean {
  if (!dna) return true;
  return (
    dna.facts.length === 0 &&
    dna.saved_closet.length === 0 &&
    dna.saved_outfits.length === 0 &&
    dna.swipe_history.length === 0 &&
    Object.keys(dna.sizes || {}).length === 0
  );
}

interface Options {
  onReply?: (text: string) => void;
  onSend?: () => void;
}

/** Central state for chat, Swipe Deck, Outfit Lookbook, Saved Closet, Style DNA, and Photo Studio. */
export function useShopper({ onReply, onSend }: Options = {}) {
  const ids = useIds();
  const [messages, setMessages] = useState<Message[]>([{ id: 0, role: "bot", text: WELCOME }]);
  const [thinking, setThinking] = useState(false);
  const [panel, setPanel] = useState<PanelView>(EMPTY);
  const [styleDna, setStyleDna] = useState<StyleDNA | null>(null);
  const [deckItems, setDeckItems] = useState<FashionItem[]>([]);
  const [deckLooks, setDeckLooks] = useState<OutfitLook[]>([]);
  const [profileOpen, setProfileOpen] = useState(false);
  const [closetOpen, setClosetOpen] = useState(false);
  const [tutorialOpen, setTutorialOpen] = useState(false);
  const [confirmForgetOpen, setConfirmForgetOpen] = useState(false);
  const [buySheetLook, setBuySheetLook] = useState<OutfitLook | null>(null);
  const [intentOpen, setIntentOpen] = useState(false);
  const [lastOccasion, setLastOccasion] = useState("date night");
  const nextId = useRef(1);
  const busy = useRef(false);
  const focusedId = useRef<string | null>(null);
  const lastDeckView = useRef<PanelView | null>(null);
  const syncedOnce = useRef(false);
  const tutorialShownThisSession = useRef(false);

  const addMessage = useCallback((role: Message["role"], text: string): number => {
    const id = nextId.current++;
    setMessages((m) => [...m, { id, role, text }]);
    return id;
  }, []);

  const patchMessage = useCallback((id: number, text: string) => {
    setMessages((m) => m.map((x) => (x.id === id ? { ...x, text } : x)));
  }, []);

  const updateDna = useCallback((dna: StyleDNA) => {
    setStyleDna(dna);
    saveCachedDna(dna);
  }, []);

  // Server is authoritative Single Source of Truth; localStorage acts as optimistic cache & cold bootstrap only.
  useEffect(() => {
    if (!ids || syncedOnce.current) return;
    syncedOnce.current = true;
    const cached = loadCachedDna();
    if (cached) setStyleDna(cached);
    void api
      .profile(ids)
      .then((serverDna) => {
        if (isProfileEmpty(serverDna) && cached && !isProfileEmpty(cached)) {
          return api.syncProfile(ids, cached).then(updateDna);
        }
        updateDna(serverDna);
        return undefined;
      })
      .catch(() => undefined);
  }, [ids, updateDna]);

  const applyAction = useCallback((a: UIAction | undefined, latestDna?: StyleDNA) => {
    const activeDna = latestDna ?? styleDna;
    if (latestDna) updateDna(latestDna);
    if (!a || a.type === "none") return;

    const maybeShowTutorial = () => {
      if (activeDna && !activeDna.tutorial_seen && !tutorialShownThisSession.current) {
        tutorialShownThisSession.current = true;
        setTutorialOpen(true);
      }
    };

    if (a.type === "confirm_forget") {
      setConfirmForgetOpen(true);
      return;
    }

    if (a.type === "swipe_deck" && a.items.length) {
      setDeckItems(a.items);
      focusedId.current = null;
      const view: PanelView = { kind: "swipe_deck", items: a.items };
      lastDeckView.current = view;
      setPanel(view);
      maybeShowTutorial();
    } else if (a.type === "grid" && a.items.length) {
      setDeckItems(a.items);
      focusedId.current = null;
      const view: PanelView = { kind: "grid", items: a.items };
      lastDeckView.current = view;
      setPanel(view);
    } else if (a.type === "focus_item" && a.focus_item) {
      focusedId.current = a.focus_item.id;
      setPanel({ kind: "detail", item: a.focus_item });
    } else if (a.type === "outfit_board") {
      focusedId.current = null;
      if (a.looks && a.looks.length > 0) {
        setDeckLooks(a.looks);
        setLastOccasion(a.looks[0].occasion || "smart casual");
        const view: PanelView = { kind: "looks_deck", looks: a.looks };
        lastDeckView.current = view;
        setPanel(view);
        maybeShowTutorial();
      } else if (a.outfit) {
        const view: PanelView = { kind: "outfit", outfit: a.outfit };
        lastDeckView.current = view;
        setPanel(view);
      }
    } else if (a.type === "compare" && a.items.length) {
      focusedId.current = null;
      setPanel({ kind: "compare", items: a.items });
    } else if (a.type === "closet") {
      setPanel({ kind: "closet" });
    } else if (a.type === "request_photo") {
      setPanel({ kind: "consent", mode: a.photo_mode ?? "complexion" });
    }
  }, [updateDna, styleDna]);

  const openDetail = useCallback((item: FashionItem) => {
    focusedId.current = item.id;
    setPanel({ kind: "detail", item });
  }, []);

  const setViewMode = useCallback((mode: "swipe_deck" | "grid" | "closet" | "wishlist" | "looks_deck" | "home") => {
    if (mode === "home") {
      setPanel(EMPTY);
      return;
    }
    if (mode === "closet") {
      setPanel({ kind: "closet" });
      return;
    }
    if (mode === "wishlist") {
      setPanel({ kind: "wishlist" });
      return;
    }
    if (mode === "looks_deck" && deckLooks.length) {
      const view: PanelView = { kind: "looks_deck", looks: deckLooks };
      lastDeckView.current = view;
      setPanel(view);
      return;
    }
    if ((mode === "swipe_deck" || mode === "grid") && deckItems.length) {
      const view: PanelView = { kind: mode, items: deckItems };
      lastDeckView.current = view;
      setPanel(view);
    }
  }, [deckItems, deckLooks]);

  const goBack = useCallback(() => {
    if (lastDeckView.current) setPanel(lastDeckView.current);
    else if (deckLooks.length) setPanel({ kind: "looks_deck", looks: deckLooks });
    else if (deckItems.length) setPanel({ kind: "swipe_deck", items: deckItems });
    else setPanel(EMPTY);
  }, [deckItems, deckLooks]);

  const markTutorialSeen = useCallback(() => {
    tutorialShownThisSession.current = true;
    setTutorialOpen(false);
    if (styleDna) {
      updateDna({ ...styleDna, tutorial_seen: true });
    }
    if (ids) {
      void api.updatePreferences(ids, { tutorial_seen: true }).then(updateDna).catch(() => undefined);
    }
  }, [ids, styleDna, updateDna]);

  const swipe = useCallback(async (item: FashionItem, direction: "like" | "dislike" | "super_like") => {
    if (!ids) return null;
    try {
      const res = await api.swipe(ids, item, direction);
      updateDna(res.style_dna);
      return res;
    } catch (e) {
      addMessage("err", errorText(e));
      return null;
    }
  }, [ids, updateDna, addMessage]);

  const swipeLook = useCallback(async (look: OutfitLook, action: "save" | "skip" | "buy_intent") => {
    if (!ids) return null;
    if (action === "buy_intent") {
      setBuySheetLook(look);
    }
    if (styleDna) {
      const seen = Array.from(new Set([...(styleDna.seen_look_ids ?? []), look.id]));
      const nextOutfits =
        action === "save"
          ? [
              { ...look, saved_at: look.saved_at || new Date().toISOString() },
              ...styleDna.saved_outfits.filter((o) => o.id !== look.id),
            ]
          : action === "skip"
            ? styleDna.saved_outfits.filter((o) => o.id !== look.id)
            : styleDna.saved_outfits;
      updateDna({ ...styleDna, seen_look_ids: seen, saved_outfits: nextOutfits });
    }
    try {
      const res = await api.swipeLook(ids, look, action);
      updateDna(res.style_dna);
      return res;
    } catch (e) {
      addMessage("err", errorText(e));
      return null;
    }
  }, [ids, styleDna, updateDna, addMessage]);

  const undoSwipeLook = useCallback(async () => {
    if (!ids) return;
    try {
      const res = await api.swipeLook(ids, null, "undo");
      updateDna(res.style_dna);
    } catch { /* ignore */ }
  }, [ids, updateDna]);

  const removeWishlistLook = useCallback(async (lookId: string) => {
    if (styleDna) {
      updateDna({ ...styleDna, saved_outfits: styleDna.saved_outfits.filter((o) => o.id !== lookId) });
    }
    if (!ids) return;
    try {
      const dna = await api.removeWishlistLook(ids, lookId);
      updateDna(dna);
    } catch (e) {
      addMessage("err", errorText(e));
    }
  }, [ids, styleDna, updateDna, addMessage]);

  const searchMoreLooks = useCallback(async () => {
    if (!ids || busy.current) return;
    busy.current = true;
    setThinking(true);
    setPanel({ kind: "loading" });
    const seen = Array.from(new Set([...(styleDna?.seen_look_ids ?? []), ...deckLooks.map((l) => l.id)]));
    const body = {
      session_id: ids.sessionId,
      user_id: ids.userId,
      occasion: lastOccasion || "smart casual",
      vibe: "effortless modern",
      exclude_look_ids: seen,
    };
    try {
      if (typeof ReadableStream !== "undefined") {
        const streamedLooks: OutfitLook[] = [];
        const out = await streamLooksSearch(
          body,
          {
            onLook: (lk) => {
              streamedLooks.push(lk);
              const snapshot = [...streamedLooks];
              setDeckLooks(snapshot);
              const view: PanelView = { kind: "looks_deck", looks: snapshot };
              lastDeckView.current = view;
              setPanel(view);
              setThinking(false);
            },
          },
          ids.token,
        );
        if (out.style_dna) updateDna(out.style_dna);
        if (out.looks.length) {
          setDeckLooks(out.looks);
          const view: PanelView = { kind: "looks_deck", looks: out.looks };
          lastDeckView.current = view;
          setPanel(view);
        }
      } else {
        const out = await api.searchLooks(ids, body.occasion, { excludeLookIds: seen });
        if (out.style_dna) updateDna(out.style_dna);
        if (out.looks.length) {
          setDeckLooks(out.looks);
          const view: PanelView = { kind: "looks_deck", looks: out.looks };
          lastDeckView.current = view;
          setPanel(view);
        }
      }
    } catch (e) {
      addMessage("err", errorText(e));
      goBack();
    } finally {
      setThinking(false);
      busy.current = false;
    }
  }, [ids, styleDna, deckLooks, lastOccasion, updateDna, addMessage, goBack]);

  const removeFromCloset = useCallback(async (itemId: string) => {
    if (!ids) return;
    try {
      const dna = await api.removeClosetItem(ids, itemId);
      updateDna(dna);
    } catch (e) {
      addMessage("err", errorText(e));
    }
  }, [ids, updateDna, addMessage]);

  const saveOutfit = useCallback(async (outfit: OutfitLook) => {
    if (!ids) return;
    try {
      const dna = await api.saveOutfit(ids, outfit);
      updateDna(dna);
      addMessage("bot", `Saved "${outfit.title}" to your Saved Looks!`);
    } catch (e) {
      addMessage("err", errorText(e));
    }
  }, [ids, updateDna, addMessage]);

  const refreshProfile = useCallback(async () => {
    if (!ids) return;
    try {
      updateDna(await api.profile(ids));
    } catch { /* keep cached */ }
  }, [ids, updateDna]);

  const forgetProfile = useCallback(async () => {
    if (!ids) return;
    try {
      const out = await api.forget(ids);
      saveCachedDna(null);
      setStyleDna(out.style_dna);
      setConfirmForgetOpen(false);
      setDeckItems([]);
      setDeckLooks([]);
      setPanel(EMPTY);
      addMessage("bot", out.message);
    } catch (e) {
      addMessage("err", errorText(e));
    }
  }, [ids, addMessage]);

  // ----- Photo Studio (Consent-First, Zero Storage) -----
  const startPhotoFlow = useCallback((mode: "complexion" | "outfit_check" = "complexion") => {
    setProfileOpen(false);
    setPanel({ kind: "consent", mode });
  }, []);

  const declinePhoto = useCallback(() => {
    setPanel({ kind: "empty", text: "No problem! Nothing was uploaded." });
  }, []);

  const grantConsent = useCallback(async (mode: "complexion" | "outfit_check") => {
    if (!ids) return;
    await api.consent(ids);
    setPanel({ kind: "upload", mode });
  }, [ids]);

  const analyzePhoto = useCallback(async (file: File, mode: "complexion" | "outfit_check", note = "") => {
    if (!ids) return;
    const b64 = await readBase64(file);
    if (mode === "outfit_check") {
      const out = await api.analyzeOutfitPhoto(ids, b64, file.type, note);
      setPanel({ kind: "outfit_check", result: out.result });
      addMessage("bot", out.result.honest_bestie_summary);
    } else {
      const out = await api.analyzeComplexion(ids, b64, file.type);
      setPanel({ kind: "estimate", estimate: out.estimate });
    }
  }, [ids, addMessage]);

  const confirmEstimate = useCallback(async (skinTone: string, undertone: string, colorSeason?: string) => {
    if (!ids) return;
    const out = await api.confirmComplexion(ids, skinTone, undertone, colorSeason);
    updateDna(out.style_dna);
    addMessage("bot", out.message);
    setPanel({ kind: "empty", text: "Complexion palette saved! Ask me to search pieces or build an outfit in your best shades." });
  }, [ids, updateDna, addMessage]);

  const discardEstimate = useCallback(async () => {
    if (ids) await api.cancelPhoto(ids).catch(() => undefined);
    setPanel({ kind: "empty", text: "Discarded. Nothing was saved." });
  }, [ids]);

  // ----- Chat -----
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
      const body = {
        session_id: ids.sessionId,
        user_id: ids.userId,
        message: clean,
        focus_item_id: focusedId.current,
      };
      let response: ChatResponse;
      if (typeof ReadableStream !== "undefined") {
        response = await streamChat(
          body,
          {
            onUi: (ui, dna) => {
              uiApplied = true;
              applyAction(ui, dna);
            },
            onText: (delta) => {
              streamed += delta;
              if (bubble === null) {
                bubble = addMessage("bot", streamed);
                setThinking(false);
              } else {
                patchMessage(bubble, streamed);
              }
            },
          },
          fetch,
          "/api/chat/stream",
          ids.token,
        );
      } else {
        response = await post<ChatResponse>("/api/chat", body, ids.token);
      }
      if (response.style_dna) updateDna(response.style_dna);
      if (bubble === null) addMessage("bot", response.reply);
      else patchMessage(bubble, response.reply);
      if (!uiApplied) applyAction(response.ui_action, response.style_dna);
      onReply?.(response.reply);
    } catch (e) {
      addMessage("err", `Something went wrong: ${errorText(e)}`);
    } finally {
      setThinking(false);
      busy.current = false;
    }
  }, [ids, onSend, onReply, addMessage, patchMessage, applyAction, updateDna]);

  return {
    ready: ids !== null,
    ids,
    messages,
    thinking,
    panel,
    styleDna,
    deckItems,
    deckLooks,
    profileOpen,
    closetOpen,
    tutorialOpen,
    confirmForgetOpen,
    buySheetLook,
    intentOpen,
    setProfileOpen,
    setClosetOpen,
    setTutorialOpen,
    setConfirmForgetOpen,
    setBuySheetLook,
    setIntentOpen,
    setPanel,
    markTutorialSeen,
    addMessage,
    send,
    swipe,
    swipeLook,
    undoSwipeLook,
    removeWishlistLook,
    searchMoreLooks,
    openDetail,
    setViewMode,
    goBack,
    applyAction,
    removeFromCloset,
    saveOutfit,
    refreshProfile,
    forgetProfile,
    startPhotoFlow,
    declinePhoto,
    grantConsent,
    analyzePhoto,
    confirmEstimate,
    discardEstimate,
  };
}

export type Shopper = ReturnType<typeof useShopper>;
export { authHeaders };
