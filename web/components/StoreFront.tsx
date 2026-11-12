"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useLiveVoice } from "@/hooks/useLiveVoice";
import { useShopper } from "@/hooks/useShopper";
import { useSpeechOutput } from "@/hooks/useSpeech";
import BuySheet from "./BuySheet";
import Header from "./Header";
import HomeStage from "./HomeStage";
import Mascot from "./Mascot";
import ProductPanel from "./ProductPanel";
import ProfileDrawer from "./ProfileDrawer";
import TutorialOverlay from "./TutorialOverlay";
import { CloseCrossButton } from "./ui";

export default function StoreFront() {
  const resumeVoiceRef = useRef<() => void>(() => {});

  const speech = useSpeechOutput({
    onEnd: () => {
      resumeVoiceRef.current();
    },
  });

  const shopper = useShopper({
    onReply: (text) => {
      if (speech.enabled) {
        speech.speak(text);
      } else {
        setTimeout(() => {
          resumeVoiceRef.current();
        }, 800);
      }
    },
    onSend: speech.cancel,
  });

  const liveVoice = useLiveVoice({
    ids: shopper.ids,
    styleDna: shopper.styleDna,
    onInputTranscript: (text) => shopper.addMessage("user", text),
    onOutputTranscript: (text) => shopper.addMessage("bot", text),
    onUiAction: (ui, dna) => shopper.applyAction(ui, dna),
    onError: (msg) => shopper.addMessage("err", msg),
  });

  const { profileOpen, refreshProfile } = shopper;
  useEffect(() => {
    if (profileOpen) void refreshProfile();
  }, [profileOpen, refreshProfile]);

  const showHome = shopper.panel.kind === "empty";
  const latestMsg = shopper.messages[shopper.messages.length - 1];
  const lastError = latestMsg?.role === "err" ? latestMsg.text : undefined;
  const lastBot =
    shopper.messages.length > 1
      ? [...shopper.messages].reverse().find((m) => m.role === "bot")?.text
      : undefined;

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-[#0b0d0c] text-stone-100">
      <Header
        wishlistCount={shopper.styleDna?.saved_outfits.length ?? 0}
        closetCount={shopper.styleDna?.saved_closet.length ?? 0}
        speech={speech}
        liveVoice={liveVoice}
        onWishlist={() => shopper.setViewMode("wishlist")}
        onCloset={() => shopper.setViewMode("closet")}
        onProfile={() => shopper.setProfileOpen(!shopper.profileOpen)}
        onOutfitCheck={() => shopper.startPhotoFlow("outfit_check")}
        onTutorial={() => shopper.setTutorialOpen(true)}
      />

      <main className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
        {showHome ? (
          <HomeStage
            thinking={shopper.thinking}
            ready={shopper.ready}
            intentOpen={shopper.intentOpen}
            lastBotReply={lastBot}
            lastError={lastError}
            onToggleIntent={() => shopper.setIntentOpen((v) => !v)}
            onSend={(t) => {
              shopper.setIntentOpen(false);
              void shopper.send(t);
            }}
            onVoiceStart={speech.cancel}
            onRegisterResumeVoice={(fn) => {
              resumeVoiceRef.current = fn;
            }}
          />
        ) : (
          <AnimatePresence mode="wait">
            <motion.section
              key={shopper.panel.kind}
              initial={{ y: 40, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 30, opacity: 0 }}
              transition={{ type: "spring", stiffness: 280, damping: 28 }}
              aria-label="Stylist Sheet"
              className="mx-auto mt-2 flex min-h-0 w-full max-w-5xl flex-1 flex-col overflow-hidden rounded-t-[24px] border border-b-0 border-white/12 bg-[#111412] shadow-2xl sm:mt-3"
            >
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
                <div className="flex items-center gap-2.5">
                  <Mascot
                    state={shopper.thinking ? "thinking" : "idle"}
                    compact
                    onClick={() => shopper.setViewMode("home")}
                  />
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-stone-100">
                      {shopper.thinking ? (
                        <>
                          <Sparkles className="h-3.5 w-3.5 animate-spin text-[#6ba58a]" />
                          <span>Aura is updating your picks…</span>
                        </>
                      ) : (
                        <span>Aura&apos;s Stylist Picks</span>
                      )}
                    </div>
                    <div className="text-[11px] text-stone-400">
                      {shopper.panel.kind === "looks_deck"
                        ? "Swipe right to save · left to skip · up to buy"
                        : shopper.panel.kind === "wishlist"
                          ? "Your saved outfits"
                          : "Curated live for your Style DNA"}
                    </div>
                  </div>
                </div>

                <CloseCrossButton ariaLabel="Close stylist sheet" onClick={() => shopper.setViewMode("home")} />
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-4 pb-6">
                <ProductPanel shopper={shopper} />
              </div>
            </motion.section>
          </AnimatePresence>
        )}
      </main>

      <BuySheet
        look={shopper.buySheetLook}
        item={shopper.buySheetItem}
        onClose={() => {
          shopper.setBuySheetLook(null);
          shopper.setBuySheetItem(null);
        }}
        onSaveWishlist={(look) => {
          void shopper.saveOutfit(look);
          shopper.setBuySheetLook(null);
        }}
      />

      <TutorialOverlay open={shopper.tutorialOpen} onComplete={shopper.markTutorialSeen} />

      <ProfileDrawer
        open={shopper.profileOpen}
        profile={shopper.styleDna}
        onClose={() => shopper.setProfileOpen(false)}
        onPhoto={(mode) => shopper.startPhotoFlow(mode)}
        onForget={shopper.forgetProfile}
      />

      {shopper.confirmForgetOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm profile reset"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs"
          onClick={() => shopper.setConfirmForgetOpen(false)}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-white/15 bg-[#131614] p-5 text-stone-100 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-base font-semibold text-white">Reset your Style DNA?</h2>
              <CloseCrossButton
                ariaLabel="Close profile reset dialog"
                onClick={() => shopper.setConfirmForgetOpen(false)}
              />
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-stone-300">
              This permanently clears your Style DNA profile, saved closet, wishlist, swipe history, session memory,
              and local cache.
            </p>
            <div className="mt-4 flex items-center justify-end">
              <button
                type="button"
                onClick={() => void shopper.forgetProfile()}
                className="rounded-xl border border-rose-500/40 bg-rose-600/85 px-3.5 py-2 text-xs font-semibold text-white hover:bg-rose-500"
              >
                Confirm Reset
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
