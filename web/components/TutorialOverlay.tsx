"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ArrowLeft, ArrowUp, Check, X } from "lucide-react";
import Mascot from "./Mascot";
import { CloseCrossButton } from "./ui";

const STEPS = [
  {
    dir: "right" as const,
    badge: "SAVE",
    title: "Swipe Right to Wishlist",
    text: "Love the look? Swipe right to save it to your Wishlist and teach Aura your taste.",
    color: "text-emerald-300 border-emerald-400/40 bg-emerald-950/60",
    animate: { x: [0, 72, 0], rotate: [0, 8, 0] },
  },
  {
    dir: "left" as const,
    badge: "SKIP",
    title: "Swipe Left to Skip",
    text: "Not your vibe? Swipe left and Aura immediately steers away from colors or cuts you pass on.",
    color: "text-rose-300 border-rose-400/40 bg-rose-950/60",
    animate: { x: [0, -72, 0], rotate: [0, -8, 0] },
  },
  {
    dir: "up" as const,
    badge: "BUY",
    title: "Swipe Up to Shop",
    text: "Ready to wear it? Swipe up anytime to open direct store links for every piece in the look.",
    color: "text-amber-300 border-amber-400/40 bg-amber-950/60",
    animate: { y: [0, -54, 0] },
  },
];

export default function TutorialOverlay({
  open,
  onComplete,
}: {
  open: boolean;
  onComplete: () => void;
}) {
  const [step, setStep] = useState(0);
  const [practiceDone, setPracticeDone] = useState<string | null>(null);

  if (!open) return null;

  const isPractice = step >= STEPS.length;
  const active = STEPS[Math.min(step, STEPS.length - 1)];

  const tryPractice = (label: string) => {
    setPracticeDone(label);
    setTimeout(() => {
      setStep(0);
      setPracticeDone(null);
      onComplete();
    }, 650);
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md"
        role="dialog"
        aria-label="How Aura swipe gestures work"
      >
        <div className="relative w-full max-w-md rounded-[28px] border border-white/15 bg-[#121513] p-6 text-center text-stone-100 shadow-2xl">
          <CloseCrossButton
            ariaLabel="Close tutorial"
            className="absolute top-4 right-4"
            onClick={() => {
              setStep(0);
              setPracticeDone(null);
              onComplete();
            }}
          />

          <div className="mt-2 flex flex-col items-center gap-3">
            <Mascot state="happy" compact />
            <div className="flex gap-1.5">
              {[0, 1, 2, 3].map((i) => (
                <span
                  key={i}
                  className={`h-1.5 rounded-full transition-all ${
                    i === step ? "w-6 bg-[#6ba58a]" : "w-1.5 bg-white/20"
                  }`}
                />
              ))}
            </div>
          </div>

          {!isPractice ? (
            <div className="mt-5 space-y-4">
              <div className="relative mx-auto flex h-44 w-48 items-center justify-center">
                <motion.div
                  key={active.dir}
                  animate={active.animate}
                  transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                  className="flex h-36 w-32 flex-col items-center justify-center gap-2 rounded-2xl border border-white/20 bg-gradient-to-br from-[#23322b] to-[#111513] p-3 shadow-xl"
                >
                  <span className={`rounded-lg border px-2 py-0.5 text-[11px] font-bold tracking-widest ${active.color}`}>
                    {active.badge}
                  </span>
                  {active.dir === "right" ? (
                    <ArrowRight className="h-6 w-6 text-emerald-400" />
                  ) : active.dir === "left" ? (
                    <ArrowLeft className="h-6 w-6 text-rose-400" />
                  ) : (
                    <ArrowUp className="h-6 w-6 text-amber-400" />
                  )}
                  <span className="text-[11px] text-stone-300">Sample Look</span>
                </motion.div>
              </div>

              <div>
                <h3 className="text-lg font-semibold">{active.title}</h3>
                <p className="mt-1 text-sm text-stone-400">{active.text}</p>
              </div>

              <button
                type="button"
                onClick={() => setStep((s) => s + 1)}
                className="w-full rounded-full bg-[#6ba58a] py-2.5 text-sm font-semibold text-neutral-950 transition hover:brightness-110"
              >
                {step < STEPS.length - 1 ? "Next" : "Try practice card"}
              </button>
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              <h3 className="text-lg font-semibold">Your turn! Practice once</h3>
              <p className="text-xs text-stone-400">
                Drag this practice card or tap any action below to unlock your stack.
              </p>

              <div className="relative mx-auto flex h-44 w-56 items-center justify-center">
                <motion.div
                  drag
                  dragSnapToOrigin
                  dragElastic={0.45}
                  onDragEnd={(_, info) => {
                    if (info.offset.x > 65) tryPractice("Saved!");
                    else if (info.offset.x < -65) tryPractice("Skipped!");
                    else if (info.offset.y < -65) tryPractice("Shop Look!");
                  }}
                  className="flex h-40 w-48 cursor-grab flex-col items-center justify-center rounded-2xl border border-[#6ba58a]/50 bg-gradient-to-br from-[#21332b] to-[#131815] p-4 shadow-xl active:cursor-grabbing"
                  style={{ touchAction: "none" }}
                >
                  {practiceDone ? (
                    <div className="flex flex-col items-center gap-1 text-[#6ba58a]">
                      <Check className="h-8 w-8" />
                      <span className="text-sm font-semibold">{practiceDone}</span>
                    </div>
                  ) : (
                    <>
                      <span className="text-xs uppercase tracking-wider text-[#6ba58a]">Practice Look</span>
                      <span className="mt-1 text-sm font-semibold">Minimalist Linen &amp; Sneakers</span>
                      <span className="mt-2 text-[11px] text-stone-400">Swipe ← ↑ →</span>
                    </>
                  )}
                </motion.div>
              </div>

              <div className="flex justify-center gap-2">
                <button
                  type="button"
                  onClick={() => tryPractice("Skipped!")}
                  className="flex items-center gap-1 rounded-full border border-rose-500/40 px-3.5 py-2 text-xs text-rose-300 hover:bg-rose-950/50"
                >
                  <X className="h-3.5 w-3.5" /> Skip
                </button>
                <button
                  type="button"
                  onClick={() => tryPractice("Shop Look!")}
                  className="flex items-center gap-1 rounded-full border border-amber-500/40 px-3.5 py-2 text-xs text-amber-300 hover:bg-amber-950/50"
                >
                  <ArrowUp className="h-3.5 w-3.5" /> Buy
                </button>
                <button
                  type="button"
                  onClick={() => tryPractice("Saved!")}
                  className="flex items-center gap-1 rounded-full bg-[#6ba58a] px-4 py-2 text-xs font-semibold text-neutral-950"
                >
                  <Check className="h-3.5 w-3.5" /> Save
                </button>
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
