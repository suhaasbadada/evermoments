import { API_BASE_URL } from "@/lib/api";
import type {
  ConsolidateResult,
  MemoryClient,
  MemoryListParams,
  MemoryResult,
  VerificationStatus,
} from "@/types/memory";

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`${path} failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const realMemoryClient: MemoryClient = {
  // POST /memory/list -> { results: MemoryResult[] }
  async listMemories(params: MemoryListParams): Promise<MemoryResult[]> {
    const data = await postJson<{ results: MemoryResult[] }>("/memory/list", params);
    return data.results ?? [];
  },

  // POST /memory/verify -> { updated: boolean }
  async verifyMemory(
    patientId: string,
    eventId: string,
    status: VerificationStatus,
    by: string,
  ): Promise<{ ok: boolean }> {
    const data = await postJson<{ updated: boolean }>("/memory/verify", {
      patient_id: patientId,
      event_id: eventId,
      status,
      by,
    });
    return { ok: data.updated };
  },

  consolidateMemories(patientId: string): Promise<ConsolidateResult> {
    return postJson("/memory/consolidate", { patient_id: patientId });
  },

  // POST /memory/forget -> { forgot: boolean }
  async deleteMemory(patientId: string, eventId?: string): Promise<{ ok: boolean }> {
    const data = await postJson<{ forgot: boolean }>("/memory/forget", {
      patient_id: patientId,
      event_id: eventId,
    });
    return { ok: data.forgot };
  },
};
