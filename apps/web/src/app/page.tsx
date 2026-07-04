"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Mic, Search, Calendar, Brain, Moon, Sun } from "lucide-react";
import { checkMemoryHealth, listMemories, seedPatient } from "@/lib/memoryClient";

const SUNDOWN_HOUR = 18; // 6 pm local time

export default function PatientHome() {
  const [sundownMode, setSundownMode] = useState(false);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    // Auto-enable sundowning if it's past 6 pm, but respect manual override
    const stored = localStorage.getItem("sundownMode");
    const isEvening = new Date().getHours() >= SUNDOWN_HOUR;
    const initial = stored !== null ? stored === "true" : isEvening;
    setSundownMode(initial);

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

    // Keep the clock current
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);

  const toggleSundown = useCallback(() => setSundownMode((v) => {
    const next = !v;
    localStorage.setItem("sundownMode", String(next));
    return next;
  }), []);

  const dateStr = now.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const timeStr = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

  // ── Sundowning / Safe mode ──────────────────────────────────────────────
  if (sundownMode) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-slate-900 via-indigo-950 to-slate-900 flex flex-col items-center justify-center px-6 py-10 gap-8">
        {/* Orientation card */}
        <div className="w-full max-w-md rounded-3xl bg-white/5 border border-white/10 backdrop-blur-sm p-8 text-center text-white shadow-2xl">
          <p className="text-6xl font-bold tabular-nums tracking-tight">{timeStr}</p>
          <p className="mt-3 text-2xl text-indigo-200">{dateStr}</p>
          <div className="mt-6 h-px bg-white/10" />
          <p className="mt-6 text-3xl font-semibold text-indigo-100">
            You are safe. 🤍
          </p>
          <p className="mt-2 text-lg text-indigo-300">
            You are at home. Everything is okay.
          </p>
        </div>

        {/* Only Record and Ask in evening mode */}
        <div className="flex w-full max-w-md flex-col gap-4">
          <Link
            href="/record"
            className="flex items-center justify-center gap-4 rounded-3xl bg-violet-600 hover:bg-violet-500 px-8 py-8 text-3xl font-semibold text-white shadow-lg shadow-violet-900 active:scale-95 transition-all"
          >
            <Mic className="h-10 w-10 shrink-0" aria-hidden="true" />
            Record a Memory
          </Link>
          <Link
            href="/ask"
            className="flex items-center justify-center gap-4 rounded-3xl bg-blue-800 hover:bg-blue-700 border border-blue-700 px-8 py-8 text-3xl font-semibold text-white shadow-lg active:scale-95 transition-all"
          >
            <Search className="h-10 w-10 shrink-0" aria-hidden="true" />
            Ask My Memory
          </Link>
        </div>

        <button
          onClick={toggleSundown}
          className="flex items-center gap-2 rounded-full bg-white/10 hover:bg-white/20 px-5 py-2 text-sm text-slate-300 transition-colors"
          aria-label="Switch to day mode"
        >
          <Sun className="h-4 w-4" aria-hidden="true" />
          Switch to Day Mode
        </button>
      </main>
    );
  }

  // ── Day mode ────────────────────────────────────────────────────────────
  return (
    <main className="min-h-screen bg-gradient-to-br from-rose-50 via-orange-50 to-amber-50 flex flex-col items-center justify-center px-6 py-12 gap-8">
      <div className="text-center">
        <p className="text-6xl mb-3" aria-hidden="true">🌿</p>
        <h1 className="text-5xl font-bold text-stone-800">Hello!</h1>
        <p className="mt-2 text-2xl text-stone-500">What would you like to do?</p>
      </div>

      <div className="grid w-full max-w-sm gap-3">
        <Link
          href="/record"
          className="flex items-center gap-4 rounded-3xl bg-rose-400 hover:bg-rose-500 px-8 py-7 text-2xl font-semibold text-white shadow-lg shadow-rose-200 active:scale-95 transition-all"
        >
          <Mic className="h-10 w-10 shrink-0" aria-hidden="true" />
          Record a Memory
        </Link>

        <Link
          href="/ask"
          className="flex items-center gap-4 rounded-3xl bg-sky-500 hover:bg-sky-600 px-8 py-7 text-2xl font-semibold text-white shadow-lg shadow-sky-200 active:scale-95 transition-all"
        >
          <Search className="h-10 w-10 shrink-0" aria-hidden="true" />
          Ask My Memory
        </Link>

        <Link
          href="/memories"
          className="flex items-center gap-4 rounded-3xl bg-teal-500 hover:bg-teal-600 px-8 py-7 text-2xl font-semibold text-white shadow-lg shadow-teal-200 active:scale-95 transition-all"
        >
          <Calendar className="h-10 w-10 shrink-0" aria-hidden="true" />
          Today&apos;s Memories
        </Link>

        <Link
          href="/practice"
          className="flex items-center gap-4 rounded-3xl bg-violet-500 hover:bg-violet-600 px-8 py-7 text-2xl font-semibold text-white shadow-lg shadow-violet-200 active:scale-95 transition-all"
        >
          <Brain className="h-10 w-10 shrink-0" aria-hidden="true" />
          Gentle Recall
        </Link>
      </div>

      {/* Demo toggle for judges — manual sundowning */}
      <button
        onClick={toggleSundown}
        className="flex items-center gap-2 rounded-full bg-stone-100 hover:bg-stone-200 px-5 py-2 text-sm text-stone-500 transition-colors"
        aria-label="Demo: activate evening mode"
      >
        <Moon className="h-4 w-4" aria-hidden="true" />
        Demo: Evening Mode
      </button>
    </main>
  );
}
