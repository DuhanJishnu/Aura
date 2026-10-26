import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Shopper",
  description: "A conversational shopping companion for shoes, clothes and accessories.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex h-full flex-col bg-stone-50 text-stone-900 antialiased dark:bg-neutral-950 dark:text-stone-100">{children}</body>
    </html>
  );
}
