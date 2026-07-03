import { AlertTriangle } from "lucide-react";
import type { MemoryWarning } from "@/lib/memoryClient";

interface SafetyBannerProps {
  warning: MemoryWarning;
}

export function SafetyBanner({ warning }: SafetyBannerProps) {
  return (
    <div
      role="alert"
      className="flex gap-3 rounded-2xl border-2 border-orange-400 bg-orange-50 p-5 shadow-sm"
    >
      <AlertTriangle
        className="mt-0.5 h-7 w-7 shrink-0 text-orange-600"
        aria-hidden="true"
      />
      <div>
        <p className="text-lg font-bold text-orange-900">Safety Notice</p>
        <p className="mt-1 text-base leading-relaxed text-orange-800">
          {warning.message}
        </p>
        {warning.type && (
          <p className="mt-1 text-sm text-orange-600 capitalize">
            Type: {warning.type.replace(/_/g, " ")}
          </p>
        )}
      </div>
    </div>
  );
}
