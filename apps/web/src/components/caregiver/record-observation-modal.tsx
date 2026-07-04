import { useState } from "react";
import { Loader2, Plus, X } from "lucide-react";
import { usePatient } from "@/components/patient-context";
import { API_BASE_URL } from "@/lib/api";
import { ingestMemoryEvent, type MemoryEvent } from "@/lib/memoryClient";

export function RecordObservationModal({
  isOpen,
  onClose,
  onSuccess,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { patientId } = usePatient();
  const [text, setText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Extract entities and event_type via backend STT endpoint
      const response = await fetch(`${API_BASE_URL}/api/stt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: text }),
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Extraction failed with status ${response.status}`);
      }

      const data = (await response.json()) as {
        transcript?: string;
        event_type?: MemoryEvent["event_type"];
        entities?: MemoryEvent["entities"];
      };

      // 2. Ingest the memory as a caregiver note
      await ingestMemoryEvent({
        patient_id: patientId,
        source: "caregiver_note",
        recorded_at: new Date().toISOString(),
        event_type: data.event_type ?? "general",
        transcript: data.transcript ?? text,
        entities: data.entities,
        verification: { status: "unverified" }, // It will show up in their dashboard
      });

      setText("");
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save observation.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-100 p-4">
          <h2 className="text-lg font-semibold text-slate-900">Add Caregiver Observation</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            disabled={isSubmitting}
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4">
          {error && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">
              {error}
            </div>
          )}

          <div className="mb-4">
            <label htmlFor="observation-text" className="mb-1 block text-sm font-medium text-slate-700">
              Observation Details
            </label>
            <textarea
              id="observation-text"
              className="w-full rounded-xl border border-slate-300 p-3 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              rows={4}
              placeholder="e.g., Patient was feeling anxious this morning."
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={isSubmitting}
              autoFocus
            />
            <p className="mt-1.5 text-xs text-slate-500">
              This note will be automatically analyzed and added to the patient&apos;s memory graph.
            </p>
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!text.trim() || isSubmitting}
              className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {isSubmitting ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Plus className="h-4 w-4" aria-hidden="true" />
              )}
              Save Observation
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
