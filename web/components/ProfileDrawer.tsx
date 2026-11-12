"use client";

import { useState } from "react";
import { Camera, ChevronDown, Heart, Palette, Shirt, ThumbsUp, Trash2 } from "lucide-react";
import { FACT_TITLE, STATUS_TEXT } from "@/lib/format";
import type { StyleDNA } from "@/lib/types";
import Drawer from "./Drawer";

const PREFS_PAGE_SIZE = 5;

export default function ProfileDrawer({
  open,
  profile,
  onClose,
  onPhoto,
  onForget,
}: {
  open: boolean;
  profile: StyleDNA | null;
  onClose: () => void;
  onPhoto: (mode: "complexion" | "outfit_check") => void;
  onForget: () => void;
}) {
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [visiblePrefs, setVisiblePrefs] = useState(PREFS_PAGE_SIZE);

  const topAesthetics = Object.entries(profile?.aesthetics ?? {})
    .filter(([, score]) => score > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  const likedSwipes = (profile?.swipe_history ?? []).filter((s) => s.direction !== "dislike").length;
  const latestFacts = [...(profile?.facts ?? [])].reverse();
  const shownFacts = latestFacts.slice(0, visiblePrefs);
  const remainingFacts = Math.max(0, latestFacts.length - shownFacts.length);

  const handleClose = () => {
    setPrefsOpen(false);
    setVisiblePrefs(PREFS_PAGE_SIZE);
    onClose();
  };

  return (
    <Drawer
      open={open}
      title="Your Style DNA"
      onClose={handleClose}
      footer={
        <div className="space-y-2.5">
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => onPhoto("complexion")}
              className="flex items-center justify-center gap-1.5 rounded-2xl border border-[#6ba58a]/40 bg-[#6ba58a]/15 px-3 py-2.5 text-xs font-medium text-[#9ce0c0] transition hover:bg-[#6ba58a]/25"
            >
              <Palette className="h-3.5 w-3.5" />
              Undertone scan
            </button>
            <button
              type="button"
              onClick={() => onPhoto("outfit_check")}
              className="flex items-center justify-center gap-1.5 rounded-2xl border border-white/15 bg-white/5 px-3 py-2.5 text-xs font-medium text-stone-200 transition hover:border-[#6ba58a]/60 hover:bg-white/10"
            >
              <Camera className="h-3.5 w-3.5 text-[#6ba58a]" />
              Rate my outfit
            </button>
          </div>
          <button
            type="button"
            onClick={() => {
              if (window.confirm("Clear your Style DNA, saved closet, swipes, and complexion notes?")) onForget();
            }}
            className="flex w-full items-center justify-center gap-1.5 rounded-xl py-2 text-xs font-medium text-rose-400/80 transition hover:bg-rose-500/10 hover:text-rose-300"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Reset Style Profile
          </button>
        </div>
      }
    >
      <div className="space-y-5">
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-center">
            <div className="flex items-center justify-center gap-1 text-lg font-semibold text-stone-100">
              <Shirt className="h-3.5 w-3.5 text-[#6ba58a]" />
              {profile?.saved_closet.length ?? 0}
            </div>
            <div className="mt-0.5 text-[11px] text-stone-400">Closet</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-center">
            <div className="flex items-center justify-center gap-1 text-lg font-semibold text-stone-100">
              <Heart className="h-3.5 w-3.5 text-[#6ba58a]" />
              {profile?.saved_outfits.length ?? 0}
            </div>
            <div className="mt-0.5 text-[11px] text-stone-400">Wishlist</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-center">
            <div className="flex items-center justify-center gap-1 text-lg font-semibold text-stone-100">
              <ThumbsUp className="h-3.5 w-3.5 text-[#6ba58a]" />
              {likedSwipes}
            </div>
            <div className="mt-0.5 text-[11px] text-stone-400">Liked</div>
          </div>
        </div>

        {topAesthetics.length > 0 && (
          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-3.5">
            <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-stone-400">
              Learned Aesthetics
            </h3>
            <div className="space-y-2">
              {topAesthetics.map(([tag, score]) => (
                <div key={tag} className="space-y-1">
                  <div className="flex justify-between text-xs capitalize text-stone-200">
                    <span>{tag}</span>
                    <span className="text-[#8fd1b2]">{Math.min(100, Math.round(score * 12))}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-[#2f7a62] to-[#6ba58a]"
                      style={{ width: `${Math.min(100, Math.round(score * 12))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {(profile?.liked_colors.length || profile?.disliked_colors.length) ? (
          <section className="space-y-2 rounded-2xl border border-white/10 bg-white/[0.03] p-3.5">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-stone-400">
              Color Palette
            </h3>
            {profile?.liked_colors.length ? (
              <div className="flex flex-wrap gap-1.5">
                {profile.liked_colors.map((c) => (
                  <span
                    key={c}
                    className="rounded-full border border-[#6ba58a]/30 bg-[#6ba58a]/15 px-2.5 py-0.5 text-xs capitalize text-[#9ce0c0]"
                  >
                    ♥ {c}
                  </span>
                ))}
              </div>
            ) : null}
            {profile?.disliked_colors.length ? (
              <div className="flex flex-wrap gap-1.5">
                {profile.disliked_colors.map((c) => (
                  <span
                    key={c}
                    className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-0.5 text-xs capitalize text-rose-300"
                  >
                    ✕ {c}
                  </span>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}

        {latestFacts.length ? (
          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-3.5">
            <button
              type="button"
              aria-expanded={prefsOpen}
              onClick={() => {
                setPrefsOpen((prev) => {
                  const next = !prev;
                  if (!next) setVisiblePrefs(PREFS_PAGE_SIZE);
                  return next;
                });
              }}
              className="flex w-full items-center justify-between text-left"
            >
              <span className="text-[11px] font-semibold uppercase tracking-wider text-stone-400">
                Saved Preferences ({latestFacts.length})
              </span>
              <ChevronDown
                className={`h-4 w-4 text-stone-400 transition-transform ${prefsOpen ? "rotate-180" : ""}`}
              />
            </button>

            {prefsOpen && (
              <div className="mt-2">
                <ul className="divide-y divide-white/10">
                  {shownFacts.map((f, idx) => (
                    <li key={`${f.key}-${f.value}-${idx}`} className="flex items-center justify-between gap-2 py-2 text-xs">
                      <div className="text-stone-200">
                        <span className="text-stone-400">{FACT_TITLE[f.key] ?? f.key}:</span>{" "}
                        <span className="font-medium capitalize">{f.value}</span>
                      </div>
                      <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-stone-400">
                        {STATUS_TEXT[f.source] ?? f.source}
                      </span>
                    </li>
                  ))}
                </ul>

                {remainingFacts > 0 && (
                  <button
                    type="button"
                    onClick={() => setVisiblePrefs((count) => count + PREFS_PAGE_SIZE)}
                    className="mt-2.5 w-full rounded-xl border border-white/12 bg-white/5 py-1.5 text-xs font-medium text-[#8fd1b2] transition hover:border-[#6ba58a]/50 hover:bg-[#6ba58a]/15"
                  >
                    View {Math.min(PREFS_PAGE_SIZE, remainingFacts)} more ({remainingFacts} remaining)
                  </button>
                )}
              </div>
            )}
          </section>
        ) : (
          <div className="rounded-2xl border border-dashed border-white/15 p-4 text-center text-xs leading-relaxed text-stone-400">
            Nothing saved yet! Tell Aura your sizes or vibe, or swipe right on picks you love — uploaded photos are never stored.
          </div>
        )}
      </div>
    </Drawer>
  );
}
