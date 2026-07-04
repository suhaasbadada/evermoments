import type { VerificationStatus } from "@/lib/memoryClient";

interface VerificationBadgeProps {
  status: VerificationStatus;
  by?: string | null;
}

const STATUS_CONFIG: Record<
  VerificationStatus,
  { label: string; className: string }
> = {
  unverified: {
    label: "Not yet checked",
    className: "bg-slate-100/90 text-slate-700 border-slate-200",
  },
  confirmed: {
    label: "Confirmed",
    className: "bg-emerald-100/90 text-emerald-800 border-emerald-200",
  },
  incorrect: {
    label: "Marked incorrect",
    className: "bg-rose-100/90 text-rose-800 border-rose-200",
  },
  needs_check: {
    label: "Needs checking",
    className: "bg-amber-100/90 text-amber-800 border-amber-200",
  },
  safety_critical: {
    label: "⚠ Safety critical",
    className: "bg-orange-100 text-orange-900 border-orange-300 font-semibold",
  },
};

export function VerificationBadge({ status, by }: VerificationBadgeProps) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] ${config.className}`}
    >
      {config.label}
      {by ? ` · by ${by}` : ""}
    </span>
  );
}
