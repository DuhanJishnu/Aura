"use client";

import type { Shopper } from "@/hooks/useShopper";
import ClosetView from "./ClosetView";
import ComparePanel from "./ComparePanel";
import LookDeck from "./LookDeck";
import OutfitBoard from "./OutfitBoard";
import { ConsentCard, EstimateCard, OutfitCheckCard, UploadCard } from "./PhotoFlow";
import ProductDetail from "./ProductDetail";
import ProductGrid from "./ProductGrid";
import SwipeDeck from "./SwipeDeck";
import WishlistView from "./WishlistView";

/** The right-hand Stylist Canvas: Swipe Deck, Outfit Lookbook, Saved Closet, Compare, or Photo Studio. */
export default function ProductPanel({ shopper }: { shopper: Shopper }) {
  const { panel } = shopper;
  const placeholder = (text: string) => (
    <p className="mt-[18vh] px-4 text-center text-stone-500 dark:text-stone-400">{text}</p>
  );

  switch (panel.kind) {
    case "empty":
      return placeholder(panel.text);
    case "loading":
      return placeholder("Searching online & styling…");
    case "error":
      return placeholder(panel.text);
    case "looks_deck":
      return (
        <LookDeck
          looks={panel.looks}
          onSwipe={shopper.swipeLook}
          onUndo={() => void shopper.undoSwipeLook()}
          onLoadMore={() => void shopper.searchMoreLooks()}
        />
      );
    case "wishlist":
      return (
        <WishlistView
          looks={shopper.styleDna?.saved_outfits ?? []}
          onInspectLook={(look) => shopper.applyAction({ type: "outfit_board", items: [], outfit: look })}
          onBuyLook={(look) => shopper.setBuySheetLook(look)}
          onRemoveLook={(id) => void shopper.removeWishlistLook(id)}
          onStartStyling={() => shopper.setViewMode("home")}
        />
      );
    case "swipe_deck":
      return (
        <SwipeDeck
          items={panel.items}
          onSwipe={shopper.swipe}
          onStyleAround={(item) =>
            shopper.send(`Build a complete outfit around the ${item.color} ${item.name} by ${item.brand}`)
          }
          onAskOpinion={(item) =>
            shopper.send(`What do you think of the ${item.name} by ${item.brand}? Give me an honest stylist check.`)
          }
          onOpenDetail={shopper.openDetail}
          onSwitchToGrid={() => shopper.setViewMode("grid")}
          onFindMore={() => shopper.send("Find more pieces online inspired by what I just liked!")}
        />
      );
    case "grid":
      return (
        <ProductGrid
          items={panel.items}
          onOpen={shopper.openDetail}
          onLike={(item) => void shopper.swipe(item, "like")}
          onSwitchToSwipe={() => shopper.setViewMode("swipe_deck")}
        />
      );
    case "detail":
      return (
        <ProductDetail
          key={panel.item.id}
          item={panel.item}
          onBack={shopper.goBack}
          onSave={() => void shopper.swipe(panel.item, "like")}
          onStyleAround={() =>
            shopper.send(`Build a complete outfit around the ${panel.item.color} ${panel.item.name}`)
          }
          onAsk={() => shopper.send(`What do you think of the ${panel.item.name} by ${panel.item.brand}?`)}
        />
      );
    case "outfit":
      return (
        <OutfitBoard
          outfit={panel.outfit}
          onSaveLook={(look) => void shopper.saveOutfit(look)}
          onSearchPiece={(q) => shopper.send(`Find ${q} online`)}
          onBack={shopper.goBack}
        />
      );
    case "compare":
      return <ComparePanel items={panel.items} onBack={shopper.goBack} onOpen={shopper.openDetail} />;
    case "closet":
      return (
        <ClosetView
          items={shopper.styleDna?.saved_closet ?? []}
          outfits={shopper.styleDna?.saved_outfits ?? []}
          onStyleAround={(item) =>
            shopper.send(`Build a complete outfit around my saved ${item.color} ${item.name}`)
          }
          onRemove={(id) => void shopper.removeFromCloset(id)}
          onOpenDetail={shopper.openDetail}
          onBuildClosetOutfit={() => shopper.send("Build an outfit using pieces from my saved closet!")}
          onOpenOutfit={(look) =>
            shopper.applyAction({ type: "outfit_board", items: [], outfit: look })
          }
        />
      );
    case "consent":
      return (
        <ConsentCard
          mode={panel.mode}
          onAgree={() => shopper.grantConsent(panel.mode)}
          onDecline={shopper.declinePhoto}
        />
      );
    case "upload":
      return (
        <UploadCard
          mode={panel.mode}
          onAnalyze={(file, note) => shopper.analyzePhoto(file, panel.mode, note)}
        />
      );
    case "estimate":
      return (
        <EstimateCard
          estimate={panel.estimate}
          onConfirm={shopper.confirmEstimate}
          onDiscard={shopper.discardEstimate}
        />
      );
    case "outfit_check":
      return (
        <OutfitCheckCard
          result={panel.result}
          onFindAddition={(q) => shopper.send(`Search online for ${q} to match my outfit`)}
          onDone={shopper.goBack}
        />
      );
  }
}
