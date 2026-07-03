import { NextRequest, NextResponse } from "next/server";
import { updateVerification } from "@/lib/mockStore";
import type { VerificationStatus } from "@/lib/memoryClient";

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const patientId = body.patient_id as string | undefined;
  const eventId = body.event_id as string | undefined;
  const status = body.status as VerificationStatus | undefined;

  if (!patientId || !eventId || !status) {
    return NextResponse.json(
      { error: "patient_id, event_id, and status are required" },
      { status: 422 }
    );
  }

  const by = (body.by as string | null) ?? null;
  const updated = updateVerification(eventId, status, by);

  return NextResponse.json({ updated });
}
