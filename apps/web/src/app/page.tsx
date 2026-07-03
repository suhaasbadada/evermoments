"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Mic, Search, Calendar, Brain, Moon, Sun } from "lucide-react";
import { checkMemoryHealth, seedPatient } from "@/lib/memoryClient";

const SUNDOWN_HOUR = 18; // 6 pm local time

export default function PatientHome() {
  const [sundownMode, setSundownMode] = useState(false);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    // Auto-enable sundowning if it's past 6 pm
    setSundownMode(new Date().getHours() >= SUNDOWN_HOUR);

    // Seed demo data on first load if memory API is reachable
    checkMemoryHealth()
      .then(() => seedPatient("p_001"))
      .catch(() => {
        // Silently skip — seed failure should not block the UI
      });

    // Keep the clock current
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);

  const toggleSundown = useCallback(() => setSundownMode((v) => !v), []);

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
      <main className="min-h-screen bg-indigo-950 flex flex-col items-center justify-center px-6 py-10 gap-8">
        {/* Orientation card */}
        <div className="w-full max-w-md rounded-3xl bg-indigo-900 p-8 text-center text-white shadow-2xl">
          <p className="text-6xl font-bold tabular-nums">{timeStr}</p>
          <p className="mt-3 text-2xl text-indigo-200">{dateStr}</p>
          <p className="mt-6 text-3xl font-semibold text-indigo-100">
            You are safe.
          </p>
          <p className="mt-2 text-lg text-indigo-300">
            You are at home. Everything is okay.
          </p>
        </div>

        {/* Only Record and Ask in evening mode */}
        <div className="flex w-full max-w-md flex-col gap-4">
          <Link
            href="/record"
            className="flex items-center justify-center gap-4 rounded-3xl bg-blue-600 px-8 py-8 text-3xl font-semibold text-white shadow-lg active:scale-95 transition-transform"
          >
            <Mic className="h-10 w-10 shrink-0" aria-hidden="true" />
            Record a Memory
          </Link>
          <Link
            href="/ask"
            className="flex items-center justify-center gap-4 rounded-3xl bg-indigo-600 px-8 py-8 text-3xl font-semibold text-white shadow-lg active:scale-95 transition-transform"
          >
            <Search className="h-10 w-10 shrink-0" aria-hidden="true" />
            Ask My Memory
          </Link>
        </div>

        <button
          onClick={toggleSundown}
          className="flex items-center gap-2 rounded-full bg-indigo-800 px-5 py-2 text-sm text-indigo-300 hover:bg-indigo-700 transition-colors"
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
    <main className="min-h-screen bg-amber-50 flex flex-col items-center justify-center px-6 py-12 gap-8">
      <div className="text-center">
        <p className="text-6xl mb-2" aria-hidden="true">
          👋
        </p>
        <h1 className="text-5xl font-bold text-amber-900">Hello!</h1>
        <p className="mt-2 text-2xl text-amber-700">What would you like to do?</p>
      </div>

      <div className="grid w-full max-w-sm gap-4">
        <Link
          href="/record"
          className="flex items-center gap-4 rounded-3xl bg-rose-500 px-8 py-7 text-2xl font-semibold text-white shadow-lg active:scale-95 transition-transform"
        >
          <Mic className="h-10 w-10 shrink-0" aria-hidden="true" />
          Record a Memory
        </Link>

        <Link
          href="/ask"
          className="flex items-center gap-4 rounded-3xl bg-blue-600 px-8 py-7 text-2xl font-semibold text-white shadow-lg active:scale-95 transition-transform"
        >
          <Search className="h-10 w-10 shrink-0" aria-hidden="true" />
          Ask My Memory
        </Link>

        <Link
          href="/memories"
          className="flex items-center gap-4 rounded-3xl bg-emerald-600 px-8 py-7 text-2xl font-semibold text-white shadow-lg active:scale-95 transition-transform"
        >
          <Calendar className="h-10 w-10 shrink-0" aria-hidden="true" />
          Today&apos;s Memories
        </Link>

        <Link
          href="/practice"
          className="flex items-center gap-4 rounded-3xl bg-violet-600 px-8 py-7 text-2xl font-semibold text-white shadow-lg active:scale-95 transition-transform"
        >
          <Brain className="h-10 w-10 shrink-0" aria-hidden="true" />
          Gentle Recall
        </Link>
      </div>

      {/* Demo toggle for judges — manual sundowning */}
      <button
        onClick={toggleSundown}
        className="flex items-center gap-2 rounded-full bg-amber-200 px-5 py-2 text-sm text-amber-800 hover:bg-amber-300 transition-colors"
        aria-label="Demo: activate evening mode"
      >
        <Moon className="h-4 w-4" aria-hidden="true" />
        Demo: Evening Mode
      </button>
    </main>
  );
}
