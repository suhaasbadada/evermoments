"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { MobileNav } from "@/components/mobile-nav";

export default function PracticePage() {
  const router = useRouter();

  return (
    <main className="min-h-screen">
      <div className="app-shell app-shell--nav flex min-h-screen flex-col gap-4">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-teal-900/70"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back
      </button>

      <h1 className="text-3xl font-semibold text-emerald-950">Gentle Recall</h1>

      <div className="app-card p-7 text-center">
        <p className="text-4xl mb-3" aria-hidden="true">
          🧩
        </p>
        <p className="text-lg font-semibold text-emerald-900">Coming soon</p>
        <p className="text-sm text-teal-900/60 mt-1.5">
          Gentle memory practice exercises will appear here.
        </p>
      </div>
      </div>
      <MobileNav />
    </main>
  );
}
