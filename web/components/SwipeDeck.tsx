"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FashionItem } from "@/lib/types";
import Thumb from "./Thumb";
import { Button, Meta } from "./ui";

interface SwipeDeckProps {
  items: FashionItem[];
  onSwipe: (item: FashionItem, direction: "like" | "dislike" | "super_like") => Promise<unknown>;
  onStyleAround: (item: FashionItem) => void;
  onAskOpinion: (item: FashionItem) => void;
  onOpenDetail: (item: FashionItem) => void;
  onSwitchToGrid: () => void;
  onFindMore: () => void;
}

export default function SwipeDeck({
  items,
  onSwipe,
  onStyleAround,
  onAskOpinion,
  onOpenDetail,
  onSwitchToGrid,
  onFindMore,
}: SwipeDeckProps) {
  const [index, setIndex] = useState(0);
  const [drag, setDrag] = useState({ x: 0, y: 0, active: false });
  const [reaction, setReaction] = useState<string>("");
  const [likedCount, setLikedCount] = useState(0);
  const startRef = useRef<{ x: number; y: number } | null>(null);

  // Reset index whenever a fresh deck arrives
  useEffect(() => {
    setIndex(0);
    setDrag({ x: 0, y: 0, active: false });
    setReaction("");
    setLikedCount(0);
  }, [items]);

  const current = items[index] ?? null;

  const commitSwipe = useCallback(
    async (dir: "like" | "dislike" | "super_like") => {
      if (!current) return;
      const picked = current;
      setIndex((i) => i + 1);
      setDrag({ x: 0, y: 0, active: false });
      if (dir !== "dislike") setLikedCount((c) => c + 1);
      const res = (await onSwipe(picked, dir)) as { reaction?: string } | null;
      if (res?.reaction) setReaction(res.reaction);
      if (dir === "super_like") {
        onStyleAround(picked);
      }
    },
    [current, onSwipe, onStyleAround],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!current) return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        void commitSwipe("like");
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        void commitSwipe("dislike");
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        void commitSwipe("super_like");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, commitSwipe]);

  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest("a, button")) return;
    startRef.current = { x: e.clientX, y: e.clientY };
    setDrag({ x: 0, y: 0, active: true });
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!startRef.current) return;
    setDrag({ x: e.clientX - startRef.current.x, y: e.clientY - startRef.current.y, active: true });
  };

  const onPointerUp = () => {
    if (!startRef.current) return;
    startRef.current = null;
    if (drag.x > 90) void commitSwipe("like");
    else if (drag.x < -90) void commitSwipe("dislike");
    else if (drag.y < -95) void commitSwipe("super_like");
    else setDrag({ x: 0, y: 0, active: false });
  };

  const stamp =
    drag.x > 45 ? "LIKE" : drag.x < -45 ? "PASS" : drag.y < -55 ? "STYLE THIS" : null;

  return (
    <div className="mx-auto flex max-w-md flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-stone-500 dark:text-stone-400">
            Style Swipe Deck
          </h2>
          {current && (
            <Meta>
              Card {index + 1} of {items.length} · Drag or use ← ↑ → keys
            </Meta>
          )}
        </div>
        <Button variant="ghost" onClick={onSwitchToGrid}>
          Grid view
        </Button>
      </div>

      {reaction && (
        <div className="rounded-xl border border-brand-500/30 bg-brand-600/10 px-3 py-2 text-xs text-brand-700 dark:text-brand-400">
          {reaction}
        </div>
      )}

      {!current ? (
        <div className="rounded-2xl border border-stone-200 bg-white p-6 text-center shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h3 className="text-lg font-semibold">Deck complete!</h3>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
            You saved {likedCount} piece{likedCount === 1 ? "" : "s"} to your closet and trained Aura on your taste.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Button onClick={onFindMore}>Find more like my likes</Button>
            <Button variant="ghost" onClick={() => setIndex(0)}>
              Review cards again
            </Button>
          </div>
        </div>
      ) : (
        <div className="relative select-none">
          <article
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            style={{
              transform: `translate3d(${drag.x}px, ${drag.y}px, 0) rotate(${drag.x * 0.04}deg)`,
              transition: drag.active ? "none" : "transform 200ms ease-out",
              touchAction: "none",
            }}
            className="cursor-grab overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-md active:cursor-grabbing dark:border-neutral-800 dark:bg-neutral-900"
          >
            <div className="relative">
              <Thumb item={current} className="h-64" />
              {stamp && (
                <div
                  className={`absolute top-4 rounded-lg border-2 px-3 py-1 text-sm font-bold tracking-widest ${
                    stamp === "LIKE"
                      ? "left-4 -rotate-12 border-emerald-400 bg-emerald-950/80 text-emerald-300"
                      : stamp === "PASS"
                        ? "right-4 rotate-12 border-rose-400 bg-rose-950/80 text-rose-300"
                        : "left-1/2 -translate-x-1/2 border-amber-400 bg-amber-950/80 text-amber-300"
                  }`}
                >
                  {stamp}
                </div>
              )}
            </div>

            <div className="space-y-2.5 p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-lg font-semibold leading-snug">{current.name}</h3>
                  <Meta>
                    {current.brand} · <span className="capitalize">{current.color}</span>
                  </Meta>
                </div>
                <span className="shrink-0 rounded-full bg-stone-100 px-2.5 py-1 text-sm font-semibold dark:bg-neutral-800">
                  {current.price_text}
                </span>
              </div>

              {current.aesthetic_tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {current.aesthetic_tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-stone-200 px-2.5 py-0.5 text-xs text-stone-600 dark:border-neutral-700 dark:text-stone-300"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {current.match_reasons.length > 0 && (
                <div className="text-xs font-medium text-brand-700 dark:text-brand-400">
                  ★ {current.match_reasons.join(" · ")}
                </div>
              )}

              {current.why_it_suits_you && (
                <p className="text-sm text-stone-700 dark:text-stone-200">{current.why_it_suits_you}</p>
              )}

              {current.styling_tip && (
                <p className="rounded-lg bg-stone-50 p-2.5 text-xs text-stone-600 dark:bg-neutral-950 dark:text-stone-300">
                  <span className="font-semibold">Style tip:</span> {current.styling_tip}
                </p>
              )}

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs">
                <button
                  type="button"
                  onClick={() => onOpenDetail(current)}
                  className="font-medium text-stone-600 underline hover:text-brand-600 dark:text-stone-300"
                >
                  Full details
                </button>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => onAskOpinion(current)}
                    className="font-medium text-stone-600 underline hover:text-brand-600 dark:text-stone-300"
                  >
                    Ask Aura
                  </button>
                  {current.url && current.image_source !== "ai_generated" ? (
                    <a
                      href={current.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-md border border-stone-300 px-2.5 py-1 font-medium hover:border-brand-600 dark:border-neutral-700"
                    >
                      {current.url_verified ? "Shop online ↗" : "Find online ↗"}
                    </a>
                  ) : current.image_source === "ai_generated" && current.url_verified && current.url ? (
                    <a
                      href={current.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-md border border-stone-300 px-2.5 py-1 font-medium hover:border-brand-600 dark:border-neutral-700"
                    >
                      View store ↗
                    </a>
                  ) : current.image_source === "ai_generated" ? (
                    <span className="rounded-md border border-amber-500/30 bg-amber-950/30 px-2 py-1 text-[11px] text-amber-200">
                      AI visualization
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          </article>

          <div className="mt-3 grid grid-cols-3 gap-2">
            <Button variant="ghost" onClick={() => void commitSwipe("dislike")} aria-label="Pass">
              ✕ Pass
            </Button>
            <Button variant="ghost" onClick={() => void commitSwipe("super_like")} aria-label="Style outfit around this">
              ★ Style This
            </Button>
            <Button onClick={() => void commitSwipe("like")} aria-label="Like and save to closet">
              ♥ Save
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
