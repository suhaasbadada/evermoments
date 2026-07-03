import type { MemoryResult } from "@/types/memory";

// Frequency-based signals computed client-side over the fetched memory list.
// These complement (not duplicate) Module 3's improve() pattern-surfacing:
// improve() derives patterns from the graph; these are raw counts over what
// the dashboard already has. Framed as memory-support signals for caregivers,
// never as detection or diagnosis.

export interface Insight {
  id: string;
  // "patient" = counted from what the patient recorded;
  // "caregiver" = counted from caregiver verification responses.
  source: "patient" | "caregiver";
  message: string;
}

const WINDOW_DAYS = 10;

function withinWindow(iso: string): boolean {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - WINDOW_DAYS);
  cutoff.setHours(0, 0, 0, 0);
  return new Date(iso) >= cutoff;
}

function normalizeFact(fact: string): string {
  return fact.toLowerCase().replace(/[^a-z0-9 ]/g, "").trim();
}

export function computeInsights(memories: MemoryResult[]): Insight[] {
  const recent = memories.filter((m) => withinWindow(m.recorded_at));
  const insights: Insight[] = [];

  // Patient signal: the same thing recorded on multiple distinct days.
  const factDays = new Map<string, { fact: string; days: Set<string> }>();
  for (const m of recent) {
    const key = normalizeFact(m.fact);
    const entry = factDays.get(key) ?? { fact: m.fact, days: new Set<string>() };
    entry.days.add(new Date(m.recorded_at).toDateString());
    factDays.set(key, entry);
  }
  for (const { fact, days } of factDays.values()) {
    if (days.size >= 2) {
      insights.push({
        id: `repeat-${normalizeFact(fact)}`,
        source: "patient",
        message: `"${fact}" recorded on ${days.size} different days in the last ${WINDOW_DAYS} days.`,
      });
    }
  }

  // Patient signal: possible duplicate medication recordings.
  const doubleDoses = recent.filter((m) => m.warning?.type === "possible_double_dose");
  if (doubleDoses.length > 0) {
    insights.push({
      id: "double-dose",
      source: "patient",
      message: `${doubleDoses.length} possible duplicate medication recording${doubleDoses.length > 1 ? "s" : ""} flagged in the last ${WINDOW_DAYS} days.`,
    });
  }

  // Caregiver signal: notes the caregiver marked incorrect — the gap between
  // what the patient recorded and what actually happened.
  const incorrect = recent.filter((m) => m.verification_status === "incorrect");
  if (incorrect.length > 0) {
    insights.push({
      id: "incorrect-count",
      source: "caregiver",
      message: `${incorrect.length} memor${incorrect.length > 1 ? "ies" : "y"} marked incorrect by a caregiver in the last ${WINDOW_DAYS} days.`,
    });
  }

  // Caregiver signal: open safety-critical notes.
  const safetyCritical = recent.filter(
    (m) => m.verification_status === "safety_critical",
  );
  if (safetyCritical.length > 0) {
    insights.push({
      id: "safety-critical",
      source: "caregiver",
      message: `${safetyCritical.length} safety-critical note${safetyCritical.length > 1 ? "s" : ""} awaiting resolution.`,
    });
  }

  return insights;
}
