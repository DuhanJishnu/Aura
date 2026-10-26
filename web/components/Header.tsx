"use client";

import { Button } from "./ui";

export default function Header({ cartCount, speech, onProfile, onCart }: {
  cartCount: number;
  speech: { supported: boolean; enabled: boolean; toggle: () => void };
  onProfile: () => void;
  onCart: () => void;
}) {
  return (
    <header className="flex items-center gap-2 border-b border-stone-200 bg-white px-4 py-2.5 dark:border-neutral-800 dark:bg-neutral-900">
      <h1 className="mr-auto text-base font-semibold tracking-wide">Shopper</h1>
      {speech.supported && (
        <Button variant="ghost" aria-pressed={speech.enabled} onClick={speech.toggle} title="Read replies aloud">
          Speak replies: {speech.enabled ? "on" : "off"}
        </Button>
      )}
      <Button variant="ghost" onClick={onProfile}>Profile</Button>
      <Button variant="ghost" onClick={onCart} aria-label={`Cart, ${cartCount} items`}>
        Cart <span className="ml-1 rounded-full bg-brand-600 px-2 py-0.5 text-xs text-white dark:bg-brand-400 dark:text-neutral-950">{cartCount}</span>
      </Button>
    </header>
  );
}
