"use client";

import type { FashionItem } from "@/lib/types";
import Thumb from "./Thumb";
import { Button, Meta } from "./ui";

export default function ProductDetail({
  item,
  onBack,
  onAsk,
  onSave,
  onStyleAround,
}: {
  item: FashionItem;
  onBack: () => void;
  onAsk: () => void;
  onSave: () => void;
  onStyleAround: () => void;
}) {
  return (
    <article className="mx-auto max-w-xl">
      <Button variant="ghost" className="mb-3" onClick={onBack}>
        ← Back
      </Button>
      <Thumb item={item} className="mb-4 h-52 rounded-2xl text-xl" />
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">{item.name}</h2>
          <Meta>
            {item.brand} · <span className="capitalize">{item.color}</span> · {item.category}
          </Meta>
        </div>
        <div className="rounded-full bg-stone-100 px-3 py-1 text-base font-semibold dark:bg-neutral-800">
          {item.price_text}
        </div>
      </div>

      {item.aesthetic_tags.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {item.aesthetic_tags.map((t) => (
            <span key={t} className="rounded-full border border-stone-200 px-2.5 py-0.5 text-xs dark:border-neutral-700">
              {t}
            </span>
          ))}
        </div>
      )}

      {item.why_it_suits_you && <p className="mt-3 text-sm">{item.why_it_suits_you}</p>}
      {item.fit_note && (
        <p className="mt-2 text-sm text-stone-600 dark:text-stone-300">
          <span className="font-semibold">Fit note:</span> {item.fit_note}
        </p>
      )}
      {item.styling_tip && (
        <p className="mt-2 rounded-xl bg-stone-100 p-3 text-sm dark:bg-neutral-900">
          <span className="font-semibold">How Aura would style it:</span> {item.styling_tip}
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={onSave}>♥ Save to Closet</Button>
        <Button variant="ghost" onClick={onStyleAround}>
          ★ Build outfit around this
        </Button>
        <Button variant="ghost" onClick={onAsk}>
          Ask Aura about this
        </Button>
        {item.url && (item.image_source !== "ai_generated" || item.url_verified) ? (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium hover:border-brand-600 dark:border-neutral-700"
          >
            {item.url_verified ? "Shop online ↗" : "Search online ↗"}
          </a>
        ) : item.image_source === "ai_generated" ? (
          <span className="rounded-lg border border-amber-500/30 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
            AI visualization (no direct product listing)
          </span>
        ) : null}
      </div>
    </article>
  );
}
