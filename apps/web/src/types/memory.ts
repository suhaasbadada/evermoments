// Mirrors the Module 3 (Cognee Memory Engine) integration contract, §6.
// Caregiver verification statuses match §6.1's `verification.status` enum exactly.
// "Duplicate" was dropped from the original 5-button mock — Japit's contract only
// has these four, and the team agreed "Incorrect" covers that case.
export type VerificationStatus =
  | "unverified"
  | "confirmed"
  | "incorrect"
  | "needs_check"
  | "safety_critical";

export type EventType =
  | "medication_intake"
  | "object_location"
  | "person_mention"
  | "appointment"
  | "routine"
  | "observation"
  | "general";

// One item from MemoryAnswer.results[] (§6.2), reused as-is for /memory/list.
export interface MemoryResult {
  fact: string;
  node_type: string;
  recorded_at: string; // ISO-8601
  source: string;
  verification_status: VerificationStatus;
  verified_by: string | null;
  note_id: string;
  event_type?: EventType;
  // Not yet in the confirmed contract — /memory/list only returns results[].
  // If Japit adds per-item warnings later, this is picked up with no UI changes.
  warning?: {
    type: string;
    message: string;
    related_note_ids: string[];
  };
}

export interface MemoryListParams {
  patient_id: string;
  filters?: {
    event_type?: EventType;
    verification_status?: VerificationStatus;
    date_from?: string;
    date_to?: string;
  };
  sort?: "recorded_at_desc";
  limit?: number;
}

export interface ConsolidateResult {
  ok: boolean;
  run_id: string;
  // Shape unconfirmed with Japit — see lib/memory/api.ts note.
  patterns?: string[];
}

export interface MemoryClient {
  listMemories(params: MemoryListParams): Promise<MemoryResult[]>;
  verifyMemory(
    patientId: string,
    eventId: string,
    status: VerificationStatus,
    by: string,
  ): Promise<{ ok: boolean }>;
  consolidateMemories(patientId: string): Promise<ConsolidateResult>;
  deleteMemory(patientId: string, eventId?: string): Promise<{ ok: boolean }>;
}
