"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { DEFAULT_PATIENT_ID } from "@/lib/memory/constants";

type PatientContextType = {
  patientId: string;
  setPatientId: (id: string) => void;
};

const PatientContext = createContext<PatientContextType | undefined>(undefined);

export function PatientProvider({ children }: { children: React.ReactNode }) {
  const [patientId, setPatientIdState] = useState<string>(DEFAULT_PATIENT_ID);

  useEffect(() => {
    const stored = localStorage.getItem("evermoments_patient_id");
    if (stored) {
      setPatientIdState(stored);
    }

    const handleStorage = (e: StorageEvent) => {
      if (e.key === "evermoments_patient_id" && e.newValue) {
        setPatientIdState(e.newValue);
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const setPatientId = (id: string) => {
    setPatientIdState(id);
    localStorage.setItem("evermoments_patient_id", id);
  };

  return (
    <PatientContext.Provider value={{ patientId, setPatientId }}>
      {children}
    </PatientContext.Provider>
  );
}

export function usePatient() {
  const context = useContext(PatientContext);
  if (context === undefined) {
    throw new Error("usePatient must be used within a PatientProvider");
  }
  return context;
}
