"use client";

import { useState } from "react";
import { contrastText } from "@/lib/format";
import type { FashionItem } from "@/lib/types";

export default function Thumb({ item, className = "h-32" }: { item: FashionItem; className?: string }) {
  const [brokenUrl, setBrokenUrl] = useState<string | null>(null);
  const bg = item.color_hex || "#6E655F";
  const fg = contrastText(bg);
  const showImage = Boolean(item.image_url && brokenUrl !== item.image_url);

  if (showImage) {
    return (
      <div className={`relative overflow-hidden bg-stone-100 dark:bg-neutral-800 ${className}`}>
        {/* Plain <img> supports dynamic retailer og:image URLs and /api/media images without domain allowlisting. */}
        <img
          src={item.image_url}
          alt={item.name}
          loading="lazy"
          onError={() => setBrokenUrl(item.image_url ?? null)}
          className="h-full w-full object-cover"
        />
        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between bg-gradient-to-b from-black/55 to-transparent px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-white">
          <span>{item.category}</span>
          <span>{Math.round(item.match_score)}% match</span>
        </div>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/55 to-transparent px-3 py-1.5 text-[11px] text-white/90">
          <span className="font-semibold uppercase tracking-wider">{item.brand}</span>
          {item.image_source === "ai_generated" ? (
            <span className="rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-medium text-amber-200">
              AI visualization
            </span>
          ) : (
            <span>{item.source_domain || "web"}</span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`relative flex flex-col justify-between overflow-hidden p-3.5 ${className}`}
      style={{
        background: `linear-gradient(145deg, ${bg} 0%, ${bg}dd 65%, #1c191722 100%)`,
        color: fg,
      }}
      aria-hidden="true"
    >
      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.14em] opacity-85">
        <span>{item.category}</span>
        <span>{Math.round(item.match_score)}% match</span>
      </div>
      <div className="text-center text-sm font-bold tracking-[0.18em] uppercase opacity-95">
        {item.brand}
      </div>
      <div className="flex items-center justify-between text-[11px] opacity-80">
        <span className="capitalize">{item.color}</span>
        <span>{item.source_domain || "web search"}</span>
      </div>
    </div>
  );
}
