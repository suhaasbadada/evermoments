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
    className: "bg-slate-100 text-slate-700 border-slate-300",
  },
  confirmed: {
    label: "Confirmed",
    className: "bg-green-100 text-green-800 border-green-300",
  },
  incorrect: {
    label: "Marked incorrect",
    className: "bg-red-100 text-red-800 border-red-300",
  },
  needs_check: {
    label: "Needs checking",
    className: "bg-yellow-100 text-yellow-800 border-yellow-300",
  },
  safety_critical: {
    label: "⚠ Safety critical",
    className: "bg-orange-100 text-orange-900 border-orange-400 font-semibold",
  },
};

export function VerificationBadge({ status, by }: VerificationBadgeProps) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-0.5 text-sm ${config.className}`}
    >
      {config.label}
      {by ? ` · by ${by}` : ""}
    </span>
  );
}
