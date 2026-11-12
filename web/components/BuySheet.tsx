"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, Heart, ShoppingBag } from "lucide-react";
import { CloseCrossButton } from "./ui";
import type { OutfitLook } from "@/lib/types";

export default function BuySheet({
  look,
  onClose,
  onSaveWishlist,
}: {
  look: OutfitLook | null;
  onClose: () => void;
  onSaveWishlist?: (look: OutfitLook) => void;
}) {
  const openAllLinks = () => {
    if (!look) return;
    look.pieces.forEach((p, idx) => {
      if (p.url) {
        setTimeout(() => {
          window.open(p.url, "_blank", "noopener,noreferrer");
        }, idx * 140);
      }
    });
  };

  return (
    <AnimatePresence>
      {look && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm sm:items-center sm:p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label={`Shop ${look.title}`}
            className="flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-t-[24px] border border-white/15 bg-[#131614] text-stone-100 shadow-2xl sm:rounded-[24px]"
          >
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div>
                <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#6ba58a]">
                  <ShoppingBag className="h-3.5 w-3.5" />
                  Shop this look
                </div>
                <h2 className="mt-0.5 text-base font-semibold">{look.title}</h2>
                {look.total_estimate_text && (
                  <p className="text-xs text-stone-400">Look total: {look.total_estimate_text}</p>
                )}
              </div>
              <CloseCrossButton ariaLabel="Close purchase sheet" onClick={onClose} />
            </div>

            <ul className="flex-1 space-y-2.5 overflow-y-auto p-4">
              {look.pieces.map((piece, idx) => (
                <li
                  key={`${piece.slot}-${idx}`}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/5 p-3"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    {piece.image_url ? (
                      <img
                        src={piece.image_url}
                        alt={piece.name}
                        className="h-12 w-12 shrink-0 rounded-xl object-cover"
                      />
                    ) : (
                      <span
                        className="h-12 w-12 shrink-0 rounded-xl border border-white/15"
                        style={{ backgroundColor: piece.color_hex || "#6ba58a" }}
                      />
                    )}
                    <div className="min-w-0">
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-stone-400">
                        {piece.slot}
                        {piece.store ? ` · ${piece.store}` : piece.brand ? ` · ${piece.brand}` : ""}
                      </div>
                      <div className="truncate text-sm font-medium">{piece.name}</div>
                      <div className="text-xs text-[#6ba58a]">
                        {piece.price_text || "Check store"} · <span className="capitalize text-stone-400">{piece.color}</span>
                      </div>
                    </div>
                  </div>

                  {piece.url && (
                    <a
                      href={piece.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex shrink-0 items-center gap-1 rounded-full bg-[#6ba58a] px-3 py-1.5 text-xs font-semibold text-neutral-950 transition hover:brightness-110"
                    >
                      {piece.url_verified ? "Shop" : "Search"} <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </li>
              ))}
            </ul>

            <div className="flex items-center gap-2 border-t border-white/10 p-4">
              {onSaveWishlist && (
                <button
                  type="button"
                  onClick={() => onSaveWishlist(look)}
                  className="flex items-center gap-1.5 rounded-full border border-white/15 px-4 py-2.5 text-xs font-medium text-stone-200 hover:bg-white/10"
                >
                  <Heart className="h-3.5 w-3.5 text-[#6ba58a]" />
                  Save to Wishlist
                </button>
              )}
              <button
                type="button"
                onClick={openAllLinks}
                className="flex-1 rounded-full bg-[#6ba58a] px-4 py-2.5 text-xs font-semibold text-neutral-950 transition hover:brightness-110"
              >
                Buy Full Look (Open Stores)
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
