import type {
  ConsolidateResult,
  MemoryClient,
  MemoryListParams,
  MemoryResult,
  VerificationStatus,
} from "@/types/memory";

// In-memory fixture mirroring Japit's seed_dummy_data.py for patient p_001:
// a wallet location note, a deliberate blue-pill double-dose, Ravi's Sunday
// visit, and an upcoming appointment. Lets the dashboard be built and
// demoed before /memory/* exists on the backend — swap to lib/memory/api.ts
// with zero component changes once it does.

function atToday(hours: number, minutes: number): string {
  const d = new Date();
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
}

function daysAgo(days: number, hours: number, minutes: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
}

let store: MemoryResult[] = [
  {
    note_id: "evt_wallet1",
    fact: "wallet located near the TV",
    node_type: "Object",
    event_type: "object_location",
    recorded_at: atToday(16, 30),
    source: "voice_note",
    verification_status: "unverified",
    verified_by: null,
  },
  {
    note_id: "evt_8f2a",
    fact: "blue pill taken after breakfast",
    node_type: "IntakeEvent",
    event_type: "medication_intake",
    recorded_at: atToday(8, 30),
    source: "voice_note",
    verification_status: "unverified",
    verified_by: null,
  },
  {
    note_id: "evt_9c11",
    fact: "blue pill taken",
    node_type: "IntakeEvent",
    event_type: "medication_intake",
    recorded_at: atToday(10, 45),
    source: "voice_note",
    verification_status: "safety_critical",
    verified_by: null,
    warning: {
      type: "possible_double_dose",
      message: "Blue pill was already recorded as taken at 08:30 today (unverified).",
      related_note_ids: ["evt_8f2a", "evt_9c11"],
    },
  },
  {
    note_id: "evt_ravi1",
    fact: "Ravi (son) visited",
    node_type: "Person",
    event_type: "person_mention",
    recorded_at: daysAgo(1, 17, 0),
    source: "voice_note",
    verification_status: "confirmed",
    verified_by: "Ravi",
  },
  {
    note_id: "evt_appt1",
    fact: "Neurology appointment scheduled",
    node_type: "Appointment",
    event_type: "appointment",
    recorded_at: daysAgo(3, 9, 0),
    source: "voice_note",
    verification_status: "unverified",
    verified_by: null,
  },
  {
    note_id: "evt_obs1",
    fact: "Felt confused after dinner",
    node_type: "Note",
    event_type: "observation",
    recorded_at: daysAgo(4, 20, 15),
    source: "voice_note",
    verification_status: "confirmed",
    verified_by: "Ravi",
  },
  {
    note_id: "evt_obs2",
    fact: "Felt confused after dinner",
    node_type: "Note",
    event_type: "observation",
    recorded_at: daysAgo(10, 20, 40),
    source: "voice_note",
    verification_status: "confirmed",
    verified_by: "Ravi",
  },
];

function delay<T>(value: T, ms = 150): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

export const mockMemoryClient: MemoryClient = {
  async listMemories(params: MemoryListParams): Promise<MemoryResult[]> {
    let results = store.filter(() => true);

    if (params.filters?.event_type) {
      results = results.filter((r) => r.event_type === params.filters?.event_type);
    }
    if (params.filters?.verification_status) {
      results = results.filter(
        (r) => r.verification_status === params.filters?.verification_status,
      );
    }
    if (params.filters?.date_from) {
      const from = new Date(params.filters.date_from).getTime();
      results = results.filter((r) => new Date(r.recorded_at).getTime() >= from);
    }
    if (params.filters?.date_to) {
      const to = new Date(params.filters.date_to).getTime();
      results = results.filter((r) => new Date(r.recorded_at).getTime() <= to);
    }

    results = [...results].sort(
      (a, b) => new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime(),
    );

    if (params.limit) {
      results = results.slice(0, params.limit);
    }

    return delay(results);
  },

  async verifyMemory(
    _patientId: string,
    eventId: string,
    status: VerificationStatus,
    by: string,
  ): Promise<{ ok: boolean }> {
    store = store.map((r) =>
      r.note_id === eventId ? { ...r, verification_status: status, verified_by: by } : r,
    );
    return delay({ ok: true });
  },

  async consolidateMemories(_patientId: string): Promise<ConsolidateResult> {
    return delay({
      ok: true,
      run_id: `run_${Date.now()}`,
      patterns: ["Repeated evening confusion noted across the last 3 days"],
    });
  },

  async deleteMemory(_patientId: string, eventId?: string): Promise<{ ok: boolean }> {
    store = eventId ? store.filter((r) => r.note_id !== eventId) : [];
    return delay({ ok: true });
  },
};
