"use client";

import { useEffect, useRef } from "react";
import { useShopper } from "@/hooks/useShopper";
import { useSpeechOutput } from "@/hooks/useSpeech";
import CartDrawer from "./CartDrawer";
import ChatPanel from "./ChatPanel";
import Header from "./Header";
import ProductPanel from "./ProductPanel";
import ProfileDrawer from "./ProfileDrawer";

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
  const { ready, refreshCart, refreshProfile } = shopper;

  useEffect(() => { if (ready) void refreshCart(); }, [ready, refreshCart]);   // a reload keeps the server-side cart
  useEffect(() => { if (shopper.profileOpen) void refreshProfile(); }, [shopper.profileOpen, refreshProfile]);

  return (
    <>
      <Header cartCount={shopper.cart.items.length} speech={speech}
        onProfile={() => shopper.setProfileOpen(!shopper.profileOpen)} onCart={() => shopper.setCartOpen(!shopper.cartOpen)} />
      <main className="grid min-h-0 flex-1 grid-rows-2 lg:grid-cols-[minmax(20rem,2fr)_3fr] lg:grid-rows-1">
        <ChatPanel
          messages={shopper.messages}
          thinking={shopper.thinking}
          ready={shopper.ready}
          onSend={shopper.send}
          onVoiceStart={speech.cancel}
          onRegisterResumeVoice={(fn) => { resumeVoiceRef.current = fn; }}
        />
        <section aria-label="Products" className="overflow-y-auto p-4"><ProductPanel shopper={shopper} /></section>
      </main>
      <CartDrawer open={shopper.cartOpen} cart={shopper.cart} onClose={() => shopper.setCartOpen(false)}
        onRemove={shopper.removeFromCart} onPlaceOrder={shopper.placeOrder} />
      <ProfileDrawer open={shopper.profileOpen} profile={shopper.profile} onClose={() => shopper.setProfileOpen(false)}
        onPhoto={shopper.startPhotoFlow} onForget={shopper.forgetProfile} />
    </>
  );
}
