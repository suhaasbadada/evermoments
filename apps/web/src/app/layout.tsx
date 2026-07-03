import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { HealthIndicator } from "@/components/HealthIndicator";
import { TailwindLoader } from "@/components/TailwindLoader";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Evermoments",
  description: "Your memory companion",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        {/* Loads Tailwind CDN after React hydration — avoids event-handler loss */}
        <TailwindLoader />
        {/* Unobtrusive memory-API health indicator */}
        <div className="fixed right-3 top-3 z-50">
          <HealthIndicator />
        </div>
        {children}
      </body>
    </html>
  );
}
