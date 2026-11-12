"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, useMotionValue, useTransform } from "framer-motion";
import { ArrowUp, Check, ExternalLink, Info, RotateCcw, Sparkles, X } from "lucide-react";
import type { OutfitLook } from "@/lib/types";

function triggerHaptic() {
  try {
    if (typeof navigator !== "undefined" && typeof navigator.vibrate === "function") {
      navigator.vibrate(12);
    }
  } catch { /* ignore */ }
}

function LookCard({
  look,
  isTop,
  stackOffset,
  expanded,
  onToggleExpand,
  onCommit,
}: {
  look: OutfitLook;
  isTop: boolean;
  stackOffset: number;
  expanded: boolean;
  onToggleExpand: () => void;
  onCommit: (action: "save" | "skip" | "buy_intent") => void;
}) {
  const [imgBroken, setImgBroken] = useState(false);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotate = useTransform(x, [-240, 0, 240], [-14, 0, 14]);
  const saveOpacity = useTransform(x, [30, 110], [0, 1]);
  const skipOpacity = useTransform(x, [-110, -30], [1, 0]);
  const buyOpacity = useTransform(y, [-110, -30], [1, 0]);

  const palette = look.pieces.map((p) => p.color_hex).filter(Boolean);
  const bgGradient =
    palette.length >= 2
      ? `linear-gradient(155deg, ${palette[0]} 0%, ${palette[1]} 55%, #121513 100%)`
      : "linear-gradient(155deg, #2d4c3e 0%, #151b18 100%)";

  const tags = (look.tags && look.tags.length > 0 ? look.tags : [look.vibe, look.occasion]).slice(0, 3);

  return (
    <motion.article
      style={{
        x: isTop ? x : 0,
        y: isTop ? y : stackOffset * 12,
        rotate: isTop ? rotate : 0,
        scale: isTop ? 1 : 1 - stackOffset * 0.045,
        zIndex: 20 - stackOffset,
        touchAction: isTop && !expanded ? "none" : "pan-y",
      }}
      drag={isTop && !expanded}
      dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
      dragElastic={0.75}
      onDragEnd={(_, info) => {
        if (!isTop) return;
        const threshold = 95;
        if (info.offset.x > threshold || info.velocity.x > 460) {
          onCommit("save");
        } else if (info.offset.x < -threshold || info.velocity.x < -460) {
          onCommit("skip");
        } else if (info.offset.y < -threshold || info.velocity.y < -460) {
          onCommit("buy_intent");
        }
      }}
      transition={{ type: "spring", stiffness: 320, damping: 28 }}
      className={`absolute inset-0 flex flex-col overflow-hidden rounded-[24px] border border-white/15 bg-[#161917] shadow-2xl select-none ${
        isTop ? "cursor-grab active:cursor-grabbing" : "pointer-events-none opacity-85"
      }`}
    >
      {/* Dynamic Gesture Stamps */}
      {isTop && (
        <>
          <motion.div
            style={{ opacity: saveOpacity }}
            className="pointer-events-none absolute top-5 left-5 z-20 -rotate-12 rounded-xl border-2 border-emerald-400 bg-emerald-950/85 px-3 py-1 text-sm font-extrabold tracking-widest text-emerald-300"
          >
            SAVE
          </motion.div>
          <motion.div
            style={{ opacity: skipOpacity }}
            className="pointer-events-none absolute top-5 right-5 z-20 rotate-12 rounded-xl border-2 border-rose-400 bg-rose-950/85 px-3 py-1 text-sm font-extrabold tracking-widest text-rose-300"
          >
            SKIP
          </motion.div>
          <motion.div
            style={{ opacity: buyOpacity }}
            className="pointer-events-none absolute top-5 left-1/2 z-20 -translate-x-1/2 rounded-xl border-2 border-amber-400 bg-amber-950/85 px-3 py-1 text-sm font-extrabold tracking-widest text-amber-300"
          >
            BUY LOOK
          </motion.div>
        </>
      )}

      {/* Hero Lookbook Visual + Overlay */}
      {!expanded ? (
        <div
          role="button"
          tabIndex={isTop ? 0 : -1}
          onClick={isTop ? onToggleExpand : undefined}
          onKeyDown={(e) => {
            if (isTop && (e.key === "Enter" || e.key === " ")) {
              e.preventDefault();
              onToggleExpand();
            }
          }}
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

          {/* Readability gradient overlay */}
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
      ) : (
        /* Expanded Piece Breakdown View */
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
      )}
    </motion.article>
  );
}

export default function LookDeck({
  looks,
  onSwipe,
  onUndo,
  onLoadMore,
}: {
  looks: OutfitLook[];
  onSwipe: (look: OutfitLook, action: "save" | "skip" | "buy_intent") => Promise<unknown>;
  onUndo?: () => void;
  onLoadMore: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [history, setHistory] = useState<Array<{ index: number; action: string }>>([]);
  const [expanded, setExpanded] = useState(false);

  // Reset stack cleanly when a new batch arrives
  const batchKey = looks.map((l) => l.id).join("|");
  useEffect(() => {
    setIndex(0);
    setHistory([]);
    setExpanded(false);
  }, [batchKey]);

  // Preload next 3 card images
  useEffect(() => {
    if (typeof window === "undefined") return;
    looks.slice(index + 1, index + 4).forEach((lk) => {
      if (lk.image_url) {
        const img = new window.Image();
        img.src = lk.image_url;
      }
    });
  }, [index, looks]);

  const current = looks[index];

  const commit = useCallback(
    (action: "save" | "skip" | "buy_intent") => {
      if (!current) return;
      triggerHaptic();
      setExpanded(false);
      setHistory((h) => [...h, { index, action }]);
      if (action !== "buy_intent") {
        setIndex((i) => i + 1);
      } else {
        setIndex((i) => i + 1);
      }
      void onSwipe(current, action);
    },
    [current, index, onSwipe],
  );

  const undo = useCallback(() => {
    if (!history.length) return;
    const prev = history[history.length - 1];
    setHistory((h) => h.slice(0, -1));
    setExpanded(false);
    setIndex(prev.index);
    onUndo?.();
  }, [history, onUndo]);

  // Keyboard navigation (Left = Skip, Right = Save, Up = Buy, Escape = Collapse)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        commit("save");
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        commit("skip");
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        commit("buy_intent");
      } else if (e.key === "Escape" && expanded) {
        setExpanded(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [commit, expanded]);

  if (!current) {
    return (
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
          {history.length > 0 && (
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
    );
  }

  const visibleSlice = looks.slice(index, index + 3);

  return (
    <div className="mx-auto flex h-full w-full max-w-md flex-col items-center justify-between gap-3 px-3 pb-2">
      <div className="flex w-full items-center justify-between text-xs text-stone-400">
        <span>
          Look {index + 1} of {looks.length}
        </span>
        {history.length > 0 ? (
          <button
            type="button"
            onClick={undo}
            aria-label="Undo last swipe"
            className="flex items-center gap-1 rounded-full border border-white/15 px-2.5 py-1 text-[11px] font-medium text-stone-200 hover:border-[#6ba58a]"
          >
            <RotateCcw className="h-3 w-3" /> Undo
          </button>
        ) : (
          <span className="text-[11px]">Drag ← ↑ → or tap card</span>
        )}
      </div>

      {/* Card Stack Container */}
      <div className="relative h-[430px] w-full flex-1 min-h-[340px] max-h-[540px]">
        {visibleSlice
          .map((look, offset) => ({ look, offset }))
          .reverse()
          .map(({ look, offset }) => (
            <LookCard
              key={look.id}
              look={look}
              isTop={offset === 0}
              stackOffset={offset}
              expanded={offset === 0 && expanded}
              onToggleExpand={() => setExpanded((x) => !x)}
              onCommit={commit}
            />
          ))}
      </div>

      {/* 4 Fallback Buttons: Skip / Info / Save / Buy */}
      <div className="flex w-full items-center justify-center gap-3 pt-1">
        <button
          type="button"
          onClick={() => commit("skip")}
          aria-label="Skip look"
          className="flex h-12 w-12 items-center justify-center rounded-full border border-rose-500/40 bg-rose-950/35 text-rose-300 transition hover:scale-105 hover:bg-rose-900/50"
          title="Skip (Left Arrow)"
        >
          <X className="h-5 w-5" />
        </button>

        <button
          type="button"
          onClick={() => setExpanded((x) => !x)}
          aria-label="Toggle look breakdown"
          aria-pressed={expanded}
          className="flex h-11 w-11 items-center justify-center rounded-full border border-white/20 bg-white/5 text-stone-200 transition hover:scale-105 hover:border-[#6ba58a]"
          title="Outfit piece details"
        >
          <Info className="h-4 w-4" />
        </button>

        <button
          type="button"
          onClick={() => commit("buy_intent")}
          aria-label="Buy this look"
          className="flex h-12 items-center gap-1.5 rounded-full border border-amber-400/50 bg-amber-950/40 px-4 text-xs font-semibold text-amber-300 transition hover:scale-105 hover:bg-amber-900/50"
          title="Shop pieces (Up Arrow)"
        >
          <ArrowUp className="h-4 w-4" />
          Buy
        </button>

        <button
          type="button"
          onClick={() => commit("save")}
          aria-label="Save look to wishlist"
          className="flex h-12 w-12 items-center justify-center rounded-full bg-[#6ba58a] text-neutral-950 shadow-[0_0_20px_rgba(107,165,138,0.4)] transition hover:scale-105 hover:brightness-110"
          title="Save to Wishlist (Right Arrow)"
        >
          <Check className="h-5 w-5 stroke-[2.6]" />
        </button>
      </div>
    </div>
  );
}
