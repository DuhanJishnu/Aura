import { swatch } from "@/lib/format";
import type { Product } from "@/lib/types";

/** The demo catalog has no photos, so a product is its color with its brand on it. */
export default function Thumb({ product, className = "h-28" }: { product: Product; className?: string }) {
  return (
    <div
      className={`flex items-center justify-center text-xs font-semibold tracking-[0.12em] ${className}`}
      style={swatch(product.color)}
      aria-hidden="true"
    >
      {product.brand.toUpperCase()}
    </div>
  );
}
