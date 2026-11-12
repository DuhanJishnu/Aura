"use client";

import { useEffect } from "react";
import { CloseCrossButton } from "./ui";

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
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label="Close" className="absolute inset-0 cursor-default bg-black/65 backdrop-blur-xs" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-sm flex-col border-l border-white/12 bg-[#121513] text-stone-100 shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <strong className="text-base font-semibold tracking-tight">{title}</strong>
          <CloseCrossButton ariaLabel="Close drawer" onClick={onClose} />
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
        {footer && <div className="flex flex-col gap-2.5 border-t border-white/10 bg-[#0f1210] p-4">{footer}</div>}
      </aside>
    </div>
  );
}
