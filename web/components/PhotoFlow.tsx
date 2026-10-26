"use client";

import { useState } from "react";
import { errorText } from "@/lib/api";
import type { Estimate } from "@/lib/types";
import { Button, Meta } from "./ui";

export function ConsentCard({ onAgree, onDecline }: { onAgree: () => Promise<void>; onDecline: () => void }) {
  const [error, setError] = useState("");
  return (
    <section aria-label="Color advice from a photo">
      <h2 className="mb-2 text-xl font-semibold">Color advice from a photo</h2>
      <p className="mb-2">
        If you agree, you can upload one photo. I&apos;ll estimate your skin tone and undertone, show you the result to confirm
        or correct, and delete the photo right after it has been analysed. Only the result you confirm is saved, and you can
        clear it any time. This is a general styling guide, not a rule.
      </p>
      <Meta>Prefer not to upload? Just tell me your undertone in the chat instead.</Meta>
      <div className="mt-3 flex gap-2">
        <Button onClick={async () => { try { await onAgree(); } catch (e) { setError(errorText(e)); } }}>I agree, continue</Button>
        <Button variant="ghost" onClick={onDecline}>No thanks</Button>
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-300">{error}</p>}
    </section>
  );
}

export function UploadCard({ onAnalyze }: { onAnalyze: (file: File) => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");
  const [working, setWorking] = useState(false);

  const go = async () => {
    if (!file) { setStatus("Choose a photo first."); return; }
    setWorking(true);
    setStatus("Analysing…");
    try { await onAnalyze(file); } catch (e) { setStatus(errorText(e)); setWorking(false); }
  };
  return (
    <section aria-label="Upload a photo">
      <h2 className="mb-2 text-xl font-semibold">Upload a photo</h2>
      <p className="mb-3">A clear, well-lit photo with your face or skin visible works best.</p>
      <input type="file" accept="image/jpeg,image/png,image/webp" aria-label="Photo" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mb-3 block" />
      <Button onClick={go} disabled={working}>Analyse photo</Button>
      <p role="status" className="mt-2 text-sm text-stone-500 dark:text-stone-400">{status}</p>
    </section>
  );
}

const TONES = ["fair", "light", "medium", "tan", "deep"];
const UNDERTONES = ["warm", "cool", "neutral"];

export function EstimateCard({ estimate, onConfirm, onDiscard }: {
  estimate: Estimate; onConfirm: (tone: string, undertone: string) => Promise<void>; onDiscard: () => void;
}) {
  const [tone, setTone] = useState(estimate.skin_tone);
  const [under, setUnder] = useState(estimate.undertone);
  const [error, setError] = useState("");
  const select = "ml-2 rounded-lg border border-stone-300 bg-stone-50 px-2 py-1 dark:border-neutral-700 dark:bg-neutral-950";
  return (
    <section aria-label="Your estimate">
      <h2 className="mb-2 text-xl font-semibold">Here&apos;s my estimate</h2>
      <p className="mb-3">
        {estimate.confidence === "low"
          ? "I'm not confident about this one (lighting or the photo can mislead). Please set it yourself."
          : "Please check it and change anything that's off. Nothing is saved until you confirm."}
      </p>
      <label className="mb-2 block">Skin tone
        <select value={tone} onChange={(e) => setTone(e.target.value)} className={select}>{TONES.map((t) => <option key={t}>{t}</option>)}</select>
      </label>
      <label className="mb-3 block">Undertone
        <select value={under} onChange={(e) => setUnder(e.target.value)} className={select}>{UNDERTONES.map((t) => <option key={t}>{t}</option>)}</select>
      </label>
      {estimate.note && <Meta>{estimate.note}</Meta>}
      <div className="mt-3 flex gap-2">
        <Button onClick={async () => { try { await onConfirm(tone, under); } catch (e) { setError(errorText(e)); } }}>Confirm and save</Button>
        <Button variant="ghost" onClick={onDiscard}>Discard</Button>
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-300">{error}</p>}
    </section>
  );
}
