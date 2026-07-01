import { HeartPulse } from "lucide-react";

import { PingStatus } from "@/components/ping-status";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-100 px-6 py-10">
      <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
        <div className="flex items-center gap-3">
          <HeartPulse className="h-8 w-8 text-rose-600" aria-hidden="true" />
          <h1 className="text-2xl font-semibold text-slate-900">Evermoments Platform</h1>
        </div>
        <p className="text-slate-600">
          Frontend and API are wired together. This status card calls
          <span className="font-medium text-slate-900"> /api/ping</span> from the browser.
        </p>
        <PingStatus />
      </main>
    </div>
  );
}
