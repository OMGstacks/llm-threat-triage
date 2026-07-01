import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import "./globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "OSAI Prep Studio",
  description: "AI-300 / OSAI red-team training range",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0d1117",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Reading a request header opts rendering into the dynamic path, so Next stamps the
  // per-request CSP nonce (set by middleware.ts) onto its framework/hydration scripts.
  // Without this the pages prerender statically and the nonce is never applied.
  headers();
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
