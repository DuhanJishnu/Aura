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
    const sessionId = stable(window.sessionStorage, "shopper_sid");
    const userId = stable(window.localStorage, "shopper_uid");
    const existingToken = loadToken();
    setIds({ sessionId, userId, token: existingToken });

    if (!existingToken && typeof fetch === "function") {
      void fetch("/api/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      })
        .then(async (res) => {
          if (!res.ok) return null;
          const data = (await res.json()) as { token?: string };
          if (data?.token) {
            try { window.localStorage.setItem("shopper_tok", data.token); } catch { /* ignore */ }
            setIds((prev) => (prev ? { ...prev, token: data.token } : { sessionId, userId, token: data.token }));
          }
          return null;
        })
        .catch(() => undefined);
    }
  }, []);

  return ids;
}
