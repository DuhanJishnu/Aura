import type { ButtonHTMLAttributes } from "react";
import { X } from "lucide-react";

const base = "rounded-lg px-4 py-2 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:cursor-not-allowed disabled:opacity-50";

export function Button({ variant = "primary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" }) {
  const look = variant === "primary"
    ? "bg-brand-600 text-white hover:bg-brand-700 dark:bg-brand-400 dark:text-neutral-950 dark:hover:bg-brand-500"
    : "border border-stone-300 bg-transparent hover:border-brand-600 dark:border-neutral-700 dark:hover:border-brand-400";
  return <button type="button" className={`${base} ${look} ${className}`} {...props} />;
}

/** Consistent top-right red cross button for dismissing modals, sheets, and drawers. */
export function CloseCrossButton({
  onClick,
  ariaLabel = "Close",
  className = "",
}: {
  onClick: () => void;
  ariaLabel?: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      title={ariaLabel}
      onClick={onClick}
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-rose-500/45 bg-rose-950/75 text-rose-400 transition hover:border-rose-400/75 hover:bg-rose-900/80 hover:text-rose-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-400 ${className}`}
    >
      <X className="h-4 w-4 stroke-[2.5]" />
    </button>
  );
}

export const Meta = ({ children }: { children: React.ReactNode }) => (
  <div className="text-sm text-stone-500 dark:text-stone-400">{children}</div>
);
