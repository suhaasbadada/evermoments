"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";

import { memoryClient } from "@/lib/memory/client";

export function ConsolidatePanel({ patientId }: { patientId: string }) {
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [patterns, setPatterns] = useState<string[]>([]);

  async function handleConsolidate() {
    setStatus("running");
    try {
      const result = await memoryClient.consolidateMemories(patientId);
      setPatterns(result.patterns ?? []);
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-900">Memory Consolidation</p>
          <p className="text-xs text-slate-500">
            Like human memory consolidation, this strengthens today&apos;s notes into the
            long-term graph.
          </p>
        </div>
        <button
          type="button"
          onClick={handleConsolidate}
          disabled={status === "running"}
          className="flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          <RefreshCw
            className={`h-4 w-4 ${status === "running" ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          Consolidate Today&apos;s Memories
        </button>
      </div>

      {status === "done" && patterns.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
          {patterns.map((pattern) => (
            <li key={pattern}>{pattern}</li>
          ))}
        </ul>
      )}
      {status === "error" && (
        <p className="text-sm text-red-600">Consolidation failed. Try again.</p>
      )}
    </div>
  );
}
