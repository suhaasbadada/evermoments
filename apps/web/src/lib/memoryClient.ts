const MEMORY_API_BASE =
  process.env.NEXT_PUBLIC_MEMORY_API_URL ?? "http://localhost:8000";

// ── Domain types ────────────────────────────────────────────────────────────

export type SourceType =
  | "voice_note"
  | "caregiver_note"
  | "document"
  | "manual";

export type EventType =
  | "medication_intake"
  | "object_location"
  | "person_mention"
  | "appointment"
  | "routine"
  | "observation"
  | "general";

export type VerificationStatus =
  | "unverified"
  | "confirmed"
  | "incorrect"
  | "needs_check"
  | "safety_critical";

export interface Medication {
  name: string;
  form?: string | null;
}

export interface Person {
  name: string;
  relationship?: string | null;
}

export interface Place {
  name: string;
}

export interface ObjectItem {
  name: string;
  location?: string | null;
}

export interface Appointment {
  title: string;
  datetime?: string | null;
  doctor?: string | null;
}

export interface Entities {
  medications?: Medication[];
  people?: Person[];
  places?: Place[];
  objects?: ObjectItem[];
  appointments?: Appointment[];
  time_reference?: string | null;
}

export interface Verification {
  status?: VerificationStatus;
  by?: string | null;
  at?: string | null;
}

export interface MemoryEvent {
  patient_id: string;
  event_id?: string | null;
  source?: SourceType;
  recorded_at: string; // ISO-8601
  transcript?: string | null;
  event_type: EventType;
  entities?: Entities;
  verification?: Verification;
}

export interface QueryRequest {
  patient_id: string;
  query: string;
  top_k?: number;
}

export interface ListFilters {
  event_type?: EventType | null;
  verification_status?: VerificationStatus | null;
  date_from?: string | null;
  date_to?: string | null;
}

export interface ListRequest {
  patient_id: string;
  filters?: ListFilters | null;
  sort?: "recorded_at_desc" | "recorded_at_asc";
  limit?: number | null;
}

export interface VerifyRequest {
  patient_id: string;
  event_id: string;
  status: VerificationStatus;
  by?: string | null;
}

export interface ConsolidateRequest {
  patient_id: string;
}

export interface ForgetRequest {
  patient_id: string;
  event_id?: string | null;
}

// ── Response types ───────────────────────────────────────────────────────────

export interface HealthResponse {
  backend: string;
  status: string;
  mode?: "local" | "cloud";
}

export interface MemoryWarning {
  type: string;
  message: string;
  related_note_ids: string[];
}

export interface IngestResponse {
  event_id: string;
  status: string;
  warning?: MemoryWarning; // single optional warning, not a list
}

export interface MemoryResult {
  fact: string;
  node_type: string;
  recorded_at: string;
  source: SourceType;
  verification_status: VerificationStatus;
  verified_by?: string | null;
  note_id: string;
}

export interface MemoryAnswer {
  query: string;
  answer: string;
  results: MemoryResult[];
  warnings: MemoryWarning[];
}

export interface ListResponse {
  results: MemoryResult[];
}

export interface VerifyResponse {
  updated: boolean;
}

export interface ConsolidateResponse {
  run_id: string;
  patterns: object[];
}

export interface ForgetResponse {
  forgot: boolean;
}

export interface GraphResponse {
  nodes: object[];
  edges: object[];
}

export interface SeedResponse {
  patient_id: string;
  loaded: number;
}

// ── Internal fetch helper ────────────────────────────────────────────────────

async function memoryFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${MEMORY_API_BASE}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      ...options,
    });
  } catch (err) {
    throw new Error(
      `Memory API unreachable at ${url}: ${err instanceof Error ? err.message : String(err)}`
    );
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Memory API ${res.status} from ${path}: ${body}`);
  }
  return (await res.json()) as T;
}

// ── Public client functions ──────────────────────────────────────────────────

export function checkMemoryHealth(): Promise<HealthResponse> {
  return memoryFetch<HealthResponse>("/api/memory/health");
}

export function ingestMemoryEvent(event: MemoryEvent): Promise<IngestResponse> {
  return memoryFetch<IngestResponse>("/api/memory/events", {
    method: "POST",
    body: JSON.stringify(event),
  });
}

export function queryMemory(
  patientId: string,
  query: string,
  topK?: number
): Promise<MemoryAnswer> {
  return memoryFetch<MemoryAnswer>("/api/memory/query", {
    method: "POST",
    body: JSON.stringify({ patient_id: patientId, query, top_k: topK }),
  });
}

export function listMemories(
  patientId: string,
  filters?: ListFilters,
  sort?: "recorded_at_desc" | "recorded_at_asc",
  limit?: number
): Promise<ListResponse> {
  return memoryFetch<ListResponse>("/api/memory/list", {
    method: "POST",
    body: JSON.stringify({ patient_id: patientId, filters, sort, limit }),
  });
}

export function verifyMemory(
  patientId: string,
  eventId: string,
  status: VerificationStatus,
  by?: string
): Promise<VerifyResponse> {
  return memoryFetch<VerifyResponse>("/api/memory/verify", {
    method: "POST",
    body: JSON.stringify({ patient_id: patientId, event_id: eventId, status, by }),
  });
}

export function consolidateMemory(patientId: string): Promise<ConsolidateResponse> {
  return memoryFetch<ConsolidateResponse>("/api/memory/consolidate", {
    method: "POST",
    body: JSON.stringify({ patient_id: patientId }),
  });
}

export function forgetMemory(
  patientId: string,
  eventId?: string
): Promise<ForgetResponse> {
  return memoryFetch<ForgetResponse>("/api/memory/forget", {
    method: "POST",
    body: JSON.stringify({ patient_id: patientId, event_id: eventId }),
  });
}

export function getMemoryGraph(patientId: string): Promise<GraphResponse> {
  return memoryFetch<GraphResponse>(`/api/memory/graph/${patientId}`);
}

export function seedPatient(patientId?: string): Promise<SeedResponse> {
  return memoryFetch<SeedResponse>("/api/memory/seed", {
    method: "POST",
    body: JSON.stringify(patientId ? { patient_id: patientId } : {}),
  });
}
