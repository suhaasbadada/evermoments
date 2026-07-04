"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, ArrowLeft, Loader2 } from "lucide-react";
import { queryMemory } from "@/lib/memoryClient";
import type { MemoryAnswer, MemoryResult } from "@/lib/memoryClient";
import { SafetyBanner } from "@/components/SafetyBanner";
import { VerificationBadge } from "@/components/VerificationBadge";
import { MobileNav } from "@/components/mobile-nav";

const PATIENT_ID = "p_001";

const EXAMPLE_QUERIES = [
  "Where did I keep my wallet?",
  "Who visited me yesterday?",
  "Did I take my medicine today?",
  "What did the doctor say?",
];

const CHIP_COLORS = [
  "bg-teal-100 text-teal-800 hover:bg-teal-200",
  "bg-cyan-100 text-cyan-800 hover:bg-cyan-200",
  "bg-emerald-100 text-emerald-800 hover:bg-emerald-200",
  "bg-indigo-100 text-indigo-800 hover:bg-indigo-200",
];

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

function SourceLine({ result }: { result: MemoryResult }) {
  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs text-teal-900/55">
      <span>{formatDate(result.recorded_at)}</span>
      <span aria-hidden="true">·</span>
      <span className="capitalize">{result.source.replace(/_/g, " ")}</span>
      <span aria-hidden="true">·</span>
      <VerificationBadge
        status={result.verification_status}
        by={result.verified_by}
      />
    </div>
  );
}

export default function AskMemoryPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<MemoryAnswer | null>(null);
  const [error, setError] = useState("");

  const submit = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setQuery(trimmed);
    setLoading(true);
    setAnswer(null);
    setError("");
    try {
      const result = await queryMemory(PATIENT_ID, trimmed);
      setAnswer(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not reach memory. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }, []);

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

      <h1 className="text-3xl font-semibold text-emerald-950">Ask My Memory</h1>

      {/* Example prompt chips */}
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Example questions">
        {EXAMPLE_QUERIES.map((q, i) => (
          <button
            key={q}
            onClick={() => submit(q)}
            className={`app-button rounded-full px-3 py-1.5 text-xs font-semibold ${CHIP_COLORS[i % CHIP_COLORS.length]}`}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Text input */}
      <div className="app-card flex gap-2 p-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit(query);
          }}
          placeholder="Type your question here…"
          aria-label="Ask a question about your memories"
          className="flex-1 rounded-xl border border-teal-900/10 bg-white/80 px-3.5 py-2.5 text-sm text-emerald-950 placeholder:text-teal-900/40 focus:border-cyan-500 focus:outline-none"
        />
        <button
          onClick={() => submit(query)}
          disabled={loading}
          aria-label="Search memories"
          className="app-button rounded-xl bg-cyan-600 px-3 py-2.5 text-white shadow-sm shadow-cyan-900/20 hover:bg-cyan-500 disabled:opacity-50"
        >
          <Search className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center gap-3 py-7">
          <Loader2
            className="h-10 w-10 text-cyan-600 animate-spin"
            aria-hidden="true"
          />
          <p className="text-sm text-teal-900/60">
            Looking through your memories…
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          role="alert"
          className="app-card border-rose-200 bg-rose-50 p-4"
        >
          <p className="text-sm text-rose-700">{error}</p>
        </div>
      )}

      {/* Answer */}
      {answer && (
        <div className="flex flex-col gap-3">
          {/* Safety banners first — double-dose detection etc. */}
          {answer.warnings.map((w, i) => (
            <SafetyBanner key={i} warning={w} />
          ))}

          {/* Primary answer card */}
          <div className="app-card p-4">
            <p className="text-base font-semibold text-emerald-950 leading-relaxed">
              {answer.answer}
            </p>
            {answer.results[0] && <SourceLine result={answer.results[0]} />}
          </div>

          {/* Additional supporting results */}
          {answer.results.slice(1).map((r, i) => (
            <div
              key={i}
              className="app-card p-4"
            >
              <p className="text-sm text-teal-950 leading-relaxed">{r.fact}</p>
              <SourceLine result={r} />
            </div>
          ))}

          {answer.results.length === 0 && (
            <div className="app-card border-amber-200 bg-amber-50 p-5 text-center">
              <p className="text-sm text-amber-700">
                I could not find anything about that. Try asking a different way.
              </p>
            </div>
          )}
        </div>
      )}
      </div>
      <MobileNav />
    </main>
  );
}
