"use client";

import type { FashionItem, OutfitLook } from "@/lib/types";
import Thumb from "./Thumb";
import { Button, Meta } from "./ui";

export default function ClosetView({
  items,
  outfits,
  onStyleAround,
  onRemove,
  onOpenDetail,
  onBuildClosetOutfit,
  onOpenOutfit,
}: {
  items: FashionItem[];
  outfits: OutfitLook[];
  onStyleAround: (item: FashionItem) => void;
  onRemove: (itemId: string) => void;
  onOpenDetail: (item: FashionItem) => void;
  onBuildClosetOutfit: () => void;
  onOpenOutfit: (outfit: OutfitLook) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Saved Closet ({items.length})</h2>
          <Meta>Pieces you swiped right on — Aura uses these to learn your style and build outfits.</Meta>
        </div>
        {items.length > 0 && (
          <Button onClick={onBuildClosetOutfit}>Build outfit from my closet</Button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-stone-300 p-6 text-center text-sm text-stone-500 dark:border-neutral-700 dark:text-stone-400">
          Your closet is empty! Ask Aura to search for clothes, shoes, or accessories, then swipe right on pieces you love.
        </p>
      ) : (
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(13.5rem,1fr))] gap-3.5">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex flex-col overflow-hidden rounded-xl border border-stone-200 bg-white dark:border-neutral-800 dark:bg-neutral-900"
            >
              <button type="button" onClick={() => onOpenDetail(item)} className="text-left">
                <Thumb item={item} className="h-24" />
              </button>
              <div className="flex flex-1 flex-col justify-between gap-2 p-3">
                <div>
                  <div className="font-semibold leading-snug">{item.name}</div>
                  <Meta>
                    {item.brand} · {item.price_text}
                  </Meta>
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <Button variant="ghost" className="px-2.5 py-1 text-xs" onClick={() => onStyleAround(item)}>
                    Style this
                  </Button>
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-lg border border-stone-300 px-2.5 py-1 text-xs font-medium hover:border-brand-600 dark:border-neutral-700"
                    >
                      Shop ↗
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => onRemove(item.id)}
                    className="ml-auto text-xs text-stone-400 hover:text-rose-600"
                    aria-label={`Remove ${item.name}`}
                  >
                    Remove
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {outfits.length > 0 && (
        <section className="space-y-2.5">
          <h3 className="text-base font-semibold">Saved Looks ({outfits.length})</h3>
          <ul className="grid gap-2.5 sm:grid-cols-2">
            {outfits.map((look) => (
              <li key={look.id}>
                <button
                  type="button"
                  onClick={() => onOpenOutfit(look)}
                  className="w-full rounded-xl border border-stone-200 bg-white p-3 text-left hover:border-brand-600 dark:border-neutral-800 dark:bg-neutral-900"
                >
                  <div className="text-xs font-semibold uppercase text-brand-600 dark:text-brand-400">
                    {look.vibe} · {look.occasion}
                  </div>
                  <div className="font-semibold">{look.title}</div>
                  <Meta>{look.pieces.length} pieces</Meta>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
