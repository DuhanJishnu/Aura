"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { speakable } from "@/lib/format";

const SPEAK_KEY = "shopper_speak";

interface SpeechOutputOptions {
  onEnd?: () => void;
}

/** Read replies aloud with the browser's speech synthesis (off by default, remembered). */
export function useSpeechOutput({ onEnd }: SpeechOutputOptions = {}) {
  const [supported, setSupported] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const enabledRef = useRef(false);
  const onEndRef = useRef(onEnd);

  useEffect(() => {
    onEndRef.current = onEnd;
  }, [onEnd]);

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
    if (!text) {
      onEndRef.current?.();
      return;
    }
    if (!enabledRef.current || !("speechSynthesis" in window)) {
      onEndRef.current?.();
      return;
    }
    const synth = window.speechSynthesis;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(speakable(text));
    utterance.lang = "en-IN";
    const voices = synth.getVoices();
    utterance.voice = voices.find((v) => v.lang === "en-IN") ?? voices.find((v) => v.lang.startsWith("en")) ?? null;

    utterance.onend = () => {
      onEndRef.current?.();
    };
    utterance.onerror = () => {
      onEndRef.current?.();
    };

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
  "no-speech": "I didn't hear anything. Speak when ready.",
  network: "Speech recognition needs an internet connection.",
  "audio-capture": "No microphone found.",
};

interface InputCallbacks {
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
  onStart?: () => void;
}

/** Hands-free speech recognition (Chrome/Edge/Safari).
 * When voiceMode is active, it stays listening across questions without needing to click mic repeatedly.
 */
export function useSpeechInput(callbacks: InputCallbacks) {
  const cb = useRef(callbacks);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const heard = useRef("");
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const voiceModeRef = useRef(false);
  const pausedRef = useRef(false);
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
      if (results[results.length - 1]?.isFinal) {
        heard.current = text;
      }
    };

    rec.onerror = (e) => {
      if (e.error !== "no-speech") {
        setStatus(SPEECH_ERRORS[e.error] ?? `Voice input stopped (${e.error}).`);
      }
    };

    rec.onend = () => {
      setListening(false);
      if (heard.current) {
        const text = heard.current;
        heard.current = "";
        pausedRef.current = true;
        setStatus("Thinking…");
        cb.current.onFinal(text);
      } else if (voiceModeRef.current && !pausedRef.current) {
        // Quiet pause: resume listening automatically in conversational mode
        setTimeout(() => {
          if (voiceModeRef.current && !pausedRef.current) {
            try { rec.start(); } catch { /* ignore */ }
          }
        }, 200);
      }
    };

    recognition.current = rec;
    setSupported(true);
    return () => {
      rec.onend = null;
      try { rec.stop(); } catch { /* not started */ }
    };
  }, []);

  const resumeListening = useCallback(() => {
    pausedRef.current = false;
    if (voiceModeRef.current) {
      setStatus("Listening… speak now.");
      setTimeout(() => {
        if (voiceModeRef.current && !pausedRef.current) {
          try { recognition.current?.start(); } catch { /* ignore */ }
        }
      }, 150);
    }
  }, []);

  const stop = useCallback(() => {
    voiceModeRef.current = false;
    pausedRef.current = false;
    setVoiceMode(false);
    setStatus("");
    try { recognition.current?.stop(); } catch { /* ignore */ }
  }, []);

  const toggle = useCallback(() => {
    const rec = recognition.current;
    if (!rec) return;
    if (voiceModeRef.current) {
      stop();
    } else {
      voiceModeRef.current = true;
      pausedRef.current = false;
      setVoiceMode(true);
      try { rec.start(); } catch { /* ignore */ }
    }
  }, [stop]);

  return { supported, listening, voiceMode, status, toggle, stop, resumeListening };
}
