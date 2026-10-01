import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { SITE_URL } from "@/lib/seo";

import { Analytics } from "@vercel/analytics/next";

import { Providers } from "./providers";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "Clipaso · Clips verticales con IA", template: "%s · Clipaso" },
  description:
    "Sube tu vídeo y Clipaso encuentra los mejores momentos y los convierte en clips verticales con subtítulos para TikTok, Reels y Shorts.",
  applicationName: "Clipaso",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0b0b" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <Providers>{children}</Providers>
        {/* Visitas sin cookies ni datos personales (Vercel Web Analytics). */}
        <Analytics />
      </body>
    </html>
  );
}
