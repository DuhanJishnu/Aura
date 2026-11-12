"use client";

import { useState } from "react";
import { errorText } from "@/lib/api";
import type { ComplexionEstimate, OutfitCheckResult } from "@/lib/types";
import { Button, Meta } from "./ui";

export function ConsentCard({
  mode,
  onAgree,
  onDecline,
}: {
  mode: "complexion" | "outfit_check";
  onAgree: () => Promise<void>;
  onDecline: () => void;
}) {
  const [error, setError] = useState("");
  const isOutfit = mode === "outfit_check";
  return (
    <section aria-label={isOutfit ? "Rate my outfit from a photo" : "Color advice from a photo"} className="mx-auto max-w-lg">
      <h2 className="mb-2 text-xl font-semibold">
        {isOutfit ? "Outfit Check & Style Match" : "Seasonal Color & Undertone Advice"}
      </h2>
      <p className="mb-2 text-sm">
        {isOutfit
          ? "Upload one photo of an outfit you're trying on or a piece you want to style. Aura will share honest styling tweaks and ideas to elevate it, then delete the photo right after analysis."
          : "Upload one well-lit photo and Aura will estimate your skin tone, undertone, and seasonal color palette. You can confirm or edit before anything is saved, and the photo is deleted immediately after analysis."}
      </p>
      <Meta>
        Zero retention policy: photos are analyzed in memory only, discarded immediately after processing, and never
        saved to disk or database. Using Reset Style Profile clears all derived palette notes too.
      </Meta>
      <div className="mt-4 flex gap-2">
        <Button
          onClick={async () => {
            try {
              await onAgree();
            } catch (e) {
              setError(errorText(e));
            }
          }}
        >
          I agree, continue
        </Button>
        <Button variant="ghost" onClick={onDecline}>
          No thanks
        </Button>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
    </section>
  );
}

export function UploadCard({
  mode,
  onAnalyze,
}: {
  mode: "complexion" | "outfit_check";
  onAnalyze: (file: File, note: string) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("");
  const [working, setWorking] = useState(false);

  const go = async () => {
    if (!file) {
      setStatus("Choose a photo first.");
      return;
    }
    setWorking(true);
    setStatus("Analysing…");
    try {
      await onAnalyze(file, note);
    } catch (e) {
      setStatus(errorText(e));
      setWorking(false);
    }
  };

  return (
    <section aria-label="Upload a photo" className="mx-auto max-w-lg space-y-3">
      <h2 className="text-xl font-semibold">
        {mode === "outfit_check" ? "Upload your outfit or garment photo" : "Upload a natural-light photo"}
      </h2>
      <p className="text-sm">
        {mode === "outfit_check"
          ? "Mirror pic, flat-lay, or a single garment you want to match."
          : "A clear, natural-light photo with skin visible works best."}
      </p>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        aria-label="Photo"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="block text-sm"
      />
      {mode === "outfit_check" && (
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Optional note (e.g. 'Wearing this to a rooftop dinner')"
          className="w-full rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-950"
        />
      )}
      <Button onClick={go} disabled={working}>
        Analyse photo
      </Button>
      <p role="status" className="text-sm text-stone-500 dark:text-stone-400">
        {status}
      </p>
    </section>
  );
}

const TONES = ["fair", "light", "medium", "tan", "deep"];
const UNDERTONES = ["warm", "cool", "neutral"];
const SEASONS = ["Spring", "Summer", "Autumn", "Winter"];

export function EstimateCard({
  estimate,
  onConfirm,
  onDiscard,
}: {
  estimate: ComplexionEstimate;
  onConfirm: (tone: string, undertone: string, season: string) => Promise<void>;
  onDiscard: () => void;
}) {
  const [tone, setTone] = useState(estimate.skin_tone);
  const [under, setUnder] = useState(estimate.undertone);
  const [season, setSeason] = useState(estimate.color_season);
  const [error, setError] = useState("");
  const select = "ml-2 rounded-lg border border-stone-300 bg-stone-50 px-2 py-1 dark:border-neutral-700 dark:bg-neutral-950";

  return (
    <section aria-label="Your complexion estimate" className="mx-auto max-w-lg space-y-3">
      <h2 className="text-xl font-semibold">Here&apos;s your color palette estimate</h2>
      <p className="text-sm">
        {estimate.confidence === "low"
          ? "Lighting can mislead, so confidence is low — adjust anything below before saving."
          : "Review or adjust anything below before Aura saves it to your Style DNA."}
      </p>
      <label className="block text-sm">
        Skin tone
        <select value={tone} onChange={(e) => setTone(e.target.value)} className={select}>
          {TONES.map((t) => <option key={t}>{t}</option>)}
        </select>
      </label>
      <label className="block text-sm">
        Undertone
        <select value={under} onChange={(e) => setUnder(e.target.value)} className={select}>
          {UNDERTONES.map((t) => <option key={t}>{t}</option>)}
        </select>
      </label>
      <label className="block text-sm">
        Color season
        <select value={season} onChange={(e) => setSeason(e.target.value)} className={select}>
          {SEASONS.map((s) => <option key={s}>{s}</option>)}
        </select>
      </label>
      {estimate.recommended_colors.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {estimate.recommended_colors.map((c) => (
            <span key={c} className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs capitalize dark:bg-neutral-800">
              {c}
            </span>
          ))}
        </div>
      )}
      {estimate.note && <Meta>{estimate.note}</Meta>}
      <div className="flex gap-2 pt-1">
        <Button
          onClick={async () => {
            try {
              await onConfirm(tone, under, season);
            } catch (e) {
              setError(errorText(e));
            }
          }}
        >
          Confirm and save
        </Button>
        <Button variant="ghost" onClick={onDiscard}>
          Discard
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
    </section>
  );
}

export function OutfitCheckCard({
  result,
  onFindAddition,
  onDone,
}: {
  result: OutfitCheckResult;
  onFindAddition: (query: string) => void;
  onDone: () => void;
}) {
  return (
    <article className="mx-auto max-w-lg space-y-4 rounded-2xl border border-stone-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-brand-600 dark:text-brand-400">
            Outfit Check
          </div>
          <h2 className="text-xl font-semibold">{result.overall_vibe}</h2>
        </div>
        <div className="rounded-full bg-brand-600 px-3 py-1 text-sm font-bold text-white dark:bg-brand-400 dark:text-neutral-950">
          {result.rating_out_of_10}/10
        </div>
      </div>

      <p className="text-sm">{result.honest_bestie_summary}</p>

      {result.what_works.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">What works</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-stone-700 dark:text-stone-300">
            {result.what_works.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {result.elevation_tips.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Quick styling tweaks</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-stone-700 dark:text-stone-300">
            {result.elevation_tips.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      )}

      {result.suggested_additions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Pieces to elevate it</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {result.suggested_additions.map((item) => (
              <Button key={item} variant="ghost" className="px-3 py-1 text-xs" onClick={() => onFindAddition(item)}>
                Search {item}
              </Button>
            ))}
          </div>
        </div>
      )}

      <Button variant="ghost" onClick={onDone}>
        Done
      </Button>
    </article>
  );
}
