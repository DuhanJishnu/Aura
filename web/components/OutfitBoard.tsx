"use client";

import { useState } from "react";
import type { OutfitLook, OutfitPiece } from "@/lib/types";
import { Button, Meta } from "./ui";

function PieceThumb({ piece }: { piece: OutfitPiece }) {
  const [brokenUrl, setBrokenUrl] = useState<string | null>(null);
  const showImage = Boolean(piece.image_url && brokenUrl !== piece.image_url);

  if (showImage) {
    return (
      <img
        src={piece.image_url}
        alt={piece.name}
        loading="lazy"
        onError={() => setBrokenUrl(piece.image_url ?? null)}
        className="h-14 w-14 shrink-0 rounded-xl border border-stone-200 object-cover dark:border-neutral-700"
      />
    );
  }
  return (
    <span
      className="h-14 w-14 shrink-0 rounded-xl border border-stone-200 dark:border-neutral-700"
      style={{ backgroundColor: piece.color_hex || "#8C7A6B" }}
      aria-hidden="true"
    />
  );
}

export default function OutfitBoard({
  outfit,
  onSaveLook,
  onSearchPiece,
  onBack,
}: {
  outfit: OutfitLook;
  onSaveLook: (outfit: OutfitLook) => void;
  onSearchPiece: (query: string) => void;
  onBack: () => void;
}) {
  const [brokenHeroUrl, setBrokenHeroUrl] = useState<string | null>(null);
  const showHero = Boolean(outfit.image_url && brokenHeroUrl !== outfit.image_url);

  return (
    <article className="mx-auto max-w-2xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
        <Button onClick={() => onSaveLook(outfit)}>♥ Save Look</Button>
      </div>

      <header className="overflow-hidden rounded-2xl border border-stone-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        {showHero && (
          <div className="relative max-h-96 w-full overflow-hidden bg-stone-100 dark:bg-neutral-800">
            <img
              src={outfit.image_url}
              alt={outfit.title}
              onError={() => setBrokenHeroUrl(outfit.image_url ?? null)}
              className="max-h-96 w-full object-cover"
            />
          </div>
        )}
        <div className="p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-brand-600 dark:text-brand-400">
            {outfit.vibe} · {outfit.occasion}
          </div>
          <h2 className="mt-1 text-xl font-semibold">{outfit.title}</h2>
          {outfit.total_estimate_text && <Meta>Estimated look total: {outfit.total_estimate_text}</Meta>}
          <p className="mt-2 text-sm text-stone-700 dark:text-stone-200">
            <span className="font-semibold">Color story:</span> {outfit.color_story}
          </p>
          <p className="mt-1 text-sm text-stone-700 dark:text-stone-200">
            <span className="font-semibold">Silhouette:</span> {outfit.proportion_tip}
          </p>
        </div>
      </header>

      <ul className="space-y-2.5">
        {outfit.pieces.map((piece, idx) => (
          <li
            key={`${piece.slot}-${idx}`}
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-stone-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900"
          >
            <div className="flex items-center gap-3">
              <PieceThumb piece={piece} />
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-stone-500 dark:text-stone-400">
                    {piece.slot}
                  </span>
                  {piece.from_closet && (
                    <span className="rounded-full bg-brand-600/15 px-2 py-0.5 text-[11px] font-medium text-brand-700 dark:text-brand-400">
                      From your Closet
                    </span>
                  )}
                </div>
                <div className="font-semibold">{piece.name}</div>
                <Meta>
                  {piece.color}
                  {piece.price_text ? ` · ${piece.price_text}` : ""}
                  {piece.fit_guidance ? ` · ${piece.fit_guidance}` : ""}
                </Meta>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={() => onSearchPiece(`${piece.color} ${piece.name}`)}>
                Find options
              </Button>
              {piece.url && (
                <a
                  href={piece.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-stone-300 px-3 py-2 text-xs font-medium hover:border-brand-600 dark:border-neutral-700"
                >
                  Shop ↗
                </a>
              )}
            </div>
          </li>
        ))}
      </ul>

      {outfit.styling_hacks.length > 0 && (
        <section className="rounded-2xl border border-stone-200 bg-stone-100/70 p-4 dark:border-neutral-800 dark:bg-neutral-900/60">
          <h3 className="text-sm font-semibold">Stylist Finishing Touches</h3>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-stone-700 dark:text-stone-300">
            {outfit.styling_hacks.map((hack, i) => (
              <li key={i}>{hack}</li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
