"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Mic, Search, Calendar, Brain } from "lucide-react";
import { checkMemoryHealth, listMemories, seedPatient } from "@/lib/memoryClient";
import { MobileNav } from "@/components/mobile-nav";

export default function PatientHome() {
  useEffect(() => {
    // Seed demo data on first load if memory API is reachable
    checkMemoryHealth()
      .then(async () => {
        const existing = await listMemories("p_001", undefined, "recorded_at_desc", 1);
        if (existing.results.length === 0) {
          await seedPatient("p_001");
        }
      })
      .catch(() => {
        // Silently skip — seed failure should not block the UI
      });
  }, []);

  return (
    <main className="min-h-screen">
      <div className="app-shell app-shell--nav flex min-h-screen flex-col justify-center gap-5">
      <div className="text-left fade-up">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-teal-700/75">
          Evermoments
        </p>
        <h1 className="mt-1 text-4xl font-semibold text-emerald-950">
          Good to see you.
        </h1>
        <p className="mt-1 text-sm text-teal-900/60">
          Pick one thing to focus on right now.
        </p>
      </div>

      <div className="grid gap-2.5 fade-up fade-up-delay-2">
        <Link
          href="/record"
          className="app-button app-card flex items-center gap-3 px-4 py-3.5 text-sm font-semibold text-emerald-950 hover:bg-white/95"
        >
          <span className="rounded-xl bg-teal-600 p-2 text-white shadow-sm">
            <Mic className="h-4 w-4 shrink-0" aria-hidden="true" />
          </span>
          Record a Memory
        </Link>

        <Link
          href="/ask"
          className="app-button app-card flex items-center gap-3 px-4 py-3.5 text-sm font-semibold text-emerald-950 hover:bg-white/95"
        >
          <span className="rounded-xl bg-cyan-600 p-2 text-white shadow-sm">
            <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
          </span>
          Ask My Memory
        </Link>

        <Link
          href="/memories"
          className="app-button app-card flex items-center gap-3 px-4 py-3.5 text-sm font-semibold text-emerald-950 hover:bg-white/95"
        >
          <span className="rounded-xl bg-emerald-600 p-2 text-white shadow-sm">
            <Calendar className="h-4 w-4 shrink-0" aria-hidden="true" />
          </span>
          Today&apos;s Memories
        </Link>

        <Link
          href="/practice"
          className="app-button app-card flex items-center gap-3 px-4 py-3.5 text-sm font-semibold text-emerald-950 hover:bg-white/95"
        >
          <span className="rounded-xl bg-indigo-600 p-2 text-white shadow-sm">
            <Brain className="h-4 w-4 shrink-0" aria-hidden="true" />
          </span>
          Gentle Recall
        </Link>
      </div>
      </div>
      <MobileNav />
    </main>
  );
}
