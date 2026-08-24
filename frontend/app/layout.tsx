import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "RevenueRescue AI — Revenue Recovery Console",
  description: "Autonomous AI revenue recovery agent. Razorpay Buildathon Track 03.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      {/* Light theme by default — no 'dark' class on html */}
      <body className={`${inter.variable} font-sans bg-background text-text-primary antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
