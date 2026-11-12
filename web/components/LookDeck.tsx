"use client";

import { useState } from "react";
import { ExternalLink, RotateCcw, Sparkles } from "lucide-react";
import type { OutfitLook } from "@/lib/types";
import SwipeStack from "./SwipeStack";

function LookFront({ look }: { look: OutfitLook }) {
  const [imgBroken, setImgBroken] = useState(false);
  const palette = look.pieces.map((p) => p.color_hex).filter(Boolean);
  const bgGradient =
    palette.length >= 2
      ? `linear-gradient(155deg, ${palette[0]} 0%, ${palette[1]} 55%, #121513 100%)`
      : "linear-gradient(155deg, #2d4c3e 0%, #151b18 100%)";

  const tags = (look.tags && look.tags.length > 0 ? look.tags : [look.vibe, look.occasion]).slice(0, 3);

  return (
    <div
      className="relative flex flex-1 flex-col justify-end overflow-hidden"
      style={{ background: bgGradient }}
    >
      {look.image_url && !imgBroken ? (
        <img
          src={look.image_url}
          alt={look.title}
          draggable={false}
          onError={() => setImgBroken(true)}
          className="absolute inset-0 h-full w-full object-cover"
        />
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
          <div className="flex gap-2">
            {look.pieces.slice(0, 4).map((p, idx) => (
              <span
                key={idx}
                className="h-10 w-10 rounded-full border-2 border-white/30 shadow-lg"
                style={{ backgroundColor: p.color_hex || "#6ba58a" }}
              />
            ))}
          </div>
          <span className="text-xs font-medium uppercase tracking-widest text-white/75">
            {look.pieces.length} Styled Pieces
          </span>
        </div>
      )}

      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-3/5 bg-gradient-to-t from-black/95 via-black/60 to-transparent" />

      <div className="relative z-10 space-y-2 p-5 text-left">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <span className="rounded-full bg-[#6ba58a]/25 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-[#8fd1b2] backdrop-blur-sm">
              {look.occasion}
            </span>
            {look.image_source === "ai_generated" && (
              <span className="rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-medium text-amber-200 backdrop-blur-sm">
                AI lookbook viz
              </span>
            )}
          </div>
          {look.total_estimate_text && (
            <span className="rounded-full bg-black/60 px-2.5 py-0.5 text-xs font-semibold text-stone-100 backdrop-blur-sm">
              {look.total_estimate_text}
            </span>
          )}
        </div>

        <h3 className="text-xl font-bold leading-snug text-white">{look.title}</h3>

        <div className="flex flex-wrap gap-1.5">
          {tags.map((t) => (
            <span
              key={t}
              className="rounded-full border border-white/20 bg-black/40 px-2.5 py-0.5 text-[11px] text-stone-200 backdrop-blur-sm"
            >
              {t}
            </span>
          ))}
        </div>

        <div className="flex items-center justify-between pt-1 text-[11px] text-stone-300">
          <span>{look.pieces.length} pieces in this look</span>
          <span className="font-medium text-[#8fd1b2]">Tap card for breakdown ↗</span>
        </div>
      </div>
    </div>
  );
}

function LookInfo({ look, onToggleExpand }: { look: OutfitLook; onToggleExpand: () => void }) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#151816] text-stone-100">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[#6ba58a]">
            {look.vibe} · {look.total_estimate_text}
          </div>
          <h3 className="text-base font-semibold">{look.title}</h3>
        </div>
        <button
          type="button"
          onClick={onToggleExpand}
          className="rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-stone-200 hover:bg-white/20"
        >
          Collapse
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4 text-left">
        <p className="text-xs text-stone-300">
          <span className="font-semibold text-white">Palette:</span> {look.color_story}
        </p>
        <ul className="space-y-2">
          {look.pieces.map((p, idx) => (
            <li
              key={`${p.slot}-${idx}`}
              className="flex items-center justify-between gap-2.5 rounded-xl border border-white/10 bg-white/5 p-2.5"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                {p.image_url ? (
                  <img src={p.image_url} alt={p.name} className="h-10 w-10 shrink-0 rounded-lg object-cover" />
                ) : (
                  <span
                    className="h-10 w-10 shrink-0 rounded-lg border border-white/15"
                    style={{ backgroundColor: p.color_hex || "#6ba58a" }}
                  />
                )}
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-stone-400">
                    {p.slot}
                    {p.store ? ` · ${p.store}` : p.brand ? ` · ${p.brand}` : ""}
                  </div>
                  <div className="truncate text-xs font-semibold text-stone-100">{p.name}</div>
                  <div className="text-[11px] text-[#6ba58a]">{p.price_text || "Check store"}</div>
                </div>
              </div>
              {p.url && (
                <a
                  href={p.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex shrink-0 items-center gap-1 rounded-full border border-white/20 px-2.5 py-1 text-[11px] font-medium hover:border-[#6ba58a]"
                >
                  Shop <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </li>
          ))}
        </ul>
        {look.styling_hacks.length > 0 && (
          <div className="rounded-xl bg-white/5 p-3 text-xs text-stone-300">
            <div className="mb-1 font-semibold text-[#8fd1b2]">Stylist hacks</div>
            <ul className="list-disc space-y-0.5 pl-4">
              {look.styling_hacks.slice(0, 2).map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default function LookDeck({
  looks,
  deckId,
  onSwipe,
  onUndo,
  onLoadMore,
}: {
  looks: OutfitLook[];
  deckId?: string;
  onSwipe: (look: OutfitLook, action: "save" | "skip" | "buy_intent") => Promise<unknown>;
  onUndo?: () => void;
  onLoadMore: () => void;
}) {
  return (
    <SwipeStack
      items={looks}
      getKey={(l) => l.id}
      getPreloadUrl={(l) => l.image_url}
      deckId={deckId ?? looks[0]?.id ?? "empty"}
      noun="Look"
      labels={{
        skip: "Skip look",
        info: "Toggle look breakdown",
        buy: "Buy this look",
        save: "Save look to wishlist",
        buyStamp: "BUY LOOK",
      }}
      renderFront={(look) => <LookFront look={look} />}
      renderInfo={(look, { toggle }) => <LookInfo look={look} onToggleExpand={toggle} />}
      onCommit={(look, action) => {
        const mapped = action === "buy" ? "buy_intent" : action;
        void onSwipe(look, mapped);
      }}
      onUndo={onUndo}
      empty={({ canUndo, undo }) => (
        <div className="mx-auto flex h-full max-w-sm flex-col items-center justify-center gap-4 px-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#6ba58a]/20 text-[#6ba58a]">
            <Sparkles className="h-7 w-7" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-stone-100">You&apos;ve seen all {looks.length} looks!</h3>
            <p className="mt-1 text-xs text-stone-400">
              Aura learned from your swipes and won&apos;t repeat these outfits. Want another fresh batch?
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={onLoadMore}
              className="rounded-full bg-[#6ba58a] px-5 py-2.5 text-sm font-semibold text-neutral-950 transition hover:brightness-110"
            >
              Want more looks?
            </button>
            {canUndo && (
              <button
                type="button"
                onClick={undo}
                className="flex items-center gap-1.5 rounded-full border border-white/15 px-4 py-2.5 text-xs text-stone-200 hover:bg-white/10"
              >
                <RotateCcw className="h-3.5 w-3.5" /> Undo last
              </button>
            )}
          </div>
        </div>
      )}
    />
  );
}
