"use client";

import { usePatient } from "./patient-context";
import { UserCircle } from "lucide-react";

export function PatientSwitcher() {
  const { patientId, setPatientId } = usePatient();

  return (
    <div className="fixed bottom-3 right-3 z-50 flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-1.5 shadow-md">
      <UserCircle className="h-5 w-5 text-slate-500" />
      <select
        value={patientId}
        onChange={(e) => setPatientId(e.target.value)}
        className="bg-transparent text-sm font-medium text-slate-700 outline-none"
      >
        <option value="p_001">Patient p_001</option>
        <option value="p_002">Patient p_002</option>
        <option value="p_003">Patient p_003</option>
      </select>
    </div>
  );
}
