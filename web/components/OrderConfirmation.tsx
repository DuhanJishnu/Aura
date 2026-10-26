import { rupees, sizeText } from "@/lib/format";
import type { Order } from "@/lib/types";
import { Button, Meta } from "./ui";

export default function OrderConfirmation({ order, onContinue }: { order: Order; onContinue: () => void }) {
  return (
    <section aria-label="Order confirmed">
      <h2 className="text-xl font-semibold">Order confirmed</h2>
      <Meta>Order {order.order_id}</Meta>
      <ul className="my-3">
        {order.items.map((i) => (
          <li key={`${i.shoe_id}-${i.size}`} className="flex justify-between border-b border-stone-200 py-1.5 dark:border-neutral-800">
            <span>{i.name} · {sizeText(i.category, i.size)}</span><span>{rupees(i.price)}</span>
          </li>
        ))}
        <li className="flex justify-between py-1.5 font-semibold"><span>Total</span><span>{rupees(order.total)}</span></li>
      </ul>
      <p className="mb-3 text-sm text-stone-500 dark:text-stone-400">This was a mock checkout. Nothing was charged.</p>
      <Button variant="ghost" onClick={onContinue}>Keep shopping</Button>
    </section>
  );
}
