"use client";

import { useEffect, useState } from "react";

import { pingApi } from "@/lib/api";

type PingState =
  | { status: "loading"; message: string }
  | { status: "success"; message: string }
  | { status: "error"; message: string };

export function PingStatus() {
  const [state, setState] = useState<PingState>({
    status: "loading",
    message: "Checking API connection...",
  });

  useEffect(() => {
    pingApi()
      .then((message) => {
        setState({
          status: "success",
          message: `API responded: ${message}`,
        });
      })
      .catch((error) => {
        setState({
          status: "error",
          message: `Unable to reach API: ${error instanceof Error ? error.message : "unknown error"}`,
        });
      });
  }, []);

  const colorClass =
    state.status === "success"
      ? "text-emerald-700 bg-emerald-100 border-emerald-300"
      : state.status === "error"
        ? "text-red-700 bg-red-100 border-red-300"
        : "text-amber-700 bg-amber-100 border-amber-300";

  return (
    <p className={`w-full rounded-lg border px-4 py-3 text-sm ${colorClass}`}>
      {state.message}
    </p>
  );
}
