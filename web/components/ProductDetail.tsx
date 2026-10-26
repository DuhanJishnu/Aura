"use client";

import { useState } from "react";
import { categoryOf, rupees, sizeLabel } from "@/lib/format";
import type { Product, Slots } from "@/lib/types";
import Thumb from "./Thumb";
import { Button, Meta } from "./ui";

export default function ProductDetail({ product, slots, onBack, onAsk, onAdd }: {
  product: Product; slots: Slots; onBack: () => void; onAsk: () => void; onAdd: (size: number) => void;
}) {
  const category = categoryOf(product);
  const sizes = product.sizes_in_stock ?? [];
  // accessories are one size; otherwise pre-select the size the shopper already told us, if it is in stock
  const initial = category === "accessories" ? (sizes[0] ?? null)
    : categoryOf(slots) === category && slots.size != null && sizes.includes(slots.size) ? slots.size : null;
  const [chosen, setChosen] = useState<number | null>(initial);
  const [hint, setHint] = useState("");

  const add = () => {
    if (chosen === null) { setHint("Pick a size first, then add it to your cart."); return; }
    setHint("");
    onAdd(chosen);
  };

  return (
    <article>
      <Button variant="ghost" className="mb-3" onClick={onBack}>← Back to results</Button>
      <Thumb product={product} className="mb-4 h-56 rounded-2xl text-xl" />
      <h2 className="text-xl font-semibold">{product.name}</h2>
      <Meta>{product.brand} · {product.color} · {product.use_type} · ★ {product.rating}</Meta>
      <div className="mt-1 font-semibold">{rupees(product.price)}</div>
      <p className="my-3">{product.description}</p>

      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        {sizes.length === 0 ? <Meta>Out of stock</Meta>
          : category === "accessories" ? <Meta>One size</Meta>
          : (<>
              <Meta>Pick a size:</Meta>
              {sizes.map((s) => (
                <button key={s} type="button" aria-pressed={chosen === s} onClick={() => { setChosen(s); setHint(""); }}
                  className={`rounded-md border px-2.5 py-0.5 text-sm ${chosen === s ? "border-brand-600 bg-brand-600 text-white dark:border-brand-400 dark:bg-brand-400 dark:text-neutral-950" : "border-stone-300 dark:border-neutral-700"}`}>
                  {sizeLabel(category, s)}
                </button>
              ))}
            </>)}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="ghost" onClick={onAsk}>Ask about this</Button>
        <Button onClick={add} disabled={sizes.length === 0}>Add to cart</Button>
      </div>
      {hint && <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-300">{hint}</p>}
    </article>
  );
}
