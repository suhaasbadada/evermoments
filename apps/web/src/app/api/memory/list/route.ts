import { NextRequest, NextResponse } from "next/server";
import { getPatientEvents, toMemoryResult } from "@/lib/mockStore";
import type { StoredEvent } from "@/lib/mockStore";
import type { EventType, VerificationStatus } from "@/lib/memoryClient";

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

  const sort =
    (body.sort as "recorded_at_desc" | "recorded_at_asc") ?? "recorded_at_desc";
  const limit =
    typeof body.limit === "number" && body.limit >= 1 ? body.limit : undefined;

  const filters = (body.filters ?? {}) as {
    event_type?: EventType | null;
    verification_status?: VerificationStatus | null;
    date_from?: string | null;
    date_to?: string | null;
  };

  let events: StoredEvent[] = getPatientEvents(patientId);

  // Apply filters
  if (filters.event_type) {
    events = events.filter((e) => e.event_type === filters.event_type);
  }
  if (filters.verification_status) {
    events = events.filter(
      (e) => e.verification_status === filters.verification_status
    );
  }
  if (filters.date_from) {
    const from = Date.parse(filters.date_from);
    if (!isNaN(from)) {
      events = events.filter((e) => Date.parse(e.recorded_at) >= from);
    }
  }
  if (filters.date_to) {
    const to = Date.parse(filters.date_to);
    if (!isNaN(to)) {
      events = events.filter((e) => Date.parse(e.recorded_at) <= to);
    }
  }

  // Sort
  events = [...events].sort((a, b) => {
    const diff =
      Date.parse(a.recorded_at) - Date.parse(b.recorded_at);
    return sort === "recorded_at_asc" ? diff : -diff;
  });

  // Limit
  if (limit !== undefined) {
    events = events.slice(0, limit);
  }

  return NextResponse.json({ results: events.map(toMemoryResult) });
}
