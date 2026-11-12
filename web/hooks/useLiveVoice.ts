"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Ids } from "@/lib/api";
import type { StyleDNA, UIAction } from "@/lib/types";

interface LiveVoiceOptions {
  ids: Ids | null;
  styleDna?: StyleDNA | null;
  onInputTranscript?: (text: string) => void;
  onOutputTranscript?: (text: string) => void;
  onUiAction?: (ui: UIAction, dna?: StyleDNA) => void;
  onError?: (message: string) => void;
}

function getWsBase(): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  if (explicit) return explicit.replace(/\/$/, "");
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (backend) return backend.replace(/^http/, "ws").replace(/\/$/, "");
  if (typeof window === "undefined") return "ws://127.0.0.1:8000";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.hostname}:8000`;
}

function downsampleTo16k(input: Float32Array, inputSampleRate: number): ArrayBuffer {
  const targetRate = 16000;
  const ratio = inputSampleRate / targetRate;
  const outLength = Math.floor(input.length / ratio);
  const buffer = new ArrayBuffer(outLength * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < outLength; i++) {
    const idx = Math.min(input.length - 1, Math.floor(i * ratio));
    const s = Math.max(-1, Math.min(1, input[idx]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

/** Real-time full-duplex Gemini Live voice hook over WebSocket with auth token, mic-denial handling, and auto-reconnect. */
export function useLiveVoice({
  ids,
  onInputTranscript,
  onOutputTranscript,
  onUiAction,
  onError,
}: LiveVoiceOptions) {
  const [supported, setSupported] = useState(false);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [status, setStatus] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const captureCtxRef = useRef<AudioContext | null>(null);
  const playCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const nextPlayTimeRef = useRef(0);
  const activeSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const manualStopRef = useRef(false);
  const retriesRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startRef = useRef<() => Promise<void>>(async () => {});

  const cbRef = useRef({ onInputTranscript, onOutputTranscript, onUiAction, onError });
  useEffect(() => {
    cbRef.current = { onInputTranscript, onOutputTranscript, onUiAction, onError };
  }, [onInputTranscript, onOutputTranscript, onUiAction, onError]);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "AudioContext" in window && Boolean(navigator.mediaDevices?.getUserMedia));
  }, []);

  const clearAudioQueue = useCallback(() => {
    for (const src of activeSourcesRef.current) {
      try { src.stop(); } catch { /* already stopped */ }
    }
    activeSourcesRef.current = [];
    if (playCtxRef.current) {
      nextPlayTimeRef.current = playCtxRef.current.currentTime;
    }
  }, []);

  const cleanupMedia = useCallback(() => {
    clearAudioQueue();
    try { processorRef.current?.disconnect(); } catch { /* ignore */ }
    processorRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void captureCtxRef.current?.close().catch(() => undefined);
    captureCtxRef.current = null;
    void playCtxRef.current?.close().catch(() => undefined);
    playCtxRef.current = null;
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
      wsRef.current.close();
    }
    wsRef.current = null;
  }, [clearAudioQueue]);

  const stop = useCallback(() => {
    manualStopRef.current = true;
    retriesRef.current = 0;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    cleanupMedia();
    setConnected(false);
    setConnecting(false);
    setStatus("");
  }, [cleanupMedia]);

  const playPcm24k = useCallback((raw: ArrayBuffer) => {
    const ctx = playCtxRef.current;
    if (!ctx) return;
    if (ctx.state === "suspended") void ctx.resume();
    const view = new DataView(raw);
    const samples = raw.byteLength / 2;
    if (samples <= 0) return;
    const audioBuffer = ctx.createBuffer(1, samples, 24000);
    const channel = audioBuffer.getChannelData(0);
    for (let i = 0; i < samples; i++) {
      channel[i] = view.getInt16(i * 2, true) / 32768;
    }
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    const startAt = Math.max(ctx.currentTime + 0.02, nextPlayTimeRef.current);
    source.start(startAt);
    nextPlayTimeRef.current = startAt + audioBuffer.duration;
    activeSourcesRef.current.push(source);
    source.onended = () => {
      activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== source);
    };
  }, []);

  useEffect(() => () => stop(), [stop]);

  const start = useCallback(async () => {
    if (!ids || connecting || connected) return;
    manualStopRef.current = false;
    setConnecting(true);
    setStatus("Connecting Gemini Live…");
    try {
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = micStream;
      const captureCtx = new AudioContext();
      captureCtxRef.current = captureCtx;
      const playCtx = new AudioContext({ sampleRate: 24000 });
      playCtxRef.current = playCtx;
      nextPlayTimeRef.current = playCtx.currentTime;

      const tokenQuery = ids.token ? `?token=${encodeURIComponent(ids.token)}` : "";
      const url = `${getWsBase()}/ws/live/${encodeURIComponent(ids.userId)}/${encodeURIComponent(ids.sessionId)}${tokenQuery}`;
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onopen = () => {
        retriesRef.current = 0;
        setConnecting(false);
        setConnected(true);
        setStatus("Gemini Live active — speak naturally anytime");
        const source = captureCtx.createMediaStreamSource(micStream);
        const proc = captureCtx.createScriptProcessor(4096, 1, 1);
        processorRef.current = proc;
        proc.onaudioprocess = (ev) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const pcm = downsampleTo16k(ev.inputBuffer.getChannelData(0), captureCtx.sampleRate);
          ws.send(pcm);
        };
        source.connect(proc);
        proc.connect(captureCtx.destination);
      };

      ws.onmessage = (ev) => {
        if (ev.data instanceof ArrayBuffer) {
          playPcm24k(ev.data);
          return;
        }
        try {
          const msg = JSON.parse(String(ev.data)) as Record<string, unknown>;
          if (msg.type === "interrupted") clearAudioQueue();
          else if (msg.type === "input_transcript" && msg.text) cbRef.current.onInputTranscript?.(String(msg.text));
          else if (msg.type === "output_transcript" && msg.text) cbRef.current.onOutputTranscript?.(String(msg.text));
          else if (msg.type === "ui" && msg.ui_action) {
            cbRef.current.onUiAction?.(msg.ui_action as UIAction, msg.style_dna as StyleDNA | undefined);
          } else if (msg.type === "error") {
            cbRef.current.onError?.(String(msg.message ?? "Live voice error."));
            stop();
          }
        } catch { /* ignore malformed frame */ }
      };

      ws.onerror = () => {
        cleanupMedia();
        setConnected(false);
        setConnecting(false);
      };

      ws.onclose = (ev) => {
        cleanupMedia();
        setConnected(false);
        setConnecting(false);
        if (!manualStopRef.current && ev.code !== 1000 && ev.code !== 1008 && retriesRef.current < 2) {
          retriesRef.current += 1;
          const delayMs = 900 * retriesRef.current;
          setStatus(`Reconnecting voice (${retriesRef.current}/2)…`);
          reconnectTimerRef.current = setTimeout(() => {
            void startRef.current();
          }, delayMs);
        } else if (!manualStopRef.current && ev.code !== 1000) {
          cbRef.current.onError?.("Live voice disconnected. Tap Live to reconnect or use standard Mic/Chat.");
          setStatus("");
        }
      };
    } catch (e) {
      const name = (e as DOMException)?.name ?? "";
      const friendly =
        name === "NotAllowedError" || name === "PermissionDeniedError"
          ? "Microphone permission was denied. Allow mic access in browser site settings to use voice."
          : name === "NotFoundError"
            ? "No microphone detected on this device."
            : e instanceof Error
              ? e.message
              : "Microphone access failed.";
      cbRef.current.onError?.(friendly);
      stop();
    }
  }, [ids, connecting, connected, playPcm24k, clearAudioQueue, cleanupMedia, stop]);

  useEffect(() => {
    startRef.current = start;
  }, [start]);

  const toggle = useCallback(() => {
    if (connected || connecting) stop();
    else void start();
  }, [connected, connecting, start, stop]);

  return { supported, connected, connecting, status, toggle, stop };
}
