"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { speakable } from "@/lib/format";

const SPEAK_KEY = "shopper_speak";

/** Read replies aloud with the browser's speech synthesis (off by default, remembered). */
export function useSpeechOutput() {
  const [supported, setSupported] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const enabledRef = useRef(false);

  useEffect(() => {
    setSupported("speechSynthesis" in window);
    try {
      const on = localStorage.getItem(SPEAK_KEY) === "1";
      setEnabled(on);
      enabledRef.current = on;
    } catch { /* storage blocked */ }
  }, []);

  const cancel = useCallback(() => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  const speak = useCallback((text: string) => {
    if (!enabledRef.current || !text || !("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(speakable(text));
    utterance.lang = "en-IN";
    const voices = synth.getVoices();
    utterance.voice = voices.find((v) => v.lang === "en-IN") ?? voices.find((v) => v.lang.startsWith("en")) ?? null;
    synth.speak(utterance);
  }, []);

  const toggle = useCallback(() => {
    const next = !enabledRef.current;
    enabledRef.current = next;
    setEnabled(next);
    try { localStorage.setItem(SPEAK_KEY, next ? "1" : "0"); } catch { /* storage blocked */ }
    if (!next) cancel();
  }, [cancel]);

  return { supported, enabled, speak, cancel, toggle };
}

const SPEECH_ERRORS: Record<string, string> = {
  "not-allowed": "Microphone permission is blocked for this site.",
  "service-not-allowed": "Speech recognition is not allowed here.",
  "no-speech": "I didn't hear anything. Tap Mic and try again.",
  network: "Speech recognition needs an internet connection.",
  "audio-capture": "No microphone found.",
};

interface InputCallbacks {
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
  onStart?: () => void;
}

/** Speak a message with the browser's speech recognition (Chrome/Edge/Safari; absent in some browsers). */
export function useSpeechInput(callbacks: InputCallbacks) {
  const cb = useRef(callbacks);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const heard = useRef("");
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => { cb.current = callbacks; });

  useEffect(() => {
    const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = "en-IN";
    rec.interimResults = true;
    rec.continuous = false;
    rec.onstart = () => {
      heard.current = "";
      setListening(true);
      setStatus("Listening… speak now.");
      cb.current.onStart?.();
    };
    rec.onresult = (e) => {
      const results = Array.from(e.results);
      const text = results.map((r) => r[0].transcript).join(" ").trim();
      cb.current.onInterim(text);
      if (results[results.length - 1]?.isFinal) heard.current = text;
    };
    rec.onerror = (e) => setStatus(SPEECH_ERRORS[e.error] ?? `Voice input stopped (${e.error}).`);
    rec.onend = () => {
      setListening(false);
      if (heard.current) {
        const text = heard.current;
        heard.current = "";
        setStatus("");
        cb.current.onFinal(text);
      }
    };
    recognition.current = rec;
    setSupported(true);
    return () => {
      rec.onend = null;
      try { rec.stop(); } catch { /* not started */ }
    };
  }, []);

  const toggle = useCallback(() => {
    const rec = recognition.current;
    if (!rec) return;
    try {
      if (listening) rec.stop();
      else rec.start();
    } catch { /* already started */ }
  }, [listening]);

  return { supported, listening, status, toggle };
}
