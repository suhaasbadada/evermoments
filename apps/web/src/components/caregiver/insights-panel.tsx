import { Activity } from "lucide-react";
import { useMemo } from "react";

import { computeInsights } from "@/lib/memory/insights";
import type { MemoryResult } from "@/types/memory";

const SOURCE_LABELS = {
  patient: "From patient recordings",
  caregiver: "From caregiver responses",
} as const;

export function InsightsPanel({ memories }: { memories: MemoryResult[] }) {
  const insights = useMemo(() => computeInsights(memories), [memories]);

  if (insights.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
      <div className="flex items-center gap-2">
        <Activity className="h-5 w-5 text-indigo-600" aria-hidden="true" />
        <p className="text-sm font-medium text-slate-900">Patterns &amp; Signals</p>
      </div>
      <ul className="flex flex-col gap-2">
        {insights.map((insight) => (
          <li key={insight.id} className="flex flex-col gap-0.5 text-sm text-slate-700">
            <span>{insight.message}</span>
            <span className="text-xs text-indigo-500">{SOURCE_LABELS[insight.source]}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-slate-500">
        Communication summary for caregivers — not a medical assessment.
      </p>
    </div>
  );
}
