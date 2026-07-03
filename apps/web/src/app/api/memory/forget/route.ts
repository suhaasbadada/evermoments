import { NextRequest, NextResponse } from "next/server";
import { removeEvent, removePatientEvents } from "@/lib/mockStore";

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const patientId = body.patient_id as string | undefined;
  if (!patientId) {
    return NextResponse.json({ error: "patient_id is required" }, { status: 422 });
  }

  const eventId = (body.event_id as string | null) ?? null;

  let forgot: boolean;
  if (eventId) {
    forgot = removeEvent(eventId);
  } else {
    // No event_id → forget all memories for this patient
    const removed = removePatientEvents(patientId);
    forgot = removed > 0;
  }

  return NextResponse.json({ forgot });
}
