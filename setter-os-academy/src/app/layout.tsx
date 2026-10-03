import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ThemeSync, themeBootScript } from "@/components/ThemeSync";

export const metadata: Metadata = {
  title: { default: "SETTER OS ACADEMY", template: "%s · SETTER OS" },
  description: "Learn the skill. Master the conversation. – Nichtkommerzieller Prototyp einer Lernplattform für Appointment Setting.",
  robots: { index: false, follow: false }, // prototype: never indexed
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0a0f1e" },
    { media: "(prefers-color-scheme: light)", color: "#f6f7fb" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className="min-h-dvh">
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-elev focus:px-3 focus:py-2">
          Zum Inhalt springen
        </a>
        <ThemeSync />
        {children}
      </body>
    </html>
  );
}
