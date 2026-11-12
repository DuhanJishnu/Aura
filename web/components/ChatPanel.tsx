"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSpeechInput } from "@/hooks/useSpeech";
import type { Message } from "@/lib/types";
import { Button } from "./ui";

const bubble: Record<Message["role"], string> = {
  user: "self-end bg-brand-600 text-white dark:bg-brand-500",
  bot: "self-start bg-stone-100 dark:bg-neutral-800",
  err: "self-start border border-red-600 text-red-700 dark:border-red-400 dark:text-red-300",
};

export default function ChatPanel({
  messages,
  thinking,
  ready,
  liveStatus,
  onSend,
  onVoiceStart,
  onRegisterResumeVoice,
}: {
  messages: Message[];
  thinking: boolean;
  ready: boolean;
  liveStatus?: string;
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

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages, thinking]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    voice.stop();
    onSend(text);
    setText("");
  };

  const statusLine = liveStatus || (voice.voiceMode ? voice.status || "Voice mode active (hands-free)" : voice.status);

  return (
    <section
      aria-label="Chat"
      className="flex min-h-0 flex-col border-stone-200 bg-white dark:border-neutral-800 dark:bg-neutral-900 lg:border-r"
    >
      <div className="flex flex-1 flex-col gap-2.5 overflow-y-auto p-4" role="log" aria-live="polite">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`max-w-[85%] break-words rounded-2xl px-3.5 py-2 ${
              m.role === "bot" ? "" : "whitespace-pre-wrap"
            } ${bubble[m.role]}`}
          >
            {m.role === "bot" ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="my-1.5 list-disc space-y-0.5 pl-4">{children}</ul>,
                  ol: ({ children }) => <ol className="my-1.5 list-decimal space-y-0.5 pl-4">{children}</ol>,
                  li: ({ children }) => <li className="leading-snug">{children}</li>,
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium underline text-brand-700 hover:text-brand-600 dark:text-brand-400"
                    >
                      {children}
                    </a>
                  ),
                  code: ({ children }) => (
                    <code className="rounded bg-stone-200/80 px-1 py-0.5 text-xs dark:bg-neutral-700">{children}</code>
                  ),
                }}
              >
                {m.text}
              </ReactMarkdown>
            ) : (
              m.text
            )}
          </div>
        ))}
        {thinking && (
          <div
            className="self-start animate-pulse rounded-2xl bg-stone-100 px-3.5 py-2 italic text-stone-500 dark:bg-neutral-800"
            aria-label="Thinking"
          >
            Styling & searching…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={submit} className="flex gap-2 p-3">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={2000}
          autoComplete="off"
          aria-label="Message"
          placeholder="Ask Aura for an outfit, vibe, or item search…"
          className="min-w-0 flex-1 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 outline-none focus:border-brand-600 dark:border-neutral-700 dark:bg-neutral-950"
        />
        {voice.supported && (
          <Button
            variant={voice.voiceMode ? "primary" : "ghost"}
            aria-pressed={voice.voiceMode}
            aria-label={voice.voiceMode ? "Stop continuous voice conversation" : "Start continuous voice conversation"}
            onClick={voice.toggle}
            title={
              voice.voiceMode
                ? "Hands-free voice mode active. Click to stop."
                : "Browser Mic voice fallback (keeps listening across turns)"
            }
            className={voice.listening ? "ring-2 ring-brand-500 animate-pulse font-semibold" : ""}
          >
            {voice.voiceMode ? "Mic • On" : "Mic"}
          </Button>
        )}
        <Button type="submit" disabled={!ready || thinking || !text.trim()}>
          Send
        </Button>
      </form>
      <div
        role="status"
        aria-live="polite"
        className={`min-h-[1.25rem] px-4 pb-2 text-xs ${
          liveStatus || voice.voiceMode
            ? "font-medium text-brand-600 dark:text-brand-400"
            : "text-stone-500 dark:text-stone-400"
        }`}
      >
        {statusLine}
      </div>
    </section>
  );
}
