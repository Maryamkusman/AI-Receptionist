import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import Shell from "@/components/Shell";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces", display: "swap", axes: ["opsz"] });

export const metadata: Metadata = {
  title: "FullChair — AI front desk",
  description: "Keeps your chairs booked: answers every call, text and DM, and refills cancellations automatically.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${fraunces.variable}`}>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
