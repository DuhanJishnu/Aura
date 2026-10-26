import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import CartDrawer from "./CartDrawer";

const noop = () => undefined;

describe("CartDrawer", () => {
  it("shows an empty cart and disables checkout", () => {
    render(<CartDrawer open cart={{ items: [], total: 0 }} onClose={noop} onRemove={noop} onPlaceOrder={noop} />);
    expect(screen.getByText("Your cart is empty.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Place order" })).toBeDisabled();
  });

  it("labels each line by category and removes the right one", async () => {
    const onRemove = vi.fn(); const onPlace = vi.fn();
    const cart = { total: 6597, items: [
      { shoe_id: 5, name: "Levis Graphic Tee", price: 1599, size: 3, category: "apparel" as const },
      { shoe_id: 7, name: "Titan Watch", price: 4999, size: 0, category: "accessories" as const },
    ] };
    render(<CartDrawer open cart={cart} onClose={noop} onRemove={onRemove} onPlaceOrder={onPlace} />);
    expect(screen.getByText(/size M · ₹1,599/)).toBeInTheDocument();
    expect(screen.getByText(/one size · ₹4,999/)).toBeInTheDocument();
    expect(screen.getByText("₹6,597")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Remove" })[1]);
    expect(onRemove).toHaveBeenCalledWith(7, 0);
    await userEvent.click(screen.getByRole("button", { name: "Place order" }));
    expect(onPlace).toHaveBeenCalled();
  });

  it("closes on Escape and renders nothing when closed", async () => {
    const onClose = vi.fn();
    const { rerender } = render(<CartDrawer open cart={{ items: [], total: 0 }} onClose={onClose} onRemove={noop} onPlaceOrder={noop} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
    rerender(<CartDrawer open={false} cart={{ items: [], total: 0 }} onClose={onClose} onRemove={noop} onPlaceOrder={noop} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
