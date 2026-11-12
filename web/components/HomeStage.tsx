"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUp, Mic, Sparkles, Square } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSpeechInput } from "@/hooks/useSpeech";
import Mascot, { type MascotState } from "./Mascot";

const OCCASION_CHIPS = [
  "Date night",
  "College today",
  "Office smart-casual",
  "Weekend coffee",
  "Wedding / festive",
];

const THINKING_LINES = [
  "Scanning real stores online…",
  "Matching your palette & proportions…",
  "Rendering lookbook previews…",
];

export default function HomeStage({
  thinking,
  ready,
  intentOpen,
  lastBotReply,
  onToggleIntent,
  onSend,
  onVoiceStart,
  onRegisterResumeVoice,
}: {
  thinking: boolean;
  ready: boolean;
  intentOpen: boolean;
  lastBotReply?: string;
  onToggleIntent: () => void;
  onSend: (text: string) => void;
  onVoiceStart: () => void;
  onRegisterResumeVoice?: (fn: () => void) => void;
}) {
  const [text, setText] = useState("");
  const [thinkIdx, setThinkIdx] = useState(0);

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
    if (!thinking) {
      setThinkIdx(0);
      return;
    }
    const id = setInterval(() => setThinkIdx((i) => (i + 1) % THINKING_LINES.length), 1800);
    return () => clearInterval(id);
  }, [thinking]);

  const mascotState: MascotState = thinking
    ? "thinking"
    : voice.listening
      ? "listening"
      : text.trim() || intentOpen
        ? "happy"
        : "idle";

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || !ready || thinking) return;
    voice.stop();
    onSend(text);
    setText("");
  };

  return (
    <div className="relative flex flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-6 text-center">
      {/* Subtle dark emerald backdrop glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-1/3 left-1/2 h-80 w-80 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#6ba58a]/12 blur-[110px]"
      />

      <div className="relative z-10 flex w-full max-w-lg flex-col items-center gap-6">
        <Mascot state={mascotState} onClick={onToggleIntent} />

        {/* Speech Bubble / Intent Prompt */}
        <AnimatePresence mode="wait">
          {thinking ? (
            <motion.div
              key="thinking"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="flex items-center gap-2 rounded-full border border-[#6ba58a]/30 bg-[#151a17] px-4 py-2 text-xs font-medium text-[#8fd1b2]"
            >
              <Sparkles className="h-3.5 w-3.5 animate-spin" />
              <span>{THINKING_LINES[thinkIdx]}</span>
            </motion.div>
          ) : intentOpen ? (
            <motion.div
              key="intent"
              initial={{ opacity: 0, y: 8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6 }}
              className="w-full space-y-3 rounded-[22px] border border-[#6ba58a]/30 bg-[#141815]/95 p-4 shadow-xl"
            >
              <p className="text-sm font-medium text-stone-100">What are we getting ready for?</p>
              <div className="flex flex-wrap justify-center gap-2">
                {OCCASION_CHIPS.map((occ) => (
                  <button
                    key={occ}
                    type="button"
                    disabled={!ready}
                    onClick={() => onSend(`Build outfits for ${occ}`)}
                    className="rounded-full border border-[#6ba58a]/40 bg-[#6ba58a]/15 px-3.5 py-1.5 text-xs font-medium text-[#9ce0c0] transition hover:bg-[#6ba58a] hover:text-neutral-950"
                  >
                    {occ}
                  </button>
                ))}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="welcome"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="w-full space-y-2"
            >
              {lastBotReply ? (
                <p
                  title={lastBotReply}
                  className="mx-auto max-w-md px-2 text-center text-sm italic leading-relaxed text-stone-300 line-clamp-2"
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ children }) => <span>{children} </span>,
                      ul: ({ children }) => <span>{children}</span>,
                      li: ({ children }) => <span>{children} · </span>,
                      strong: ({ children }) => <strong className="font-semibold text-stone-100">{children}</strong>,
                      a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="underline text-[#6ba58a]">
                          {children}
                        </a>
                      ),
                    }}
                  >
                    {`“${lastBotReply.replace(/\s+/g, " ").trim()}”`}
                  </ReactMarkdown>
                </p>
              ) : (
                <>
                  <h2 className="text-xl font-semibold tracking-tight text-stone-100 sm:text-2xl">
                    Hey, I&apos;m Aura — ready to style?
                  </h2>
                  <p className="text-xs text-stone-400">
                    Tap me, speak, or type an occasion below to get a swipeable look stack.
                  </p>
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Pill Input + Mic + Send */}
        <form
          onSubmit={submit}
          className="flex w-full items-center gap-2 rounded-full border border-white/15 bg-[#151816] p-1.5 pl-4 shadow-2xl focus-within:border-[#6ba58a]/70"
        >
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={2000}
            autoComplete="off"
            aria-label="Message"
            placeholder="Tell Aura what you're dressing for..."
            className="min-w-0 flex-1 bg-transparent text-sm text-stone-100 placeholder:text-stone-500 focus:outline-none"
          />

          {voice.supported && (
            <button
              type="button"
              onClick={voice.toggle}
              aria-pressed={voice.voiceMode}
              aria-label={voice.voiceMode ? "Stop voice input" : "Start voice input"}
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition ${
                voice.listening
                  ? "bg-[#6ba58a] text-neutral-950 animate-pulse"
                  : "bg-white/10 text-stone-300 hover:bg-white/20"
              }`}
              title={voice.listening ? "Stop voice input" : "Speak to Aura"}
            >
              {voice.listening ? <Square className="h-3.5 w-3.5 fill-current" /> : <Mic className="h-4 w-4" />}
            </button>
          )}

          <button
            type="submit"
            disabled={!ready || thinking || !text.trim()}
            aria-label="Send message"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#6ba58a] text-neutral-950 transition hover:brightness-110 disabled:opacity-40"
          >
            <ArrowUp className="h-4 w-4 stroke-[2.5]" />
          </button>
        </form>

        {voice.status && (
          <p role="status" aria-live="polite" className="text-xs font-medium text-[#8fd1b2]">
            {voice.status}
          </p>
        )}
      </div>
    </div>
  );
}
