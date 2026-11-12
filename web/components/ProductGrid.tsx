import type { FashionItem } from "@/lib/types";
import Thumb from "./Thumb";
import { Button, Meta } from "./ui";

export default function ProductGrid({
  items,
  onOpen,
  onLike,
  onSwitchToSwipe,
}: {
  items: FashionItem[];
  onOpen: (item: FashionItem) => void;
  onLike: (item: FashionItem) => void;
  onSwitchToSwipe: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Meta>{items.length} curated online finds</Meta>
        <Button variant="ghost" onClick={onSwitchToSwipe}>
          Swipe mode
        </Button>
      </div>
      <ul className="grid grid-cols-[repeat(auto-fill,minmax(12.5rem,1fr))] gap-3.5">
        {items.map((item) => (
          <li
            key={item.id}
            className="flex flex-col overflow-hidden rounded-xl border border-stone-200 bg-white transition hover:border-brand-600 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-brand-400"
          >
            <button type="button" onClick={() => onOpen(item)} className="text-left">
              <Thumb item={item} />
              <div className="p-3 pb-1">
                <div className="font-semibold leading-snug">{item.name}</div>
                <div className="text-xs text-stone-500 dark:text-stone-400">
                  {item.brand} · <span className="capitalize">{item.color}</span>
                </div>
                <div className="mt-1 font-semibold">{item.price_text}</div>
              </div>
            </button>
            <div className="mt-auto flex items-center justify-between gap-2 p-3 pt-1">
              <Button variant="ghost" className="px-2.5 py-1 text-xs" onClick={() => onLike(item)}>
                ♥ Save
              </Button>
              {item.url && (item.image_source !== "ai_generated" || item.url_verified) ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-medium text-brand-700 underline dark:text-brand-400"
                >
                  {item.url_verified ? "Shop ↗" : "Find ↗"}
                </a>
              ) : item.image_source === "ai_generated" ? (
                <span className="text-[11px] text-amber-300">AI viz</span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
