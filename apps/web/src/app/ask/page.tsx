"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, ArrowLeft, Loader2 } from "lucide-react";
import { queryMemory } from "@/lib/memoryClient";
import type { MemoryAnswer, MemoryResult } from "@/lib/memoryClient";
import { SafetyBanner } from "@/components/SafetyBanner";
import { VerificationBadge } from "@/components/VerificationBadge";

const PATIENT_ID = "p_001";

const EXAMPLE_QUERIES = [
  "Where did I keep my wallet?",
  "Who visited me yesterday?",
  "Did I take my medicine today?",
  "What did the doctor say?",
];

const CHIP_COLORS = [
  "bg-rose-100 text-rose-700 hover:bg-rose-200",
  "bg-sky-100 text-sky-700 hover:bg-sky-200",
  "bg-teal-100 text-teal-700 hover:bg-teal-200",
  "bg-violet-100 text-violet-700 hover:bg-violet-200",
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
    <div className="flex flex-wrap items-center gap-2 mt-3 text-sm text-stone-400">
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
    <main className="min-h-screen bg-gradient-to-br from-rose-50 via-orange-50 to-amber-50 flex flex-col px-6 py-10 gap-6 max-w-xl mx-auto">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-stone-500 hover:text-stone-700 text-lg self-start transition-colors"
      >
        <ArrowLeft className="h-5 w-5" aria-hidden="true" />
        Back
      </button>

      <h1 className="text-4xl font-bold text-stone-800">Ask My Memory</h1>

      {/* Example prompt chips */}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Example questions">
        {EXAMPLE_QUERIES.map((q, i) => (
          <button
            key={q}
            onClick={() => submit(q)}
            className={`rounded-full px-4 py-2 text-base font-medium active:scale-95 transition-all ${CHIP_COLORS[i % CHIP_COLORS.length]}`}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Text input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit(query);
          }}
          placeholder="Type your question here…"
          aria-label="Ask a question about your memories"
          className="flex-1 rounded-2xl border-2 border-stone-200 bg-white px-5 py-4 text-xl text-stone-800 placeholder:text-stone-300 focus:outline-none focus:border-sky-400 transition-colors shadow-sm"
        />
        <button
          onClick={() => submit(query)}
          disabled={loading}
          aria-label="Search memories"
          className="rounded-2xl bg-sky-500 hover:bg-sky-600 px-5 py-4 text-white shadow-lg shadow-sky-200 disabled:opacity-50 active:scale-95 transition-all"
        >
          <Search className="h-7 w-7" aria-hidden="true" />
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center gap-4 py-8">
          <Loader2
            className="h-14 w-14 text-sky-500 animate-spin"
            aria-hidden="true"
          />
          <p className="text-xl text-stone-500">
            Looking through your memories…
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          role="alert"
          className="rounded-2xl bg-red-50 border border-red-200 p-5 shadow-sm"
        >
          <p className="text-lg text-red-700">{error}</p>
        </div>
      )}

      {/* Answer */}
      {answer && (
        <div className="flex flex-col gap-4">
          {/* Safety banners first — double-dose detection etc. */}
          {answer.warnings.map((w, i) => (
            <SafetyBanner key={i} warning={w} />
          ))}

          {/* Primary answer card */}
          <div className="rounded-2xl bg-white border border-stone-100 shadow-md p-6">
            <p className="text-2xl font-semibold text-stone-800 leading-relaxed">
              {answer.answer}
            </p>
            {answer.results[0] && <SourceLine result={answer.results[0]} />}
          </div>

          {/* Additional supporting results */}
          {answer.results.slice(1).map((r, i) => (
            <div
              key={i}
              className="rounded-2xl bg-white border border-stone-100 shadow-sm p-5"
            >
              <p className="text-lg text-stone-700 leading-relaxed">{r.fact}</p>
              <SourceLine result={r} />
            </div>
          ))}

          {answer.results.length === 0 && (
            <div className="rounded-2xl bg-amber-50 border border-amber-100 p-6 text-center shadow-sm">
              <p className="text-xl text-amber-700">
                I could not find anything about that. Try asking a different way.
              </p>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
