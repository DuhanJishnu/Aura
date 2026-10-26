import type { ButtonHTMLAttributes } from "react";

const base = "rounded-lg px-4 py-2 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:cursor-not-allowed disabled:opacity-50";

export function Button({ variant = "primary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" }) {
  const look = variant === "primary"
    ? "bg-brand-600 text-white hover:bg-brand-700 dark:bg-brand-400 dark:text-neutral-950 dark:hover:bg-brand-500"
    : "border border-stone-300 bg-transparent hover:border-brand-600 dark:border-neutral-700 dark:hover:border-brand-400";
  return <button type="button" className={`${base} ${look} ${className}`} {...props} />;
}

export const Meta = ({ children }: { children: React.ReactNode }) => (
  <div className="text-sm text-stone-500 dark:text-stone-400">{children}</div>
);
