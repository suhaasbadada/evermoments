import { NextRequest, NextResponse } from "next/server";
import { getPatientEvents } from "@/lib/mockStore";

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

  const events = getPatientEvents(patientId);

  // Mock: detect repeated medication events as a pattern
  const medEvents = events.filter((e) => e.event_type === "medication_intake");
  const locEvents = events.filter((e) => e.event_type === "object_location");

  const patterns: object[] = [];
  if (medEvents.length > 1) {
    patterns.push({
      type: "routine",
      description: `${medEvents.length} medication intake events found`,
      event_ids: medEvents.map((e) => e.event_id),
    });
  }
  if (locEvents.length > 1) {
    patterns.push({
      type: "object_tracking",
      description: `${locEvents.length} object location events found`,
      event_ids: locEvents.map((e) => e.event_id),
    });
  }

  return NextResponse.json({
    run_id: crypto.randomUUID(),
    patterns,
  });
}
