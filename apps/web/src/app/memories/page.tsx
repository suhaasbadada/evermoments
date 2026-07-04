"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import { listMemories, seedPatient } from "@/lib/memoryClient";
import type { MemoryResult } from "@/lib/memoryClient";
import { VerificationBadge } from "@/components/VerificationBadge";
import { MobileNav } from "@/components/mobile-nav";



function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

import { usePatient } from "@/components/patient-context";

export default function MemoriesPage() {
  const router = useRouter();
  const { patientId } = usePatient();
  const [memories, setMemories] = useState<MemoryResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadMemories = useCallback(async (showSpinner = false) => {
    if (showSpinner) setLoading(true);
    setError("");

    try {
      const first = await listMemories(patientId, undefined, "recorded_at_desc", 20);
      if (first.results.length > 0) {
        setMemories(first.results);
        return;
      }

      // Demo-friendly behavior: seed baseline memories when the store is empty.
      await seedPatient(patientId);
      const second = await listMemories(patientId, undefined, "recorded_at_desc", 20);
      setMemories(second.results);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load memories."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => {
      void loadMemories(true);
    }, 0);

    const handlePageShow = () => {
      void loadMemories(false);
    };

    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        void loadMemories(false);
      }
    };

    window.addEventListener("pageshow", handlePageShow);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.clearTimeout(initialLoad);
      window.removeEventListener("pageshow", handlePageShow);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [loadMemories]);

  return (
    <main className="min-h-screen">
      <div className="app-shell app-shell--nav flex min-h-screen flex-col gap-4">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-teal-900/70 transition-colors hover:text-teal-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back
      </button>

      <h1 className="text-3xl font-semibold text-emerald-950">Today&apos;s Memories</h1>

      {loading && (
        <div className="flex flex-col items-center gap-3 py-8">
          <Loader2
            className="h-10 w-10 text-emerald-600 animate-spin"
            aria-hidden="true"
          />
          <p className="text-sm text-teal-900/60">Loading your memories…</p>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="app-card border-rose-200 bg-rose-50 p-4"
        >
          <p className="text-sm text-rose-700">{error}</p>
        </div>
      )}

      {!loading && !error && memories.length === 0 && (
        <div className="app-card p-6 text-center">
          <p className="text-4xl mb-2" aria-hidden="true">🌱</p>
          <p className="text-lg text-emerald-950">No memories yet.</p>
          <p className="text-sm text-teal-900/55 mt-1.5">
            Record your first memory to get started!
          </p>
        </div>
      )}

      <div className="flex flex-col gap-2.5">
        {memories.map((m, i) => (
          <div
            key={i}
            className="app-card p-4"
          >
            <p className="text-sm text-teal-950 leading-relaxed">{m.fact}</p>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <span className="text-xs text-teal-900/55">
                {formatDate(m.recorded_at)}
              </span>
              <span className="text-teal-900/35" aria-hidden="true">·</span>
              <VerificationBadge
                status={m.verification_status}
                by={m.verified_by}
              />
            </div>
          </div>
        ))}
      </div>
      </div>
      <MobileNav />
    </main>
  );
}
