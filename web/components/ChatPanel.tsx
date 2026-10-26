"use client";

import { useEffect, useRef, useState } from "react";
import { useSpeechInput } from "@/hooks/useSpeech";
import type { Message } from "@/lib/types";
import { Button } from "./ui";

const CHIPS = [
  { label: "Shoes", message: "I'm looking for shoes" },
  { label: "Clothes", message: "I'm looking for clothes" },
  { label: "Accessories", message: "I'm looking for accessories" },
];

const bubble: Record<Message["role"], string> = {
  user: "self-end bg-brand-600 text-white dark:bg-brand-500",
  bot: "self-start bg-stone-100 dark:bg-neutral-800",
  err: "self-start border border-red-600 text-red-700 dark:border-red-400 dark:text-red-300",
};

export default function ChatPanel({ messages, thinking, ready, onSend, onVoiceStart, onRegisterResumeVoice }: {
  messages: Message[];
  thinking: boolean;
  ready: boolean;
  onSend: (text: string) => void;
  onVoiceStart: () => void;
  onRegisterResumeVoice?: (fn: () => void) => void;
}) {
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const voice = useSpeechInput({
    onInterim: setText,
    onFinal: (t) => {
      setText("");
      onSend(t);
    },
    onStart: onVoiceStart,
  });

  useEffect(() => {
    onRegisterResumeVoice?.(voice.resumeListening);
  }, [onRegisterResumeVoice, voice.resumeListening]);

  useEffect(() => { endRef.current?.scrollIntoView?.({ block: "end" }); }, [messages, thinking]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    voice.stop();
    onSend(text);
    setText("");
  };

  return (
    <section aria-label="Chat" className="flex min-h-0 flex-col border-stone-200 bg-white dark:border-neutral-800 dark:bg-neutral-900 lg:border-r">
      <div className="flex flex-1 flex-col gap-2.5 overflow-y-auto p-4" role="log" aria-live="polite">
        {messages.map((m) => (
          <div key={m.id} className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 ${bubble[m.role]}`}>{m.text}</div>
        ))}
        {thinking && <div className="self-start animate-pulse rounded-2xl bg-stone-100 px-3.5 py-2 italic text-stone-500 dark:bg-neutral-800" aria-label="Thinking">Thinking…</div>}
        <div ref={endRef} />
      </div>

      <div className="flex flex-wrap gap-2 px-3 pt-2" aria-label="Quick start">
        {CHIPS.map((c) => (
          <button key={c.label} type="button" disabled={!ready || thinking} onClick={() => onSend(c.message)}
            className="rounded-full border border-stone-300 px-3 py-1 text-sm hover:border-brand-600 disabled:opacity-50 dark:border-neutral-700">{c.label}</button>
        ))}
      </div>

      <form onSubmit={submit} className="flex gap-2 p-3">
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} autoComplete="off" aria-label="Message"
          placeholder="Tell me what you're looking for…"
          className="min-w-0 flex-1 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 outline-none focus:border-brand-600 dark:border-neutral-700 dark:bg-neutral-950" />
        {voice.supported && (
          <Button
            variant={voice.voiceMode ? "primary" : "ghost"}
            aria-pressed={voice.voiceMode}
            aria-label={voice.voiceMode ? "Stop continuous voice conversation" : "Start continuous voice conversation"}
            onClick={voice.toggle}
            title={voice.voiceMode ? "Hands-free voice mode active. Click to stop." : "Start hands-free voice conversation (keeps listening across questions)"}
            className={voice.listening ? "ring-2 ring-brand-500 animate-pulse font-semibold" : ""}
          >
            {voice.voiceMode ? "Mic • Live" : "Mic"}
          </Button>
        )}
        <Button type="submit" disabled={!ready || thinking || !text.trim()}>Send</Button>
      </form>
      <div role="status" aria-live="polite" className={`min-h-[1.25rem] px-4 pb-2 text-xs ${voice.voiceMode ? "text-brand-600 dark:text-brand-400 font-medium" : "text-stone-500 dark:text-stone-400"}`}>
        {voice.voiceMode ? (voice.status || "Voice mode active (hands-free)") : voice.status}
      </div>
    </section>
  );
}
