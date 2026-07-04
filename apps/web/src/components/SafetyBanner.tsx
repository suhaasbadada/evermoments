import { AlertTriangle } from "lucide-react";
import type { MemoryWarning } from "@/lib/memoryClient";

interface SafetyBannerProps {
  warning: MemoryWarning;
}

export function SafetyBanner({ warning }: SafetyBannerProps) {
  return (
    <div
      role="alert"
      className="app-card flex gap-2.5 border-orange-300 bg-orange-50/95 p-3.5"
    >
      <AlertTriangle
        className="mt-0.5 h-5 w-5 shrink-0 text-orange-600"
        aria-hidden="true"
      />
      <div>
        <p className="text-sm font-semibold text-orange-900">Safety Notice</p>
        <p className="mt-1 text-xs leading-relaxed text-orange-900/85">
          {warning.message}
        </p>
        {warning.type && (
          <p className="mt-1 text-[11px] text-orange-700 capitalize">
            Type: {warning.type.replace(/_/g, " ")}
          </p>
        )}
      </div>
    </div>
  );
}
