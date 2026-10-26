"use client";

import { rupees, sizeText } from "@/lib/format";
import type { Cart } from "@/lib/types";
import Drawer from "./Drawer";
import { Button, Meta } from "./ui";

export default function CartDrawer({ open, cart, onClose, onRemove, onPlaceOrder }: {
  open: boolean; cart: Cart; onClose: () => void; onRemove: (productId: number, size: number) => void; onPlaceOrder: () => void;
}) {
  return (
    <Drawer open={open} title="Your cart" onClose={onClose} footer={
      <>
        <div className="flex justify-between"><span>Total</span><strong>{rupees(cart.total)}</strong></div>
        <Button onClick={onPlaceOrder} disabled={cart.items.length === 0}>Place order</Button>
      </>
    }>
      {cart.items.length === 0 ? <Meta>Your cart is empty.</Meta> : (
        <ul>
          {cart.items.map((c) => (
            <li key={`${c.shoe_id}-${c.size}`} className="flex items-center justify-between gap-2 border-b border-stone-200 py-2 dark:border-neutral-800">
              <div><div>{c.name}</div><Meta>{sizeText(c.category, c.size)} · {rupees(c.price)}</Meta></div>
              <Button variant="ghost" onClick={() => onRemove(c.shoe_id, c.size)}>Remove</Button>
            </li>
          ))}
        </ul>
      )}
    </Drawer>
  );
}
