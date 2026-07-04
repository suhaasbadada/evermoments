import { AlertTriangle, Calendar, FileText, MapPin, Pill, Trash2, User } from "lucide-react";

import { formatRecordedAt } from "@/lib/memory/format";
import { VERIFICATION_BADGE_CLASSES, VERIFICATION_LABELS } from "@/lib/memory/labels";
import type { EventType, MemoryResult, VerificationStatus } from "@/types/memory";

import { VerificationActions } from "./verification-actions";

const EVENT_ICONS: Record<EventType, typeof Pill> = {
  medication_intake: Pill,
  object_location: MapPin,
  person_mention: User,
  appointment: Calendar,
  routine: FileText,
  observation: FileText,
  general: FileText,
};

export function MemoryCard({
  memory,
  busy,
  onVerify,
  onDelete,
}: {
  memory: MemoryResult;
  busy?: boolean;
  onVerify: (status: VerificationStatus) => void;
  onDelete: () => void;
}) {
  const Icon = EVENT_ICONS[memory.event_type ?? "general"];

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Icon className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
          <div>
            <p className="font-medium text-slate-900">{memory.fact}</p>
            <p className="text-xs text-slate-500">
              {formatRecordedAt(memory.recorded_at)} · {memory.source}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full border px-2 py-0.5 text-xs font-medium ${VERIFICATION_BADGE_CLASSES[memory.verification_status]}`}
          >
            {VERIFICATION_LABELS[memory.verification_status]}
            {memory.verified_by ? ` · ${memory.verified_by}` : ""}
          </span>
          <button
            type="button"
            onClick={onDelete}
            aria-label="Delete memory"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      {memory.warning && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{memory.warning.message}</span>
        </div>
      )}

      <VerificationActions
        currentStatus={memory.verification_status}
        disabled={busy}
        onVerify={onVerify}
      />
    </div>
  );
}
