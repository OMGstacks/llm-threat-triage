import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OSAI Prep Studio",
  description: "AI-300 / OSAI red-team training range",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
