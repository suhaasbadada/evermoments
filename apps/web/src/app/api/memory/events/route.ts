import { NextRequest, NextResponse } from "next/server";
import { addEvent, checkWarning } from "@/lib/mockStore";
import type { StoredEvent } from "@/lib/mockStore";
import type { SourceType, EventType, VerificationStatus } from "@/lib/memoryClient";

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const patientId = body.patient_id as string | undefined;
  const recordedAt = body.recorded_at as string | undefined;
  const eventType = body.event_type as EventType | undefined;

  if (!patientId || !recordedAt || !eventType) {
    return NextResponse.json(
      { error: "patient_id, recorded_at, and event_type are required" },
      { status: 422 }
    );
  }

  // Validate ISO-8601
  if (isNaN(Date.parse(recordedAt))) {
    return NextResponse.json(
      { error: "recorded_at must be a valid ISO-8601 datetime" },
      { status: 422 }
    );
  }

  const verification = (body.verification ?? {}) as {
    status?: VerificationStatus;
    by?: string | null;
    at?: string | null;
  };

  const event: StoredEvent = {
    event_id: body.event_id as string ?? crypto.randomUUID(),
    patient_id: patientId,
    source: (body.source as SourceType) ?? "voice_note",
    recorded_at: recordedAt,
    transcript: (body.transcript as string | null) ?? null,
    event_type: eventType,
    entities: (body.entities as StoredEvent["entities"]) ?? {},
    verification_status: verification.status ?? "unverified",
    verified_by: verification.by ?? null,
    verified_at: verification.at ?? null,
  };

  addEvent(event);

  const warning = checkWarning(event);

  return NextResponse.json({
    event_id: event.event_id,
    status: "stored",
    ...(warning !== undefined ? { warning } : {}),
  });
}
