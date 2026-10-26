"use client";

import { useEffect } from "react";

export default function Drawer({ open, title, onClose, children, footer }: {
  open: boolean; title: string; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-20 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label="Close" className="absolute inset-0 cursor-default bg-black/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-sm flex-col border-l border-stone-200 bg-white shadow-xl dark:border-neutral-800 dark:bg-neutral-900">
        <div className="flex items-center justify-between border-b border-stone-200 p-4 dark:border-neutral-800">
          <strong>{title}</strong>
          <button type="button" onClick={onClose} className="rounded-lg border border-stone-200 px-3 py-1 text-sm hover:border-brand-600 dark:border-neutral-700">Close</button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
        {footer && <div className="flex flex-col gap-2 border-t border-stone-200 p-4 dark:border-neutral-800">{footer}</div>}
      </aside>
    </div>
  );
}
