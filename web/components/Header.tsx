"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, Dna, Heart, HelpCircle, Menu, Mic, Shirt, Volume2, VolumeX, X } from "lucide-react";

export default function Header({
  wishlistCount,
  closetCount,
  speech,
  onWishlist,
  onCloset,
  onProfile,
  onOutfitCheck,
  onTutorial,
}: {
  wishlistCount: number;
  closetCount: number;
  speech: { supported: boolean; enabled: boolean; toggle: () => void };
  liveVoice?: { supported: boolean; connected: boolean; connecting: boolean; toggle: () => void };
  onWishlist: () => void;
  onCloset: () => void;
  onProfile: () => void;
  onOutfitCheck: () => void;
  onTutorial: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [menuOpen]);

  return (
    <header className="relative z-30 flex h-14 shrink-0 flex-nowrap items-center justify-end gap-2 border-b border-white/10 bg-[#0d0f0e]/95 px-3 backdrop-blur-md sm:px-5">
      <div className="flex shrink-0 flex-nowrap items-center gap-1.5 sm:gap-2">
        <button
          type="button"
          onClick={onWishlist}
          aria-label={`Saved wishlist, ${wishlistCount} looks`}
          className="flex items-center gap-1.5 whitespace-nowrap rounded-full border border-white/15 bg-white/5 px-2.5 py-1.5 text-xs font-medium text-stone-200 transition hover:border-[#6ba58a]/60 hover:bg-white/10"
        >
          <Heart className="h-3.5 w-3.5 text-[#6ba58a]" />
          <span>Wishlist</span>
          <span className="rounded-full bg-[#6ba58a] px-1.5 py-0.2 text-[11px] font-bold text-neutral-950">
            {wishlistCount}
          </span>
        </button>

        <button
          type="button"
          onClick={onCloset}
          aria-label={`Saved closet, ${closetCount} items`}
          className="flex items-center gap-1.5 whitespace-nowrap rounded-full border border-white/15 bg-white/5 px-2.5 py-1.5 text-xs font-medium text-stone-200 transition hover:border-[#6ba58a]/60 hover:bg-white/10"
        >
          <Shirt className="h-3.5 w-3.5 text-[#6ba58a]" />
          <span>Closet</span>
          <span className="rounded-full bg-white/15 px-1.5 py-0.2 text-[11px] font-semibold text-stone-100">
            {closetCount}
          </span>
        </button>

        <div className="relative" ref={menuRef}>
          <button
            type="button"
            aria-label="Open Aura menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((o) => !o)}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 bg-white/5 text-stone-200 transition hover:border-[#6ba58a]/60 hover:bg-white/10"
          >
            {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 mt-2 w-56 overflow-hidden rounded-2xl border border-white/15 bg-[#151816] p-1.5 shadow-2xl"
            >
              {speech.supported && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    speech.toggle();
                    setMenuOpen(false);
                  }}
                  className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs font-medium text-stone-200 hover:bg-white/10"
                >
                  <span className="flex items-center gap-2">
                    {speech.enabled ? <Volume2 className="h-4 w-4 text-[#6ba58a]" /> : <VolumeX className="h-4 w-4 text-stone-400" />}
                    Speak replies
                  </span>
                  <span className="text-[11px] text-stone-400">{speech.enabled ? "On" : "Off"}</span>
                </button>
              )}

              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onOutfitCheck();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs font-medium text-stone-200 hover:bg-white/10"
              >
                <Camera className="h-4 w-4 text-[#6ba58a]" />
                Outfit Check (Photo)
              </button>

              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onProfile();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs font-medium text-stone-200 hover:bg-white/10"
              >
                <Dna className="h-4 w-4 text-[#6ba58a]" />
                Style DNA &amp; Sizes
              </button>

              <div className="my-1 border-t border-white/10" />

              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  onTutorial();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs font-medium text-stone-200 hover:bg-white/10"
              >
                <HelpCircle className="h-4 w-4 text-[#6ba58a]" />
                How it works
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
