import type { Metadata } from "next";

import { CaregiverDashboard } from "@/components/caregiver/caregiver-dashboard";

export const metadata: Metadata = {
  title: "Caregiver Dashboard | Evermoments",
};

export default function CaregiverPage() {
  return (
    <div className="min-h-screen bg-slate-100 px-6 py-10">
      <main className="mx-auto w-full max-w-3xl rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
        <CaregiverDashboard />
      </main>
    </div>
  );
}
