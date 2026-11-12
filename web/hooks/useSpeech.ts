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
  "service-not-allowed": "Browser speech recognition isn't available here.",
  "no-speech": "I didn't hear anything. Tap mic to try again.",
  network: "Browser speech service is offline here.",
  "audio-capture": "No microphone found on this device.",
  aborted: "Voice input stopped.",
};

interface InputCallbacks {
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
  onStart?: () => void;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("Could not read audio"));
    reader.readAsDataURL(blob);
  });
}

/** Hands-free speech recognition with clean error handling and MediaRecorder + Gemini transcription fallback. */
export function useSpeechInput(callbacks: InputCallbacks) {
  const cb = useRef(callbacks);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const heard = useRef("");
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const voiceModeRef = useRef(false);
  const pausedRef = useRef(false);
  const fatalErrorRef = useRef(false);
  const silentRetriesRef = useRef(0);
  const speechBrokenRef = useRef(false);
  const [status, setStatus] = useState("");

  // MediaRecorder fallback refs (when Chromium blocks Web Speech API)
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    cb.current = callbacks;
  });

  const canRecord = useCallback(
    () =>
      typeof window !== "undefined" &&
      typeof MediaRecorder !== "undefined" &&
      Boolean(navigator.mediaDevices?.getUserMedia),
    [],
  );

  const cleanupRecorder = useCallback(() => {
    try {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
    } catch { /* ignore */ }
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startRecorder = useCallback(async () => {
    if (!canRecord()) {
      setStatus("Microphone recording is not supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
      const mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      recorderRef.current = mr;

      mr.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };

      mr.onstop = async () => {
        const usedMime = mr.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: usedMime });
        chunksRef.current = [];
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        recorderRef.current = null;
        setListening(false);
        setVoiceMode(false);
        voiceModeRef.current = false;

        if (blob.size < 400) {
          setStatus("Didn't catch any audio. Tap mic to try again.");
          return;
        }
        setStatus("Transcribing…");
        try {
          const b64 = await blobToBase64(blob);
          const res = await fetch("/api/voice/transcribe", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ audio_base64: b64, mime_type: usedMime }),
          });
          if (!res.ok) throw new Error("Transcribe failed");
          const data = (await res.json()) as { text?: string };
          const text = (data.text ?? "").trim();
          if (text) {
            setStatus("");
            cb.current.onFinal(text);
          } else {
            setStatus("I didn't hear anything clearly. Try again!");
          }
        } catch {
          setStatus("Couldn't transcribe voice note right now.");
        }
      };

      mr.start();
      voiceModeRef.current = true;
      setVoiceMode(true);
      setListening(true);
      setStatus("Recording… tap mic to send.");
      cb.current.onStart?.();
    } catch (e) {
      cleanupRecorder();
      voiceModeRef.current = false;
      setVoiceMode(false);
      setListening(false);
      const name = e instanceof DOMException ? e.name : "";
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setStatus("Microphone permission is blocked for this site.");
      } else if (name === "NotFoundError") {
        setStatus("No microphone found on this device.");
      } else {
        setStatus("Couldn't access microphone.");
      }
    }
  }, [canRecord, cleanupRecorder]);

  useEffect(() => {
    const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Ctor) {
      if (canRecord()) setSupported(true);
      return;
    }
    const rec = new Ctor();
    rec.lang = "en-IN";
    rec.interimResults = true;
    rec.continuous = false;

    rec.onstart = () => {
      heard.current = "";
      fatalErrorRef.current = false;
      setListening(true);
      setStatus("Listening… speak now.");
      cb.current.onStart?.();
    };

    rec.onresult = (e) => {
      silentRetriesRef.current = 0;
      const results = Array.from(e.results);
      const text = results.map((r) => r[0].transcript).join(" ").trim();
      cb.current.onInterim(text);
      if (results[results.length - 1]?.isFinal) {
        heard.current = text;
      }
    };

    rec.onerror = (e) => {
      if (e.error === "no-speech") {
        silentRetriesRef.current += 1;
        if (silentRetriesRef.current > 1) {
          fatalErrorRef.current = true;
          voiceModeRef.current = false;
          setVoiceMode(false);
          setStatus(SPEECH_ERRORS["no-speech"]);
        }
        return;
      }

      fatalErrorRef.current = true;
      voiceModeRef.current = false;
      setVoiceMode(false);
      setListening(false);

      // Chromium without Chrome speech keys often fails with "network" or "service-not-allowed":
      // seamlessly fall back to MediaRecorder + Gemini transcription instead of looping!
      if ((e.error === "network" || e.error === "service-not-allowed") && canRecord()) {
        speechBrokenRef.current = true;
        void startRecorder();
        return;
      }
      setStatus(SPEECH_ERRORS[e.error] ?? `Voice input stopped (${e.error}).`);
    };

    rec.onend = () => {
      setListening(false);
      if (heard.current) {
        const text = heard.current;
        heard.current = "";
        pausedRef.current = true;
        setStatus("Thinking…");
        cb.current.onFinal(text);
      } else if (voiceModeRef.current && !pausedRef.current && !fatalErrorRef.current) {
        setTimeout(() => {
          if (voiceModeRef.current && !pausedRef.current && !fatalErrorRef.current) {
            try {
              rec.start();
            } catch {
              voiceModeRef.current = false;
              setVoiceMode(false);
            }
          }
        }, 200);
      }
    };

    recognition.current = rec;
    setSupported(true);
    return () => {
      fatalErrorRef.current = true;
      rec.onend = null;
      try { rec.stop(); } catch { /* not started */ }
      cleanupRecorder();
    };
  }, [canRecord, cleanupRecorder, startRecorder]);

  const resumeListening = useCallback(() => {
    pausedRef.current = false;
    if (voiceModeRef.current && !fatalErrorRef.current && !speechBrokenRef.current) {
      setStatus("Listening… speak now.");
      setTimeout(() => {
        if (voiceModeRef.current && !pausedRef.current && !fatalErrorRef.current) {
          try {
            recognition.current?.start();
          } catch {
            voiceModeRef.current = false;
            setVoiceMode(false);
          }
        }
      }, 150);
    }
  }, []);

  const stop = useCallback(() => {
    voiceModeRef.current = false;
    pausedRef.current = false;
    fatalErrorRef.current = true;
    setVoiceMode(false);
    setListening(false);
    setStatus("");
    try { recognition.current?.stop(); } catch { /* ignore */ }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      try { recorderRef.current.stop(); } catch { /* ignore */ }
    }
  }, []);

  const toggle = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state === "recording") {
      try { recorderRef.current.stop(); } catch { cleanupRecorder(); }
      return;
    }
    if (speechBrokenRef.current || !recognition.current) {
      void startRecorder();
      return;
    }
    const rec = recognition.current;
    if (voiceModeRef.current || listening) {
      stop();
    } else {
      fatalErrorRef.current = false;
      silentRetriesRef.current = 0;
      voiceModeRef.current = true;
      pausedRef.current = false;
      setVoiceMode(true);
      try {
        rec.start();
      } catch {
        voiceModeRef.current = false;
        setVoiceMode(false);
        setStatus("Couldn't start voice input.");
      }
    }
  }, [cleanupRecorder, listening, startRecorder, stop]);

  return { supported, listening, voiceMode, status, toggle, stop, resumeListening };
}
