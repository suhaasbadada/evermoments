import { NextRequest, NextResponse } from "next/server";
import { seedPatientData } from "@/lib/mockStore";

export async function POST(request: NextRequest) {
  // Body is optional (SeedRequest?)
  let patientId = "p_001"; // default
  try {
    const body = (await request.json()) as Record<string, unknown>;
    if (typeof body.patient_id === "string" && body.patient_id) {
      patientId = body.patient_id;
    }
  } catch {
    // Empty body is fine — use default patient_id
  }

  const loaded = seedPatientData(patientId);

  return NextResponse.json({ patient_id: patientId, loaded });
}
