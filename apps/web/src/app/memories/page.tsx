"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import { listMemories, seedPatient } from "@/lib/memoryClient";
import type { MemoryResult } from "@/lib/memoryClient";
import { VerificationBadge } from "@/components/VerificationBadge";

const PATIENT_ID = "p_001";

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

export default function MemoriesPage() {
  const router = useRouter();
  const [memories, setMemories] = useState<MemoryResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadMemories = useCallback(async (showSpinner = false) => {
    if (showSpinner) setLoading(true);
    setError("");

    try {
      const first = await listMemories(PATIENT_ID, undefined, "recorded_at_desc", 20);
      if (first.results.length > 0) {
        setMemories(first.results);
        return;
      }

      // Demo-friendly behavior: seed baseline memories when the store is empty.
      await seedPatient(PATIENT_ID);
      const second = await listMemories(PATIENT_ID, undefined, "recorded_at_desc", 20);
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
    void loadMemories(true);

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
      window.removeEventListener("pageshow", handlePageShow);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [loadMemories]);

  return (
    <main className="min-h-screen bg-amber-50 flex flex-col px-6 py-10 gap-6 max-w-xl mx-auto">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-amber-800 text-lg self-start"
      >
        <ArrowLeft className="h-5 w-5" aria-hidden="true" />
        Back
      </button>

      <h1 className="text-4xl font-bold text-amber-900">Today&apos;s Memories</h1>

      {loading && (
        <div className="flex flex-col items-center gap-4 py-10">
          <Loader2
            className="h-14 w-14 text-amber-600 animate-spin"
            aria-hidden="true"
          />
          <p className="text-xl text-amber-700">Loading your memories…</p>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-2xl bg-red-50 border border-red-300 p-5"
        >
          <p className="text-lg text-red-800">{error}</p>
        </div>
      )}

      {!loading && !error && memories.length === 0 && (
        <div className="rounded-2xl bg-white border border-amber-200 p-8 text-center shadow">
          <p className="text-5xl mb-3" aria-hidden="true">
            🌱
          </p>
          <p className="text-2xl text-amber-700">No memories yet.</p>
          <p className="text-lg text-amber-600 mt-2">
            Record your first memory to get started!
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {memories.map((m, i) => (
          <div
            key={i}
            className="rounded-2xl bg-white border border-amber-200 shadow-sm p-5"
          >
            <p className="text-lg text-slate-900 leading-relaxed">{m.fact}</p>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <span className="text-sm text-slate-500">
                {formatDate(m.recorded_at)}
              </span>
              <span className="text-slate-300" aria-hidden="true">
                ·
              </span>
              <VerificationBadge
                status={m.verification_status}
                by={m.verified_by}
              />
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
