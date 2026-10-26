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
    return crypto.randomUUID(); // storage blocked (private mode): fine for this tab
  }
}

/** sessionId lives for the tab; userId survives tabs so a saved size can be found again. Null until mounted. */
export function useIds(): Ids | null {
  const [ids, setIds] = useState<Ids | null>(null);
  useEffect(() => {
    setIds({ sessionId: stable(window.sessionStorage, "shopper_sid"), userId: stable(window.localStorage, "shopper_uid") });
  }, []);
  return ids;
}
