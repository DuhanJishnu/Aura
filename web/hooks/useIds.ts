"use client";

import { useEffect, useState } from "react";
import type { Ids } from "@/lib/api";

function stable(store: Storage, key: string): string {
  try {
    let value = store.getItem(key);
    if (!value) {
      value = crypto.randomUUID();
      store.setItem(key, value);
    }
    return value;
  } catch {
    return crypto.randomUUID();
  }
}

function loadToken(): string | undefined {
  try {
    return window.localStorage.getItem("shopper_tok") || undefined;
  } catch {
    return undefined;
  }
}

/** sessionId lives for the tab; userId & opaque auth token survive reloads for user scoping. */
export function useIds(): Ids | null {
  const [ids, setIds] = useState<Ids | null>(null);

  useEffect(() => {
    let cancelled = false;
    const sessionId = stable(window.sessionStorage, "shopper_sid");
    const userId = stable(window.localStorage, "shopper_uid");
    const existingToken = loadToken();
    setIds({ sessionId, userId, token: existingToken });

    if (typeof fetch !== "function") return;

    const claimSession = async (uid: string, token?: string): Promise<{ userId: string; token?: string } | null> => {
      try {
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (token) headers["X-Aura-Token"] = token;
        const res = await fetch("/api/auth/session", {
          method: "POST",
          headers,
          body: JSON.stringify({ user_id: uid }),
        });
        if (res.status === 403) {
          // Cached userId is already bound to a different server-side token; rotate to a fresh profile ID.
          const freshId = crypto.randomUUID();
          try {
            window.localStorage.setItem("shopper_uid", freshId);
            window.localStorage.removeItem("shopper_tok");
          } catch { /* ignore */ }
          const retry = await fetch("/api/auth/session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: freshId }),
          });
          if (!retry.ok) return { userId: freshId, token: undefined };
          const retryData = (await retry.json()) as { token?: string };
          if (retryData?.token) {
            try { window.localStorage.setItem("shopper_tok", retryData.token); } catch { /* ignore */ }
          }
          return { userId: freshId, token: retryData?.token };
        }
        if (!res.ok) return null;
        const data = (await res.json()) as { token?: string };
        if (data?.token) {
          try { window.localStorage.setItem("shopper_tok", data.token); } catch { /* ignore */ }
          return { userId: uid, token: data.token };
        }
        return null;
      } catch {
        return null;
      }
    };

    void claimSession(userId, existingToken).then((next) => {
      if (cancelled || !next) return;
      setIds({ sessionId, userId: next.userId, token: next.token });
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return ids;
}
