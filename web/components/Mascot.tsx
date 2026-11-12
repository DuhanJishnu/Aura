"use client";

import { motion } from "framer-motion";

export type MascotState = "idle" | "listening" | "thinking" | "happy" | "sad";

export default function Mascot({
  state = "idle",
  compact = false,
  onClick,
  className = "",
}: {
  state?: MascotState;
  compact?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  const size = compact ? "h-12 w-12" : "h-36 w-36 sm:h-44 sm:w-44";
  const ringScale =
    state === "listening"
      ? [1, 1.24, 1]
      : state === "thinking"
        ? [1, 1.14, 1]
        : state === "happy"
          ? [1, 1.18, 1]
          : [1, 1.07, 1];

  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label="Aura stylist mascot — tap to ask what we are getting ready for"
      whileHover={onClick ? { scale: 1.05 } : undefined}
      whileTap={onClick ? { scale: 0.94 } : undefined}
      className={`group relative flex items-center justify-center rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6ba58a] ${size} ${className}`}
    >
      {/* Ambient Emerald Aura Halo */}
      <motion.span
        aria-hidden="true"
        animate={{ scale: ringScale, opacity: state === "listening" ? [0.45, 0.85, 0.45] : [0.3, 0.55, 0.3] }}
        transition={{ duration: state === "listening" ? 1.2 : 3.2, repeat: Infinity, ease: "easeInOut" }}
        className="pointer-events-none absolute inset-[-18%] rounded-full bg-[radial-gradient(circle,#6ba58a66_0%,#2f7a6222_55%,transparent_75%)] blur-md"
      />

      {/* Orbiting sparkle ring while Aura searches / styles */}
      {state === "thinking" && (
        <motion.span
          aria-hidden="true"
          animate={{ rotate: 360 }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "linear" }}
          className="pointer-events-none absolute inset-[-8%] rounded-full border border-dashed border-[#6ba58a]/70"
        >
          <span className="absolute -top-1 left-1/2 h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-[#6ba58a] shadow-[0_0_12px_#6ba58a]" />
        </motion.span>
      )}

      {/* Main 3D-shaded Studio Character Sphere */}
      <motion.div
        animate={
          state === "happy"
            ? { y: [0, -10, 0], rotate: [0, -4, 4, 0] }
            : state === "listening"
              ? { y: [0, -4, 0], scale: [1, 1.04, 1] }
              : state === "thinking"
                ? { y: [0, -5, 0], rotate: [-2, 2, -2] }
                : { y: [0, -6, 0] }
        }
        transition={{ duration: state === "happy" ? 0.65 : 3.4, repeat: state === "happy" ? 1 : Infinity, ease: "easeInOut" }}
        className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-full border border-[#6ba58a]/40 shadow-[inset_-10px_-14px_26px_rgba(8,22,16,0.85),inset_8px_8px_20px_rgba(170,235,205,0.28),0_18px_45px_rgba(0,0,0,0.65)]"
        style={{
          background:
            "radial-gradient(circle at 32% 28%, #8fd1b2 0%, #3d8367 42%, #152b22 82%, #0a1410 100%)",
        }}
      >
        {/* Specular studio highlight */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute top-[12%] left-[20%] h-[22%] w-[36%] -rotate-12 rounded-full bg-white/30 blur-[2px]"
        />

        {/* Expressive Eyes + Mouth */}
        <svg viewBox="0 0 120 120" className="h-[74%] w-[74%]" aria-hidden="true">
          {/* Both eyes dart curiously side to side while searching */}
          <motion.g
            animate={
              state === "thinking"
                ? { x: [0, -7, -7, 7, 7, 0], y: [0, -2, -2, -1.5, -1.5, 0] }
                : { x: 0, y: 0 }
            }
            transition={
              state === "thinking"
                ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" }
                : { duration: 0.25 }
            }
          >
            {/* Left eye */}
            <motion.ellipse
              cx="41"
              cy="52"
              rx="6"
              ry={state === "happy" ? 3 : 8}
              fill="#0a1611"
              animate={state === "idle" ? { scaleY: [1, 1, 0.12, 1, 1] } : { scaleY: 1 }}
              transition={{ duration: 4.5, repeat: state === "idle" ? Infinity : 0, times: [0, 0.88, 0.92, 0.96, 1] }}
              style={{ transformOrigin: "41px 52px" }}
            />
            <motion.circle
              cx="43"
              cy="49"
              r="2.2"
              fill="#e9fff5"
              opacity="0.9"
              animate={state === "thinking" ? { cx: [43, 39.5, 39.5, 45.5, 45.5, 43] } : { cx: 43 }}
              transition={state === "thinking" ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }}
            />

            {/* Right eye */}
            <motion.ellipse
              cx="79"
              cy="52"
              rx="6"
              ry={state === "happy" ? 3 : 8}
              fill="#0a1611"
              animate={state === "idle" ? { scaleY: [1, 1, 0.12, 1, 1] } : { scaleY: 1 }}
              transition={{ duration: 4.5, repeat: state === "idle" ? Infinity : 0, times: [0, 0.88, 0.92, 0.96, 1] }}
              style={{ transformOrigin: "79px 52px" }}
            />
            <motion.circle
              cx="81"
              cy="49"
              r="2.2"
              fill="#e9fff5"
              opacity="0.9"
              animate={state === "thinking" ? { cx: [81, 77.5, 77.5, 83.5, 83.5, 81] } : { cx: 81 }}
              transition={state === "thinking" ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }}
            />
          </motion.g>

          {/* Soft blush */}
          <ellipse cx="30" cy="64" rx="6" ry="3" fill="#ff9e8a" opacity="0.32" />
          <ellipse cx="90" cy="64" rx="6" ry="3" fill="#ff9e8a" opacity="0.32" />

          {/* Mouth expression */}
          {state === "listening" ? (
            <ellipse cx="60" cy="70" rx="6" ry="7" fill="#0a1611" />
          ) : state === "thinking" ? (
            <path d="M51 71 Q60 68 69 71" stroke="#0a1611" strokeWidth="4" strokeLinecap="round" fill="none" />
          ) : state === "sad" ? (
            <path d="M50 74 Q60 66 70 74" stroke="#0a1611" strokeWidth="4" strokeLinecap="round" fill="none" />
          ) : (
            <path
              d={state === "happy" ? "M46 66 Q60 81 74 66" : "M48 67 Q60 76 72 67"}
              stroke="#0a1611"
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
