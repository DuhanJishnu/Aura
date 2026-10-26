"use client";

import type { Shopper } from "@/hooks/useShopper";
import ComparePanel from "./ComparePanel";
import OrderConfirmation from "./OrderConfirmation";
import { ConsentCard, EstimateCard, UploadCard } from "./PhotoFlow";
import ProductDetail from "./ProductDetail";
import ProductGrid from "./ProductGrid";

/** The right-hand side: whatever the conversation last asked to show. */
export default function ProductPanel({ shopper }: { shopper: Shopper }) {
  const { panel } = shopper;
  const placeholder = (text: string) => <p className="mt-[18vh] text-center text-stone-500 dark:text-stone-400">{text}</p>;

  switch (panel.kind) {
    case "empty": return placeholder(panel.text);
    case "loading": return placeholder("Loading…");
    case "error": return placeholder(panel.text);
    case "grid": return <ProductGrid products={panel.products} onOpen={shopper.focusProduct} />;
    case "detail":
      return (
        <ProductDetail key={panel.product.id} product={panel.product} slots={shopper.slots} onBack={shopper.goBack}
          onAsk={() => shopper.send(`What do you think of the ${panel.product.name}?`)} onAdd={(size) => shopper.addToCart(panel.product, size)} />
      );
    case "compare": return <ComparePanel products={panel.products} onBack={shopper.goBack} onOpen={shopper.focusProduct} />;
    case "order": return <OrderConfirmation order={panel.order} onContinue={shopper.goBack} />;
    case "consent": return <ConsentCard onAgree={shopper.grantConsent} onDecline={shopper.declinePhoto} />;
    case "upload": return <UploadCard onAnalyze={shopper.analyzePhoto} />;
    case "estimate": return <EstimateCard estimate={panel.estimate} onConfirm={shopper.confirmEstimate} onDiscard={shopper.discardEstimate} />;
  }
}
