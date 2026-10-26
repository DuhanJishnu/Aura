import { rupees, sizeLabel } from "@/lib/format";
import type { Product } from "@/lib/types";
import { Button } from "./ui";

export default function ComparePanel({ products, onBack, onOpen }: { products: Product[]; onBack: () => void; onOpen: (id: number) => void }) {
  const rows: [string, (p: Product) => string][] = [
    ["Price", (p) => rupees(p.price)],
    ["Rating", (p) => `★ ${p.rating}`],
    ["Color", (p) => p.color],
    ["Use", (p) => p.use_type],
    ["Sizes in stock", (p) => (p.sizes_in_stock ?? []).map((s) => sizeLabel(p.category, s)).join(", ") || "none"],
  ];
  return (
    <div>
      <Button variant="ghost" className="mb-3" onClick={onBack}>← Back to results</Button>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr>
              <th />
              {products.map((p) => (
                <th key={p.id} className="p-2"><Button variant="ghost" onClick={() => onOpen(p.id)}>{p.name}</Button></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label} className="border-b border-stone-200 align-top dark:border-neutral-800">
                <td className="whitespace-nowrap p-2 text-stone-500 dark:text-stone-400">{label}</td>
                {products.map((p) => <td key={p.id} className="p-2">{value(p)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
