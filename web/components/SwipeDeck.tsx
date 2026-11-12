"use client";

import { useState } from "react";
import { ExternalLink, LayoutGrid, RotateCcw, Sparkles } from "lucide-react";
import type { FashionItem } from "@/lib/types";
import SwipeStack from "./SwipeStack";

export function ItemFront({ item }: { item: FashionItem }) {
  const [imgBroken, setImgBroken] = useState(false);
  const bgGradient = `linear-gradient(155deg, ${item.color_hex || "#2d4c3e"} 0%, #141715 100%)`;

  return (
    <div
      className="relative flex flex-1 flex-col justify-end overflow-hidden"
      style={{ background: bgGradient }}
    >
      {item.image_url && !imgBroken ? (
        <img
          src={item.image_url}
          alt={item.name}
          draggable={false}
          onError={() => setImgBroken(true)}
          className="absolute inset-0 h-full w-full object-cover"
        />
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
          <span
            className="h-12 w-12 rounded-full border-2 border-white/30 shadow-lg"
            style={{ backgroundColor: item.color_hex || "#6ba58a" }}
          />
          <span className="text-xs font-medium uppercase tracking-widest text-white/75">{item.category}</span>
        </div>
      )}

      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/95 via-black/55 to-transparent" />

      <div className="relative z-10 space-y-1.5 p-5 text-left">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <span className="rounded-full bg-black/55 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-stone-200 backdrop-blur-sm">
              {item.brand}
            </span>
            {item.image_source === "ai_generated" && (
              <span className="rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-medium text-amber-200 backdrop-blur-sm">
                AI visualization
              </span>
            )}
          </div>
          {item.price_text && (
            <span className="rounded-full bg-black/60 px-2.5 py-0.5 text-xs font-semibold text-stone-100 backdrop-blur-sm">
              {item.price_text}
            </span>
          )}
        </div>

        <h3 className="truncate text-lg font-bold leading-snug text-white">{item.name}</h3>
      </div>
    </div>
  );
}

function ItemInfo({
  item,
  onToggleExpand,
  onOpenDetail,
  onStyleAround,
  onAskOpinion,
}: {
  item: FashionItem;
  onToggleExpand: () => void;
  onOpenDetail: (item: FashionItem) => void;
  onStyleAround: (item: FashionItem) => void;
  onAskOpinion: (item: FashionItem) => void;
}) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#151816] text-stone-100">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="min-w-0 pr-2 text-left">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[#6ba58a]">
            {item.brand} · <span className="capitalize">{item.color}</span>
            {item.price_text ? ` · ${item.price_text}` : ""}
          </div>
          <h3 className="truncate text-base font-semibold">{item.name}</h3>
        </div>
        <button
          type="button"
          onClick={onToggleExpand}
          className="shrink-0 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-stone-200 hover:bg-white/20"
        >
          Collapse
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4 text-left">
        {item.aesthetic_tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {item.aesthetic_tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full border border-white/15 bg-white/5 px-2.5 py-0.5 text-[11px] text-stone-300"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {item.match_reasons.length > 0 && (
          <div className="text-xs font-medium text-[#8fd1b2]">★ {item.match_reasons.join(" · ")}</div>
        )}

        {item.why_it_suits_you && <p className="text-xs leading-relaxed text-stone-200">{item.why_it_suits_you}</p>}

        {item.styling_tip && (
          <p className="rounded-xl bg-white/5 p-3 text-xs text-stone-300">
            <span className="font-semibold text-[#8fd1b2]">Style tip:</span> {item.styling_tip}
          </p>
        )}

        {item.source_domain && (
          <div className="text-[11px] text-stone-400">Source: {item.source_domain}</div>
        )}

        <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
          <button
            type="button"
            onClick={() => onStyleAround(item)}
            className="rounded-full border border-[#6ba58a]/40 bg-[#6ba58a]/15 px-3 py-1.5 font-medium text-[#9ce0c0] hover:bg-[#6ba58a]/25"
          >
            ★ Style This
          </button>
          <button
            type="button"
            onClick={() => onAskOpinion(item)}
            className="rounded-full border border-white/15 bg-white/5 px-3 py-1.5 font-medium text-stone-200 hover:bg-white/10"
          >
            Ask Aura
          </button>
          <button
            type="button"
            onClick={() => onOpenDetail(item)}
            className="rounded-full border border-white/15 bg-white/5 px-3 py-1.5 font-medium text-stone-200 hover:bg-white/10"
          >
            Full details
          </button>
          {item.url && (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto flex items-center gap-1 rounded-full border border-white/20 px-3 py-1.5 font-medium text-stone-100 hover:border-[#6ba58a]"
            >
              {item.url_verified ? "Shop online" : "Find online"} <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

/** Image-first swipe deck for individual discovered fashion items, unified on SwipeStack. */
export default function SwipeDeck({
  items,
  deckId,
  onSwipe,
  onUndo,
  onBuy,
  onStyleAround,
  onAskOpinion,
  onOpenDetail,
  onSwitchToGrid,
  onFindMore,
  onNeedMore,
}: {
  items: FashionItem[];
  deckId?: string;
  onSwipe: (item: FashionItem, dir: "like" | "dislike" | "super_like") => Promise<unknown>;
  onUndo?: () => void;
  onBuy?: (item: FashionItem) => void;
  onStyleAround: (item: FashionItem) => void;
  onAskOpinion: (item: FashionItem) => void;
  onOpenDetail: (item: FashionItem) => void;
  onSwitchToGrid: () => void;
  onFindMore: () => void;
  onNeedMore?: () => void;
}) {
  return (
    <SwipeStack
      items={items}
      getKey={(it) => it.id}
      getPreloadUrl={(it) => it.image_url}
      deckId={deckId ?? items[0]?.id ?? "empty"}
      noun="Card"
      labels={{
        skip: "Pass",
        info: "Toggle item details",
        buy: "Buy this item",
        save: "Like and save to closet",
        buyStamp: "BUY",
      }}
      headerRight={
        <button
          type="button"
          onClick={onSwitchToGrid}
          className="flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-2.5 py-1 text-[11px] text-stone-200 hover:border-[#6ba58a]"
        >
          <LayoutGrid className="h-3 w-3" /> Grid
        </button>
      }
      renderFront={(item) => <ItemFront item={item} />}
      renderInfo={(item, { toggle }) => (
        <ItemInfo
          item={item}
          onToggleExpand={toggle}
          onOpenDetail={onOpenDetail}
          onStyleAround={onStyleAround}
          onAskOpinion={onAskOpinion}
        />
      )}
      onCommit={(item, action) => {
        if (action === "buy") {
          onBuy?.(item);
          void onSwipe(item, "like");
        } else if (action === "save") {
          void onSwipe(item, "like");
        } else {
          void onSwipe(item, "dislike");
        }
      }}
      onUndo={onUndo}
      onNeedMore={onNeedMore}
      empty={({ canUndo, undo }) => (
        <div className="mx-auto flex h-full max-w-sm flex-col items-center justify-center gap-4 px-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#6ba58a]/20 text-[#6ba58a]">
            <Sparkles className="h-7 w-7" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-stone-100">You&apos;ve seen all {items.length} picks!</h3>
            <p className="mt-1 text-xs text-stone-400">
              Aura learned from your swipes and won&apos;t repeat these items.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={onFindMore}
              className="rounded-full bg-[#6ba58a] px-5 py-2.5 text-sm font-semibold text-neutral-950 transition hover:brightness-110"
            >
              Find more like my likes
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
