"use client";

import { useMemo, useState } from "react";
import { ShoppingBag, Sparkles, Trash2 } from "lucide-react";
import type { OutfitLook } from "@/lib/types";
import Mascot from "./Mascot";

export default function WishlistView({
  looks,
  onInspectLook,
  onBuyLook,
  onRemoveLook,
  onStartStyling,
}: {
  looks: OutfitLook[];
  onInspectLook: (look: OutfitLook) => void;
  onBuyLook: (look: OutfitLook) => void;
  onRemoveLook: (lookId: string) => void;
  onStartStyling: () => void;
}) {
  const [filterOccasion, setFilterOccasion] = useState<string>("All");

  const occasions = useMemo(() => {
    const uniq = Array.from(new Set(looks.map((l) => l.occasion).filter(Boolean)));
    return ["All", ...uniq];
  }, [looks]);

  const visible = useMemo(() => {
    if (filterOccasion === "All") return looks;
    return looks.filter((l) => l.occasion === filterOccasion);
  }, [filterOccasion, looks]);

  if (looks.length === 0) {
    return (
      <div className="mx-auto flex max-w-sm flex-col items-center justify-center gap-4 py-12 text-center">
        <Mascot state="idle" compact />
        <div>
          <h2 className="text-lg font-semibold text-stone-100">Your Wishlist is empty</h2>
          <p className="mt-1 text-xs text-stone-400">
            Swipe right on any full look Aura builds for you and it saves right here across reloads.
          </p>
        </div>
        <button
          type="button"
          onClick={onStartStyling}
          className="flex items-center gap-1.5 rounded-full bg-[#6ba58a] px-5 py-2.5 text-sm font-semibold text-neutral-950 hover:brightness-110"
        >
          <Sparkles className="h-4 w-4" />
          Discover outfits
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-stone-100">Saved Wishlist ({looks.length})</h2>
          <p className="text-xs text-stone-400">Right-swiped outfits synced to your Style DNA.</p>
        </div>
        {occasions.length > 2 && (
          <div className="flex flex-wrap gap-1.5">
            {occasions.map((occ) => (
              <button
                key={occ}
                type="button"
                onClick={() => setFilterOccasion(occ)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  filterOccasion === occ
                    ? "bg-[#6ba58a] text-neutral-950"
                    : "border border-white/15 bg-white/5 text-stone-300 hover:border-[#6ba58a]"
                }`}
              >
                {occ}
              </button>
            ))}
          </div>
        )}
      </div>

      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((look) => (
          <li
            key={look.id}
            className="flex flex-col overflow-hidden rounded-[22px] border border-white/10 bg-[#151816]"
          >
            <button
              type="button"
              onClick={() => onInspectLook(look)}
              className="relative h-52 w-full overflow-hidden bg-stone-900 text-left"
            >
              {look.image_url ? (
                <img src={look.image_url} alt={look.title} className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full items-center justify-center gap-2 bg-gradient-to-br from-[#23332b] to-[#111513]">
                  {look.pieces.slice(0, 4).map((p, idx) => (
                    <span
                      key={idx}
                      className="h-8 w-8 rounded-full border border-white/25"
                      style={{ backgroundColor: p.color_hex || "#6ba58a" }}
                    />
                  ))}
                </div>
              )}
              <span className="absolute top-3 left-3 rounded-full bg-black/65 px-2.5 py-0.5 text-[11px] font-semibold text-[#8fd1b2] backdrop-blur-sm">
                {look.occasion}
              </span>
            </button>

            <div className="flex flex-1 flex-col justify-between gap-3 p-4">
              <div>
                <h3 className="font-semibold text-stone-100">{look.title}</h3>
                <p className="mt-0.5 text-xs text-stone-400">
                  {look.total_estimate_text || `${look.pieces.length} pieces`}
                  {look.saved_at ? ` · Saved ${look.saved_at.slice(0, 10)}` : ""}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onInspectLook(look)}
                  className="rounded-full border border-white/15 px-3 py-1.5 text-xs font-medium text-stone-200 hover:border-[#6ba58a]"
                >
                  Details
                </button>
                <button
                  type="button"
                  onClick={() => onBuyLook(look)}
                  className="flex items-center gap-1 rounded-full bg-[#6ba58a] px-3 py-1.5 text-xs font-semibold text-neutral-950 hover:brightness-110"
                >
                  <ShoppingBag className="h-3 w-3" /> Shop
                </button>
                <button
                  type="button"
                  onClick={() => onRemoveLook(look.id)}
                  aria-label={`Remove ${look.title}`}
                  className="ml-auto rounded-full p-1.5 text-stone-400 hover:bg-white/10 hover:text-rose-400"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
