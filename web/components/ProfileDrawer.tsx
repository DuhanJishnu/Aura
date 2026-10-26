"use client";

import { FACT_TITLE, STATUS_TEXT } from "@/lib/format";
import type { ProfileView } from "@/lib/types";
import Drawer from "./Drawer";
import { Button, Meta } from "./ui";

export default function ProfileDrawer({ open, profile, onClose, onPhoto, onForget }: {
  open: boolean; profile: ProfileView | null; onClose: () => void; onPhoto: () => void; onForget: () => void;
}) {
  const rows: [string, string, string][] = [];
  if (profile?.size != null) rows.push(["Shoe size", String(profile.size), "saved after a purchase for yourself"]);
  for (const f of profile?.facts ?? []) rows.push([FACT_TITLE[f.key] ?? f.key, f.value, STATUS_TEXT[f.status] ?? f.status]);

  return (
    <Drawer open={open} title="Your profile" onClose={onClose} footer={
      <>
        <Button variant="ghost" onClick={onPhoto}>Color advice from a photo</Button>
        <Button variant="ghost" onClick={() => { if (window.confirm("Delete your saved size, preferences, skin tone and undertone?")) onForget(); }}>Forget my profile</Button>
      </>
    }>
      {rows.length === 0 ? <Meta>Nothing saved yet. I only save what you tell me or confirm, and I never store photos.</Meta> : (
        <ul>
          {rows.map(([k, v, s]) => (
            <li key={`${k}-${v}`} className="border-b border-stone-200 py-2 dark:border-neutral-800"><div>{k}: {v}</div><Meta>{s}</Meta></li>
          ))}
        </ul>
      )}
    </Drawer>
  );
}
