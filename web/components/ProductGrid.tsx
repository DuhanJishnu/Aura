import { rupees } from "@/lib/format";
import type { Product } from "@/lib/types";
import Thumb from "./Thumb";

export default function ProductGrid({ products, onOpen }: { products: Product[]; onOpen: (id: number) => void }) {
  return (
    <ul className="grid grid-cols-[repeat(auto-fill,minmax(10.5rem,1fr))] gap-3.5">
      {products.map((p) => (
        <li key={p.id}>
          <button type="button" onClick={() => onOpen(p.id)}
            className="w-full overflow-hidden rounded-xl border border-stone-200 bg-white text-left transition hover:border-brand-600 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-brand-400">
            <Thumb product={p} />
            <div className="p-3">
              <div className="font-semibold">{p.name}</div>
              <div className="text-sm text-stone-500 dark:text-stone-400">{p.color} · {p.use_type} · ★ {p.rating}</div>
              <div className="mt-1 font-semibold">{rupees(p.price)}</div>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
