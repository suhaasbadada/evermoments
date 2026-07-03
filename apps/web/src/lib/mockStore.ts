/**
 * mockStore.ts — in-memory storage for the Next.js mock API routes.
 *
 * Module-level state resets on server restart. That is expected and fine for
 * a local dev mock. Replace the whole apps/web/src/app/api/memory tree with
 * a real backend by updating NEXT_PUBLIC_MEMORY_API_URL — zero client changes.
 */

import type {
  SourceType,
  EventType,
  VerificationStatus,
  Entities,
  MemoryWarning,
} from "@/lib/memoryClient";

// ── Internal record shape ────────────────────────────────────────────────────

export interface StoredEvent {
  event_id: string;
  patient_id: string;
  source: SourceType;
  recorded_at: string; // ISO-8601
  transcript: string | null;
  event_type: EventType;
  entities: Entities;
  verification_status: VerificationStatus;
  verified_by: string | null;
  verified_at: string | null;
}

// ── The store ────────────────────────────────────────────────────────────────

const eventStore: StoredEvent[] = [];

export function getAllEvents(): StoredEvent[] {
  return eventStore;
}

export function getPatientEvents(patientId: string): StoredEvent[] {
  return eventStore.filter((e) => e.patient_id === patientId);
}

export function addEvent(event: StoredEvent): void {
  eventStore.push(event);
}

export function findEventById(eventId: string): StoredEvent | undefined {
  return eventStore.find((e) => e.event_id === eventId);
}

export function updateVerification(
  eventId: string,
  status: VerificationStatus,
  by: string | null
): boolean {
  const event = findEventById(eventId);
  if (!event) return false;
  event.verification_status = status;
  event.verified_by = by;
  event.verified_at = new Date().toISOString();
  return true;
}

export function removeEvent(eventId: string): boolean {
  const idx = eventStore.findIndex((e) => e.event_id === eventId);
  if (idx === -1) return false;
  eventStore.splice(idx, 1);
  return true;
}

export function removePatientEvents(patientId: string): number {
  let removed = 0;
  let i = eventStore.length;
  while (i--) {
    if (eventStore[i].patient_id === patientId) {
      eventStore.splice(i, 1);
      removed++;
    }
  }
  return removed;
}

// ── Fact derivation ──────────────────────────────────────────────────────────

export function deriveFact(event: StoredEvent): string {
  if (event.transcript) return event.transcript;

  const parts: string[] = [];
  const e = event.entities;

  if (e.objects?.length) {
    parts.push(
      e.objects
        .map((o) => (o.location ? `${o.name} is ${o.location}` : o.name))
        .join(", ")
    );
  }
  if (e.medications?.length) {
    parts.push(`Took ${e.medications.map((m) => m.name).join(", ")}`);
  }
  if (e.people?.length) {
    parts.push(
      e.people
        .map((p) => (p.relationship ? `${p.name} (${p.relationship})` : p.name))
        .join(", ")
    );
  }
  if (e.appointments?.length) {
    parts.push(e.appointments.map((a) => a.title).join(", "));
  }
  if (e.time_reference) parts.push(e.time_reference);

  return parts.join("; ") || `${event.event_type.replace(/_/g, " ")} event`;
}

// ── MemoryResult converter ───────────────────────────────────────────────────

export function toMemoryResult(event: StoredEvent) {
  return {
    fact: deriveFact(event),
    node_type: event.event_type,
    recorded_at: event.recorded_at,
    source: event.source,
    verification_status: event.verification_status,
    verified_by: event.verified_by,
    note_id: event.event_id,
  };
}

// ── Warning detection (medication double-dose) ───────────────────────────────

export function checkWarning(event: StoredEvent): MemoryWarning | undefined {
  if (event.event_type !== "medication_intake") return undefined;

  const meds = event.entities.medications ?? [];
  if (meds.length === 0) return undefined;

  const windowMs = 8 * 60 * 60 * 1000; // 8-hour window
  const eventTime = new Date(event.recorded_at).getTime();
  const medNames = meds.map((m) => m.name.toLowerCase());

  const priorDose = eventStore.find(
    (e) =>
      e.patient_id === event.patient_id &&
      e.event_id !== event.event_id &&
      e.event_type === "medication_intake" &&
      Math.abs(new Date(e.recorded_at).getTime() - eventTime) < windowMs &&
      (e.entities.medications ?? []).some((m) =>
        medNames.includes(m.name.toLowerCase())
      )
  );

  if (!priorDose) return undefined;

  return {
    type: "double_dose",
    message: `You may have already taken ${meds.map((m) => m.name).join(", ")} recently. Please check with a caregiver before taking more.`,
    related_note_ids: [priorDose.event_id],
  };
}

// ── Keyword search ───────────────────────────────────────────────────────────

export function searchEvents(
  patientId: string,
  query: string,
  topK: number
): StoredEvent[] {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  const events = getPatientEvents(patientId);

  const scored = events.map((e) => {
    const text = [
      deriveFact(e),
      e.event_type,
      e.entities.people?.map((p) => p.name).join(" ") ?? "",
      e.entities.medications?.map((m) => m.name).join(" ") ?? "",
      e.entities.objects?.map((o) => `${o.name} ${o.location ?? ""}`).join(" ") ?? "",
      e.entities.appointments?.map((a) => a.title).join(" ") ?? "",
    ]
      .join(" ")
      .toLowerCase();

    const score = terms.reduce((s, t) => s + (text.includes(t) ? 1 : 0), 0);
    return { event: e, score };
  });

  return scored
    .filter((x) => x.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return (
        new Date(b.event.recorded_at).getTime() -
        new Date(a.event.recorded_at).getTime()
      );
    })
    .slice(0, topK)
    .map((x) => x.event);
}

// ── Natural-language answer synthesis ───────────────────────────────────────

export function synthesizeAnswer(
  query: string,
  results: StoredEvent[]
): string {
  if (results.length === 0) {
    return "I couldn't find anything about that in your memories. Try asking a different way.";
  }

  const top = results[0];
  const q = query.toLowerCase();

  if (q.includes("where") && top.event_type === "object_location") {
    const obj = top.entities.objects?.[0];
    if (obj?.location) return `Your ${obj.name} is ${obj.location}.`;
  }

  if (
    (q.includes("medicine") ||
      q.includes("pill") ||
      q.includes("medication") ||
      q.includes("tablet")) &&
    top.event_type === "medication_intake"
  ) {
    const medName =
      top.entities.medications?.map((m) => m.name).join(", ") ?? "medication";
    const timeRef = top.entities.time_reference
      ? ` ${top.entities.time_reference}`
      : " recently";
    return `Yes, you took your ${medName}${timeRef}.`;
  }

  if (
    (q.includes("who") || q.includes("visit")) &&
    top.event_type === "person_mention"
  ) {
    const person = top.entities.people?.[0];
    if (person) {
      const rel = person.relationship ? ` (your ${person.relationship})` : "";
      return `${person.name}${rel} was mentioned in your recent memories.`;
    }
  }

  if (q.includes("doctor") || q.includes("appointment")) {
    const appt = top.entities.appointments?.[0];
    if (appt) {
      return `You have: ${appt.title}${appt.datetime ? ` on ${appt.datetime}` : ""}${appt.doctor ? ` with ${appt.doctor}` : ""}.`;
    }
  }

  return deriveFact(top);
}

// ── Seed data ────────────────────────────────────────────────────────────────

type SeedTemplate = Omit<StoredEvent, "event_id" | "patient_id">;

const SEED_TEMPLATES: SeedTemplate[] = [
  {
    source: "voice_note",
    recorded_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    transcript: "I kept my wallet in the top drawer of my dresser.",
    event_type: "object_location",
    entities: {
      objects: [{ name: "wallet", location: "top drawer of the dresser" }],
    },
    verification_status: "confirmed",
    verified_by: "Maya",
    verified_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
  },
  {
    source: "voice_note",
    recorded_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    transcript: "I took my morning blood pressure pill after breakfast.",
    event_type: "medication_intake",
    entities: {
      medications: [{ name: "blood pressure pill", form: "tablet" }],
      time_reference: "after breakfast",
    },
    verification_status: "confirmed",
    verified_by: "Maya",
    verified_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
  },
  {
    source: "caregiver_note",
    recorded_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    transcript: "My daughter Maya came to visit and we had tea together.",
    event_type: "person_mention",
    entities: {
      people: [{ name: "Maya", relationship: "daughter" }],
    },
    verification_status: "unverified",
    verified_by: null,
    verified_at: null,
  },
  {
    source: "caregiver_note",
    recorded_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    transcript: "Doctor Sharma appointment on Thursday at 10am.",
    event_type: "appointment",
    entities: {
      appointments: [
        {
          title: "Doctor Sharma",
          datetime: "Thursday 10:00 AM",
          doctor: "Dr. Sharma",
        },
      ],
    },
    verification_status: "needs_check",
    verified_by: null,
    verified_at: null,
  },
  {
    source: "voice_note",
    recorded_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    transcript: "My reading glasses are on the side table next to the sofa.",
    event_type: "object_location",
    entities: {
      objects: [{ name: "reading glasses", location: "side table next to the sofa" }],
    },
    verification_status: "unverified",
    verified_by: null,
    verified_at: null,
  },
];

export function seedPatientData(patientId: string): number {
  // Deduplicate by transcript so re-seeding does not double entries
  const existingTranscripts = new Set(
    getPatientEvents(patientId).map((e) => e.transcript)
  );

  const toAdd = SEED_TEMPLATES.filter(
    (t) => !existingTranscripts.has(t.transcript)
  ).map((t) => ({
    ...t,
    patient_id: patientId,
    event_id: crypto.randomUUID(),
  }));

  eventStore.push(...toAdd);
  return toAdd.length;
}
