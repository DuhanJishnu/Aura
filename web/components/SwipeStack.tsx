"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, useMotionValue, useTransform } from "framer-motion";
import { ArrowUp, Check, Info, RotateCcw, X } from "lucide-react";

export interface SwipeStackLabels {
  skip?: string;
  info?: string;
  buy?: string;
  save?: string;
  buyStamp?: string;
}

export interface SwipeStackProps<T> {
  items: T[];
  getKey: (item: T) => string;
  getPreloadUrl?: (item: T) => string | undefined;
  deckId: string;
  noun?: string;
  labels?: SwipeStackLabels;
  headerRight?: React.ReactNode;
  renderFront: (item: T, ctl: { expanded: boolean; toggle: () => void }) => React.ReactNode;
  renderInfo: (item: T, ctl: { toggle: () => void }) => React.ReactNode;
  onCommit: (item: T, action: "save" | "skip" | "buy") => void;
  onUndo?: () => void;
  onNeedMore?: () => void;
  empty: (ctl: { canUndo: boolean; undo: () => void }) => React.ReactNode;
}

function triggerHaptic() {
  try {
    if (typeof navigator !== "undefined" && typeof navigator.vibrate === "function") {
      navigator.vibrate(12);
    }
  } catch { /* ignore */ }
}

function StackCard<T>({
  item,
  isTop,
  stackOffset,
  expanded,
  buyStamp,
  onToggleExpand,
  onCommit,
  renderFront,
  renderInfo,
}: {
  item: T;
  isTop: boolean;
  stackOffset: number;
  expanded: boolean;
  buyStamp: string;
  onToggleExpand: () => void;
  onCommit: (action: "save" | "skip" | "buy") => void;
  renderFront: (item: T, ctl: { expanded: boolean; toggle: () => void }) => React.ReactNode;
  renderInfo: (item: T, ctl: { toggle: () => void }) => React.ReactNode;
}) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotate = useTransform(x, [-240, 0, 240], [-14, 0, 14]);
  const saveOpacity = useTransform(x, [30, 110], [0, 1]);
  const skipOpacity = useTransform(x, [-110, -30], [1, 0]);
  const buyOpacity = useTransform(y, [-110, -30], [1, 0]);

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
          onCommit("buy");
        }
      }}
      transition={{ type: "spring", stiffness: 320, damping: 28 }}
      className={`absolute inset-0 flex flex-col overflow-hidden rounded-[24px] border border-white/15 bg-[#161917] shadow-2xl select-none ${
        isTop ? "cursor-grab active:cursor-grabbing" : "pointer-events-none opacity-85"
      }`}
    >
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
            {buyStamp}
          </motion.div>
        </>
      )}

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
          className="relative flex flex-1 flex-col overflow-hidden"
        >
          {renderFront(item, { expanded, toggle: onToggleExpand })}
        </div>
      ) : (
        renderInfo(item, { toggle: onToggleExpand })
      )}
    </motion.article>
  );
}

/** Shared framer-motion swipe stack for both outfit lookbooks and individual fashion items. */
export default function SwipeStack<T>({
  items,
  getKey,
  getPreloadUrl,
  deckId,
  noun = "Card",
  labels,
  headerRight,
  renderFront,
  renderInfo,
  onCommit,
  onUndo,
  onNeedMore,
  empty,
}: SwipeStackProps<T>) {
  const [index, setIndex] = useState(0);
  const [history, setHistory] = useState<Array<{ index: number; action: string }>>([]);
  const [expanded, setExpanded] = useState(false);
  const prefetchedLenRef = useRef<number>(-1);

  // Reset stack ONLY when deckId changes (not when items are appended to the same deck)
  useEffect(() => {
    setIndex(0);
    setHistory([]);
    setExpanded(false);
    prefetchedLenRef.current = -1;
  }, [deckId]);

  // Preload next 3 card images
  useEffect(() => {
    if (typeof window === "undefined" || !getPreloadUrl) return;
    items.slice(index + 1, index + 4).forEach((item) => {
      const url = getPreloadUrl(item);
      if (url) {
        const img = new window.Image();
        img.src = url;
      }
    });
  }, [index, items, getPreloadUrl]);

  // Trigger onNeedMore once per batch length when <= 3 cards remain
  useEffect(() => {
    if (!onNeedMore || items.length === 0) return;
    const remaining = items.length - index;
    if (remaining > 0 && remaining <= 3 && prefetchedLenRef.current !== items.length) {
      prefetchedLenRef.current = items.length;
      onNeedMore();
    }
  }, [index, items.length, onNeedMore]);

  const current = items[index];

  const commit = useCallback(
    (action: "save" | "skip" | "buy") => {
      if (!current) return;
      triggerHaptic();
      setExpanded(false);
      setHistory((h) => [...h, { index, action }]);
      setIndex((i) => i + 1);
      onCommit(current, action);
    },
    [current, index, onCommit],
  );

  const undo = useCallback(() => {
    if (!history.length) return;
    const prev = history[history.length - 1];
    setHistory((h) => h.slice(0, -1));
    setExpanded(false);
    setIndex(prev.index);
    onUndo?.();
  }, [history, onUndo]);

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
        commit("buy");
      } else if (e.key === "Escape" && expanded) {
        setExpanded(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [commit, expanded]);

  if (!current) {
    return <>{empty({ canUndo: history.length > 0, undo })}</>;
  }

  const visibleSlice = items.slice(index, index + 3);
  const skipLabel = labels?.skip ?? "Skip";
  const infoLabel = labels?.info ?? "Toggle details";
  const buyLabel = labels?.buy ?? "Buy";
  const saveLabel = labels?.save ?? "Save";
  const buyStamp = labels?.buyStamp ?? "BUY";

  return (
    <div className="mx-auto flex h-full w-full max-w-md flex-col items-center justify-between gap-3 px-3 pb-2">
      <div className="flex w-full items-center justify-between gap-2 text-xs text-stone-400">
        <span>
          {noun} {index + 1} of {items.length}
        </span>
        <div className="flex items-center gap-2">
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
          {headerRight}
        </div>
      </div>

      {/* Card Stack Container */}
      <div className="relative h-[430px] w-full flex-1 min-h-[340px] max-h-[540px]">
        {visibleSlice
          .map((item, offset) => ({ item, offset }))
          .reverse()
          .map(({ item, offset }) => (
            <StackCard
              key={getKey(item)}
              item={item}
              isTop={offset === 0}
              stackOffset={offset}
              expanded={offset === 0 && expanded}
              buyStamp={buyStamp}
              onToggleExpand={() => setExpanded((x) => !x)}
              onCommit={(action) => {
                triggerHaptic();
                setExpanded(false);
                setHistory((h) => [...h, { index, action }]);
                setIndex((i) => i + 1);
                onCommit(item, action);
              }}
              renderFront={renderFront}
              renderInfo={renderInfo}
            />
          ))}
      </div>

      {/* 4 Unified Actions: Skip / Info / Buy / Save */}
      <div className="flex w-full items-center justify-center gap-3 pt-1">
        <button
          type="button"
          onClick={() => commit("skip")}
          aria-label={skipLabel}
          className="flex h-12 w-12 items-center justify-center rounded-full border border-rose-500/40 bg-rose-950/35 text-rose-300 transition hover:scale-105 hover:bg-rose-900/50"
          title="Skip (Left Arrow)"
        >
          <X className="h-5 w-5" />
        </button>

        <button
          type="button"
          onClick={() => setExpanded((x) => !x)}
          aria-label={infoLabel}
          aria-pressed={expanded}
          className="flex h-11 w-11 items-center justify-center rounded-full border border-white/20 bg-white/5 text-stone-200 transition hover:scale-105 hover:border-[#6ba58a]"
          title="Details"
        >
          <Info className="h-4 w-4" />
        </button>

        <button
          type="button"
          onClick={() => commit("buy")}
          aria-label={buyLabel}
          className="flex h-12 items-center gap-1.5 rounded-full border border-amber-400/50 bg-amber-950/40 px-4 text-xs font-semibold text-amber-300 transition hover:scale-105 hover:bg-amber-900/50"
          title="Shop (Up Arrow)"
        >
          <ArrowUp className="h-4 w-4" />
          Buy
        </button>

        <button
          type="button"
          onClick={() => commit("save")}
          aria-label={saveLabel}
          className="flex h-12 w-12 items-center justify-center rounded-full border border-[#6ba58a]/60 bg-[#6ba58a] text-neutral-950 shadow-lg transition hover:scale-105 hover:brightness-110"
          title="Save (Right Arrow)"
        >
          <Check className="h-5 w-5 stroke-[2.5]" />
        </button>
      </div>
    </div>
  );
}
