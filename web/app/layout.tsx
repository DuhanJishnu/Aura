import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aura · AI Fashion Stylist",
  description: "Google ADK AI personal stylist with live online discovery, swipe-to-learn taste memory, outfit boards, and Gemini Live voice.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="flex h-full flex-col overflow-hidden bg-[#0b0d0c] text-stone-100 antialiased">
        {children}
      </body>
    </html>
  );
}
