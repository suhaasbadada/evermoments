import { NextRequest, NextResponse } from "next/server";
import { getPatientEvents, deriveFact } from "@/lib/mockStore";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ patient_id: string }> }
) {
  const { patient_id } = await params;
  const events = getPatientEvents(patient_id);

  // Build a simple graph: one node per event, edges when events share entities
  const nodes = events.map((e) => ({
    id: e.event_id,
    label: deriveFact(e).slice(0, 60),
    type: e.event_type,
    recorded_at: e.recorded_at,
    verification_status: e.verification_status,
  }));

  const edges: { source: string; target: string; relation: string }[] = [];

  // Connect medication events that reference the same medication
  for (let i = 0; i < events.length; i++) {
    for (let j = i + 1; j < events.length; j++) {
      const a = events[i];
      const b = events[j];

      const aMeds = (a.entities.medications ?? []).map((m) => m.name.toLowerCase());
      const bMeds = (b.entities.medications ?? []).map((m) => m.name.toLowerCase());
      const sharedMed = aMeds.find((m) => bMeds.includes(m));
      if (sharedMed) {
        edges.push({ source: a.event_id, target: b.event_id, relation: `shared_medication:${sharedMed}` });
      }

      const aPeople = (a.entities.people ?? []).map((p) => p.name.toLowerCase());
      const bPeople = (b.entities.people ?? []).map((p) => p.name.toLowerCase());
      const sharedPerson = aPeople.find((p) => bPeople.includes(p));
      if (sharedPerson) {
        edges.push({ source: a.event_id, target: b.event_id, relation: `shared_person:${sharedPerson}` });
      }
    }
  }

  return NextResponse.json({ nodes, edges });
}
