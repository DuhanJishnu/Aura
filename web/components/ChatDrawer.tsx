"use client";

import { AnimatePresence, motion } from "framer-motion";
import { MessageCircle } from "lucide-react";
import type { Message } from "@/lib/types";
import ChatPanel from "./ChatPanel";
import { CloseCrossButton } from "./ui";

export default function ChatDrawer({
  open,
  onToggle,
  messages,
  thinking,
  ready,
  liveStatus,
  onSend,
  onVoiceStart,
  onRegisterResumeVoice,
}: {
  open: boolean;
  onToggle: (open: boolean) => void;
  messages: Message[];
  thinking: boolean;
  ready: boolean;
  liveStatus?: string;
  onSend: (text: string) => void;
  onVoiceStart: () => void;
  onRegisterResumeVoice?: (fn: () => void) => void;
}) {
  const lastBot = [...messages].reverse().find((m) => m.role === "bot");

  return (
    <>
      {/* Persistent compact Chat Pill at bottom when drawer is closed */}
      {!open && (
        <div className="pointer-events-none fixed inset-x-0 bottom-3 z-30 flex justify-center px-4">
          <button
            type="button"
            onClick={() => onToggle(true)}
            aria-label="Open Aura chat drawer"
            className="pointer-events-auto flex max-w-md items-center gap-2 rounded-full border border-white/15 bg-[#151816]/95 px-4 py-2 text-xs text-stone-200 shadow-2xl backdrop-blur-md transition hover:border-[#6ba58a]"
          >
            <MessageCircle className="h-4 w-4 shrink-0 text-[#6ba58a]" />
            <span className="truncate">
              {thinking
                ? "Aura is styling…"
                : lastBot?.text
                  ? lastBot.text.slice(0, 68) + (lastBot.text.length > 68 ? "…" : "")
                  : "Chat or refine with Aura"}
            </span>
            <span className="shrink-0 rounded-full bg-[#6ba58a]/20 px-2 py-0.5 text-[10px] font-semibold text-[#8fd1b2]">
              Chat
            </span>
          </button>
        </div>
      )}

      {/* Pull-up Chat Drawer */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 flex items-end justify-center bg-black/60 backdrop-blur-xs"
            onClick={() => onToggle(false)}
          >
            <motion.div
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", stiffness: 320, damping: 32 }}
              onClick={(e) => e.stopPropagation()}
              className="flex h-[75vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-[24px] border border-white/15 bg-[#121513] shadow-2xl"
            >
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#6ba58a]">
                  Chat with Aura
                </span>
                <CloseCrossButton ariaLabel="Close chat drawer" onClick={() => onToggle(false)} />
              </div>

              <div className="flex min-h-0 flex-1 flex-col [&>section]:flex-1 [&>section]:border-r-0">
                <ChatPanel
                  messages={messages}
                  thinking={thinking}
                  ready={ready}
                  liveStatus={liveStatus}
                  onSend={(t) => {
                    onSend(t);
                    onToggle(false);
                  }}
                  onVoiceStart={onVoiceStart}
                  onRegisterResumeVoice={onRegisterResumeVoice}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
