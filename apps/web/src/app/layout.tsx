import type { Metadata } from "next";
import { Manrope, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { HealthIndicator } from "@/components/HealthIndicator";
import { TailwindLoader } from "@/components/TailwindLoader";

const bodyFont = Manrope({
  variable: "--font-body",
  subsets: ["latin"],
});

const displayFont = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Evermoments",
  description: "Your memory companion",
};

import { PatientProvider } from "@/components/patient-context";
import { PatientSwitcher } from "@/components/patient-switcher";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${bodyFont.variable} ${displayFont.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        {/* Loads Tailwind CDN after React hydration — avoids event-handler loss */}
        <TailwindLoader />
        {/* Unobtrusive memory-API health indicator */}
        <div className="fixed right-3 top-3 z-50">
          <HealthIndicator />
        </div>
        <PatientProvider>
          {children}
          <PatientSwitcher />
        </PatientProvider>
      </body>
    </html>
  );
}
