"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

export default function PracticePage() {
  const router = useRouter();

  return (
    <main className="min-h-screen bg-amber-50 flex flex-col px-6 py-10 gap-6 max-w-xl mx-auto">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-amber-800 text-lg self-start"
      >
        <ArrowLeft className="h-5 w-5" aria-hidden="true" />
        Back
      </button>

      <h1 className="text-4xl font-bold text-amber-900">Gentle Recall</h1>

      <div className="rounded-2xl bg-white border border-amber-200 shadow p-8 text-center">
        <p className="text-5xl mb-4" aria-hidden="true">
          🧩
        </p>
        <p className="text-2xl font-semibold text-amber-800">Coming soon</p>
        <p className="text-lg text-amber-600 mt-2">
          Gentle memory practice exercises will appear here.
        </p>
      </div>
    </main>
  );
}
