"use client";

import { useMemo, useState } from "react";

import type { EventType, MemoryResult, VerificationStatus } from "@/types/memory";

import { MemoryCard } from "./memory-card";

type TimeBucket = "Today" | "Yesterday" | "This Week" | "Earlier";

const BUCKET_ORDER: TimeBucket[] = ["Today", "Yesterday", "This Week", "Earlier"];

// Category chips map to event_type values from the §6.1 contract. There is no
// standalone "place" event type — object_location covers items and where they
// are, so one chip serves both.
const CATEGORIES: { key: EventType | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "person_mention", label: "People" },
  { key: "object_location", label: "Places & Objects" },
  { key: "medication_intake", label: "Medication" },
  { key: "appointment", label: "Appointments" },
  { key: "observation", label: "Observations" },
];

function bucketFor(iso: string): TimeBucket {
  const date = new Date(iso);
  const now = new Date();

  if (date.toDateString() === now.toDateString()) return "Today";

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";

  const weekAgo = new Date(now);
  weekAgo.setDate(now.getDate() - 7);
  weekAgo.setHours(0, 0, 0, 0);
  if (date >= weekAgo) return "This Week";

  return "Earlier";
}

export function TimelineView({
  memories,
  pendingIds,
  onVerify,
  onDelete,
}: {
  memories: MemoryResult[];
  pendingIds: Set<string>;
  onVerify: (eventId: string, status: VerificationStatus) => void;
  onDelete: (eventId: string) => void;
}) {
  const [category, setCategory] = useState<EventType | "all">("all");

  const buckets = useMemo(() => {
    const filtered =
      category === "all" ? memories : memories.filter((m) => m.event_type === category);

    const grouped = new Map<TimeBucket, MemoryResult[]>();
    for (const memory of filtered) {
      const bucket = bucketFor(memory.recorded_at);
      grouped.set(bucket, [...(grouped.get(bucket) ?? []), memory]);
    }
    return grouped;
  }, [memories, category]);

  const isEmpty = BUCKET_ORDER.every((b) => !buckets.get(b)?.length);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map(({ key, label }) => {
          const isActive = key === category;
          return (
            <button
              key={key}
              type="button"
              onClick={() => setCategory(key)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                isActive
                  ? "border-rose-600 bg-rose-50 text-rose-700"
                  : "border-slate-300 bg-white text-slate-600 hover:border-slate-400"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {isEmpty && (
        <p className="text-sm text-slate-500">No memories in this category yet.</p>
      )}

      {BUCKET_ORDER.map((bucket) => {
        const items = buckets.get(bucket);
        if (!items?.length) return null;
        return (
          <section key={bucket} className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {bucket}
            </h2>
            {items.map((memory) => (
              <MemoryCard
                key={memory.note_id}
                memory={memory}
                busy={pendingIds.has(memory.note_id)}
                onVerify={(status) => onVerify(memory.note_id, status)}
                onDelete={() => onDelete(memory.note_id)}
              />
            ))}
          </section>
        );
      })}
    </div>
  );
}
