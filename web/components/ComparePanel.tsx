import type { FashionItem } from "@/lib/types";
import { Button } from "./ui";

export default function ComparePanel({
  items,
  onBack,
  onOpen,
}: {
  items: FashionItem[];
  onBack: () => void;
  onOpen: (item: FashionItem) => void;
}) {
  const rows: [string, (p: FashionItem) => string][] = [
    ["Brand", (p) => p.brand],
    ["Price", (p) => p.price_text],
    ["Color", (p) => p.color],
    ["Style match", (p) => `${Math.round(p.match_score)}%`],
    ["Vibe tags", (p) => p.aesthetic_tags.join(", ") || "—"],
    ["Fit note", (p) => p.fit_note || "—"],
    ["Styling tip", (p) => p.styling_tip || "—"],
  ];

  return (
    <div>
      <Button variant="ghost" className="mb-3" onClick={onBack}>
        ← Back
      </Button>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr>
              <th />
              {items.map((p) => (
                <th key={p.id} className="p-2">
                  <Button variant="ghost" onClick={() => onOpen(p)}>
                    {p.name}
                  </Button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label} className="border-b border-stone-200 align-top dark:border-neutral-800">
                <td className="whitespace-nowrap p-2 font-medium text-stone-500 dark:text-stone-400">{label}</td>
                {items.map((p) => (
                  <td key={p.id} className="p-2">
                    {value(p)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
