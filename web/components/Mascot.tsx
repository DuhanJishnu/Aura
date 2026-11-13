"use client";

import { motion } from "framer-motion";

export type MascotState = "idle" | "listening" | "thinking" | "speaking" | "happy" | "sad";

export default function Mascot({
  state = "idle",
  live = false,
  compact = false,
  onClick,
  className = "",
}: {
  state?: MascotState;
  live?: boolean;
  compact?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  const size = compact ? "h-12 w-12" : "h-36 w-36 sm:h-44 sm:w-44";
  const ringScale =
    state === "listening"
      ? [1, 1.25, 1]
      : state === "speaking"
        ? [1, 1.18, 1]
        : state === "thinking"
          ? [1, 1.14, 1]
          : state === "happy"
            ? [1, 1.18, 1]
            : [1, 1.07, 1];

  const haloGradient = live
    ? "bg-[radial-gradient(circle,#38bdf888_0%,#0284c733_55%,transparent_75%)]"
    : "bg-[radial-gradient(circle,#6ba58a66_0%,#2f7a6222_55%,transparent_75%)]";

  const sphereBg = live
    ? "radial-gradient(circle at 32% 28%, #7dd3fc 0%, #0ea5e9 38%, #0369a1 70%, #082f49 90%, #031726 100%)"
    : "radial-gradient(circle at 32% 28%, #8fd1b2 0%, #3d8367 42%, #152b22 82%, #0a1410 100%)";

  const sphereBorder = live ? "border-[#38bdf8]/50" : "border-[#6ba58a]/40";
  const sphereShadow = live
    ? "shadow-[inset_-10px_-14px_26px_rgba(2,26,43,0.9),inset_8px_8px_22px_rgba(186,230,253,0.38),0_18px_45px_rgba(0,0,0,0.65)]"
    : "shadow-[inset_-10px_-14px_26px_rgba(8,22,16,0.85),inset_8px_8px_20px_rgba(170,235,205,0.28),0_18px_45px_rgba(0,0,0,0.65)]";

  const sparkleBorder = live ? "border-[#38bdf8]/70" : "border-[#6ba58a]/70";
  const sparkleDot = live
    ? "bg-[#38bdf8] shadow-[0_0_14px_#38bdf8]"
    : "bg-[#6ba58a] shadow-[0_0_12px_#6ba58a]";

  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label={`Aura stylist mascot — ${live ? "Live voice active" : "tap to ask what we are getting ready for"}`}
      whileHover={onClick ? { scale: 1.05 } : undefined}
      whileTap={onClick ? { scale: 0.94 } : undefined}
      className={`group relative flex items-center justify-center rounded-full focus:outline-none focus-visible:ring-2 ${
        live ? "focus-visible:ring-[#38bdf8]" : "focus-visible:ring-[#6ba58a]"
      } ${size} ${className}`}
    >
      {/* Ambient Aura Halo (Cyan glow when Live, Emerald when Normal) */}
      <motion.span
        aria-hidden="true"
        animate={{
          scale: ringScale,
          opacity: state === "listening" || state === "speaking" ? [0.55, 0.95, 0.55] : [0.3, 0.55, 0.3],
        }}
        transition={{
          duration: state === "speaking" ? 0.7 : state === "listening" ? 1.2 : 3.2,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className={`pointer-events-none absolute inset-[-18%] rounded-full blur-md ${haloGradient}`}
      />

      {/* Orbiting sparkle ring while Aura searches / thinks */}
      {state === "thinking" && (
        <motion.span
          aria-hidden="true"
          animate={{ rotate: 360 }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "linear" }}
          className={`pointer-events-none absolute inset-[-8%] rounded-full border border-dashed ${sparkleBorder}`}
        >
          <span className={`absolute -top-1 left-1/2 h-2.5 w-2.5 -translate-x-1/2 rounded-full ${sparkleDot}`} />
        </motion.span>
      )}

      {/* Main 3D-shaded Studio Character Sphere */}
      <motion.div
        animate={
          state === "speaking"
            ? { y: [0, -4, 0], scale: [1, 1.02, 1] }
            : state === "happy"
              ? { y: [0, -10, 0], rotate: [0, -4, 4, 0] }
              : state === "listening"
                ? { y: [0, -4, 0], scale: [1, 1.04, 1] }
                : state === "thinking"
                  ? { y: [0, -5, 0], rotate: [-2, 2, -2] }
                  : { y: [0, -6, 0] }
        }
        transition={{
          duration: state === "speaking" ? 0.36 : state === "happy" ? 0.65 : 3.4,
          repeat: state === "happy" ? 1 : Infinity,
          ease: "easeInOut",
        }}
        className={`relative flex h-full w-full items-center justify-center overflow-hidden rounded-full border ${sphereBorder} ${sphereShadow}`}
        style={{ background: sphereBg }}
      >
        {/* Specular studio highlight */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute top-[12%] left-[20%] h-[22%] w-[36%] -rotate-12 rounded-full bg-white/35 blur-[2px]"
        />

        {/* Expressive Eyes + Mouth */}
        <svg viewBox="0 0 120 120" className="h-[74%] w-[74%]" aria-hidden="true">
          {/* Eyes grouping with state-dependent glance / motion */}
          <motion.g
            animate={
              state === "thinking"
                ? { x: [0, -7, -7, 7, 7, 0], y: [0, -2, -2, -1.5, -1.5, 0] }
                : state === "speaking"
                  ? { y: [0, -1.2, 0, -0.8, 0] }
                  : { x: 0, y: 0 }
            }
            transition={
              state === "thinking"
                ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" }
                : state === "speaking"
                  ? { duration: 0.42, repeat: Infinity, ease: "easeInOut" }
                  : { duration: 0.25 }
            }
          >
            {/* Left eye */}
            <motion.ellipse
              cx="41"
              cy="52"
              rx="6"
              ry={state === "happy" ? 3 : state === "listening" ? 8.5 : 8}
              fill="#06120d"
              animate={
                state === "idle"
                  ? { scaleY: [1, 1, 0.12, 1, 1] }
                  : state === "speaking"
                    ? { scaleY: [1, 0.88, 1, 0.92, 1] }
                    : { scaleY: 1 }
              }
              transition={{
                duration: state === "speaking" ? 0.6 : 4.5,
                repeat: Infinity,
                times: state === "idle" ? [0, 0.88, 0.92, 0.96, 1] : undefined,
              }}
              style={{ transformOrigin: "41px 52px" }}
            />
            <motion.circle
              cx="43"
              cy="49"
              r="2.2"
              fill={live ? "#e0f2fe" : "#e9fff5"}
              opacity="0.95"
              animate={state === "thinking" ? { cx: [43, 39.5, 39.5, 45.5, 45.5, 43] } : { cx: 43 }}
              transition={state === "thinking" ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }}
            />

            {/* Right eye */}
            <motion.ellipse
              cx="79"
              cy="52"
              rx="6"
              ry={state === "happy" ? 3 : state === "listening" ? 8.5 : 8}
              fill="#06120d"
              animate={
                state === "idle"
                  ? { scaleY: [1, 1, 0.12, 1, 1] }
                  : state === "speaking"
                    ? { scaleY: [1, 0.88, 1, 0.92, 1] }
                    : { scaleY: 1 }
              }
              transition={{
                duration: state === "speaking" ? 0.6 : 4.5,
                repeat: Infinity,
                times: state === "idle" ? [0, 0.88, 0.92, 0.96, 1] : undefined,
              }}
              style={{ transformOrigin: "79px 52px" }}
            />
            <motion.circle
              cx="81"
              cy="49"
              r="2.2"
              fill={live ? "#e0f2fe" : "#e9fff5"}
              opacity="0.95"
              animate={state === "thinking" ? { cx: [81, 77.5, 77.5, 83.5, 83.5, 81] } : { cx: 81 }}
              transition={state === "thinking" ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }}
            />
          </motion.g>

          {/* Soft blush cheeks */}
          <ellipse
            cx="30"
            cy="64"
            rx="6"
            ry="3"
            fill={live ? "#38bdf8" : "#ff9e8a"}
            opacity={live ? "0.28" : "0.32"}
          />
          <ellipse
            cx="90"
            cy="64"
            rx="6"
            ry="3"
            fill={live ? "#38bdf8" : "#ff9e8a"}
            opacity={live ? "0.28" : "0.32"}
          />

          {/* Mouth expression */}
          {state === "speaking" ? (
            <motion.g>
              <motion.path
                animate={{
                  d: [
                    "M48 67 Q60 70 72 67 Q60 72 48 67",
                    "M47 67 Q60 70 73 67 Q60 84 47 67",
                    "M48 68 Q60 71 72 68 Q60 76 48 68",
                    "M47 66 Q60 69 73 66 Q60 88 47 66",
                    "M48 67 Q60 70 72 67 Q60 72 48 67",
                  ],
                }}
                transition={{ duration: 0.42, repeat: Infinity, ease: "easeInOut" }}
                fill={live ? "#082f49" : "#0c2018"}
                stroke="#06120d"
                strokeWidth="2.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <motion.ellipse
                cx="60"
                cy="75"
                rx="4.5"
                ry="3"
                fill={live ? "#38bdf8" : "#f472b6"}
                opacity="0.85"
                animate={{ scaleY: [0.6, 1.15, 0.7, 1.2, 0.6] }}
                transition={{ duration: 0.42, repeat: Infinity, ease: "easeInOut" }}
              />
            </motion.g>
          ) : state === "listening" ? (
            <ellipse cx="60" cy="70" rx="5.5" ry="6.5" fill="#06120d" />
          ) : state === "thinking" ? (
            <path d="M51 71 Q60 68 69 71" stroke="#06120d" strokeWidth="4" strokeLinecap="round" fill="none" />
          ) : state === "sad" ? (
            <path d="M50 74 Q60 66 70 74" stroke="#06120d" strokeWidth="4" strokeLinecap="round" fill="none" />
          ) : (
            <path
              d={state === "happy" ? "M46 66 Q60 81 74 66" : "M48 67 Q60 76 72 67"}
              stroke="#06120d"
              strokeWidth="4.2"
              strokeLinecap="round"
              fill="none"
            />
          )}
        </svg>
      </motion.div>
    </motion.button>
  );
}
