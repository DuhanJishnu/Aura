import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ProductDetail from "./ProductDetail";
import type { Product } from "@/lib/types";

const base: Product = { id: 1, name: "Nike Runner", brand: "Nike", price: 4999, use_type: "sports", color: "black", rating: 4.5, description: "A shoe.", category: "shoes", sizes_in_stock: [8, 9, 10] };
const noop = () => undefined;

describe("ProductDetail", () => {
  it("pre-selects the size the shopper already gave, and adds that size", async () => {
    const onAdd = vi.fn();
    render(<ProductDetail product={base} slots={{ category: "shoes", size: 9 }} onBack={noop} onAsk={noop} onAdd={onAdd} />);
    expect(screen.getByRole("button", { name: "9" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(onAdd).toHaveBeenCalledWith(9);
  });

  it("asks for a size instead of guessing when none was chosen", async () => {
    const onAdd = vi.fn();
    render(<ProductDetail product={base} slots={{}} onBack={noop} onAsk={noop} onAdd={onAdd} />);
    await userEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(onAdd).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Pick a size first");
    await userEvent.click(screen.getByRole("button", { name: "10" }));
    await userEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(onAdd).toHaveBeenCalledWith(10);
  });

  it("does not apply a shoe size to a shirt, and shows apparel sizes as letters", () => {
    const shirt: Product = { ...base, category: "apparel", name: "Levis Graphic Tee", sizes_in_stock: [2, 3, 5] };
    render(<ProductDetail product={shirt} slots={{ category: "shoes", size: 9 }} onBack={noop} onAsk={noop} onAdd={noop} />);
    expect(screen.queryAllByRole("button", { pressed: true })).toHaveLength(0);
    expect(screen.getByRole("button", { name: "S" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "M" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "XL" })).toBeInTheDocument();
  });

  it("treats accessories as one size: nothing to pick, add works straight away", async () => {
    const onAdd = vi.fn();
    const watch: Product = { ...base, category: "accessories", name: "Titan Watch", sizes_in_stock: [0] };
    render(<ProductDetail product={watch} slots={{}} onBack={noop} onAsk={noop} onAdd={onAdd} />);
    expect(screen.getByText("One size")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(onAdd).toHaveBeenCalledWith(0);
  });

  it("disables adding when it is out of stock, and wires back and ask", async () => {
    const onBack = vi.fn(); const onAsk = vi.fn();
    render(<ProductDetail product={{ ...base, sizes_in_stock: [] }} slots={{}} onBack={onBack} onAsk={onAsk} onAdd={noop} />);
    expect(screen.getByText("Out of stock")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add to cart" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /back to results/i }));
    await userEvent.click(screen.getByRole("button", { name: "Ask about this" }));
    expect(onBack).toHaveBeenCalled(); expect(onAsk).toHaveBeenCalled();
  });
});
