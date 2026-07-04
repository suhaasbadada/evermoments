"use client";

import { useEffect, useState } from "react";
import { checkMemoryHealth } from "@/lib/memoryClient";
import type { HealthResponse } from "@/lib/memoryClient";

type Status = "checking" | "connected" | "disconnected";

export function HealthIndicator() {
  const [status, setStatus] = useState<Status>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    checkMemoryHealth()
      .then((h) => {
        setHealth(h);
        setStatus("connected");
      })
      .catch(() => {
        setStatus("disconnected");
      });
  }, []);

  const dotClass =
    status === "connected"
      ? "bg-green-500"
      : status === "disconnected"
        ? "bg-red-500"
        : "bg-yellow-400 animate-pulse";

  const label =
    status === "connected"
      ? `Memory connected${health?.mode ? ` · ${health.mode}` : ""}`
      : status === "disconnected"
        ? "Memory not connected"
        : "Checking memory…";

  return (
    <div
      className="flex items-center gap-1.5 rounded-full border border-teal-900/10 bg-white/80 px-2 py-1 text-[11px] text-teal-900/70 shadow-sm backdrop-blur"
      title={label}
      aria-label={label}
    >
      <span
        className={`inline-block h-2 w-2 rounded-full ${dotClass}`}
        aria-hidden="true"
      />
      <span className="hidden sm:inline">{label}</span>
    </div>
  );
}
