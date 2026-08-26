import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Manrope, Montserrat } from "next/font/google";

import "./globals.css";
import { SiteShell } from "@/components/site-shell";
import { siteName, siteUrl } from "@/lib/site";

const headingFont = Montserrat({
  subsets: ["latin", "cyrillic"],
  weight: ["500", "700"],
  variable: "--font-heading",
});

const bodyFont = Manrope({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: {
    default: `${siteName} Marketplace`,
    template: `%s | ${siteName}`,
  },
  description:
    "Новый public storefront Servio на Next.js App Router: более сильный visual layer, mobile-first UX и safe migration поверх существующего backend-first marketplace контура.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="ru" className={`${headingFont.variable} ${bodyFont.variable}`}>
      <body style={{ fontFamily: "var(--font-body)" }}>
        <SiteShell>{children}</SiteShell>
      </body>
    </html>
  );
}
