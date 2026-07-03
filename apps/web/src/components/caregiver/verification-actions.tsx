import type { VerificationStatus } from "@/types/memory";
import { VERIFICATION_ACTIONS, VERIFICATION_LABELS } from "@/lib/memory/labels";

export function VerificationActions({
  currentStatus,
  disabled,
  onVerify,
}: {
  currentStatus: VerificationStatus;
  disabled?: boolean;
  onVerify: (status: VerificationStatus) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {VERIFICATION_ACTIONS.map((status) => {
        const isActive = status === currentStatus;
        return (
          <button
            key={status}
            type="button"
            disabled={disabled || isActive}
            onClick={() => onVerify(status)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed ${
              isActive
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-300 bg-white text-slate-700 hover:border-slate-400 disabled:opacity-50"
            }`}
          >
            {VERIFICATION_LABELS[status]}
          </button>
        );
      })}
    </div>
  );
}
