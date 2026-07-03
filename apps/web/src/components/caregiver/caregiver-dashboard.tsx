"use client";

import { LoaderCircle, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { memoryClient } from "@/lib/memory/client";
import { DEFAULT_PATIENT_ID } from "@/lib/memory/constants";
import type { MemoryResult, VerificationStatus } from "@/types/memory";

import { ConsolidatePanel } from "./consolidate-panel";
import { InsightsPanel } from "./insights-panel";
import { MemoryCard } from "./memory-card";
import { TabBar, type CaregiverTab } from "./tab-bar";
import { TimelineView } from "./timeline-view";

const ATTENTION_STATUSES: VerificationStatus[] = ["unverified", "needs_check", "safety_critical"];

export function CaregiverDashboard() {
  const [memories, setMemories] = useState<MemoryResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<CaregiverTab>("attention");
  const [caregiverName, setCaregiverName] = useState("Ravi");
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;

    memoryClient
      .listMemories({ patient_id: DEFAULT_PATIENT_ID, sort: "recorded_at_desc" })
      .then((results) => {
        if (!cancelled) {
          setMemories(results);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Could not load memories.");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const attentionList = useMemo(
    () => memories.filter((m) => ATTENTION_STATUSES.includes(m.verification_status)),
    [memories],
  );
  const medicationList = useMemo(
    () => memories.filter((m) => m.event_type === "medication_intake"),
    [memories],
  );

  const listForTab: Record<Exclude<CaregiverTab, "timeline">, MemoryResult[]> = {
    attention: attentionList,
    all: memories,
    medication: medicationList,
  };

  const counts: Partial<Record<CaregiverTab, number>> = {
    attention: attentionList.length,
    all: memories.length,
    medication: medicationList.length,
  };

  async function handleVerify(eventId: string, status: VerificationStatus) {
    setPendingIds((prev) => new Set(prev).add(eventId));
    try {
      await memoryClient.verifyMemory(
        DEFAULT_PATIENT_ID,
        eventId,
        status,
        caregiverName.trim() || "Caregiver",
      );
      setMemories((prev) =>
        prev.map((m) =>
          m.note_id === eventId
            ? { ...m, verification_status: status, verified_by: caregiverName.trim() || "Caregiver" }
            : m,
        ),
      );
    } catch {
      setError("Could not update verification status. Try again.");
    } finally {
      setPendingIds((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    }
  }

  async function handleDelete(eventId: string) {
    if (!window.confirm("Delete this memory? This cannot be undone.")) return;

    setPendingIds((prev) => new Set(prev).add(eventId));
    try {
      await memoryClient.deleteMemory(DEFAULT_PATIENT_ID, eventId);
      setMemories((prev) => prev.filter((m) => m.note_id !== eventId));
    } catch {
      setError("Could not delete the memory. Try again.");
    } finally {
      setPendingIds((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-rose-600" aria-hidden="true" />
          <h1 className="text-xl font-semibold text-slate-900">Caregiver Dashboard</h1>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Verifying as
          <input
            value={caregiverName}
            onChange={(e) => setCaregiverName(e.target.value)}
            className="w-32 rounded-lg border border-slate-300 px-2 py-1 text-sm text-slate-900"
          />
        </label>
      </div>

      <ConsolidatePanel patientId={DEFAULT_PATIENT_ID} />

      {!loading && <InsightsPanel memories={memories} />}

      <TabBar active={activeTab} counts={counts} onChange={setActiveTab} />

      {loading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
          Loading memories…
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && activeTab === "timeline" && (
        <TimelineView
          memories={memories}
          pendingIds={pendingIds}
          onVerify={handleVerify}
          onDelete={handleDelete}
        />
      )}

      {!loading && activeTab !== "timeline" && (
        <>
          {!error && listForTab[activeTab].length === 0 && (
            <p className="text-sm text-slate-500">Nothing here right now.</p>
          )}
          <div className="flex flex-col gap-3">
            {listForTab[activeTab].map((memory) => (
              <MemoryCard
                key={memory.note_id}
                memory={memory}
                busy={pendingIds.has(memory.note_id)}
                onVerify={(status) => handleVerify(memory.note_id, status)}
                onDelete={() => handleDelete(memory.note_id)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
