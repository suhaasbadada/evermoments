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
  // POST /memory/list -> MemoryAnswer.results[], per the contract Japit agreed to add.
  listMemories(params: MemoryListParams): Promise<MemoryResult[]> {
    return postJson<MemoryResult[]>("/memory/list", params);
  },

  verifyMemory(
    patientId: string,
    eventId: string,
    status: VerificationStatus,
    by: string,
  ): Promise<{ ok: boolean }> {
    return postJson("/memory/verify", {
      patient_id: patientId,
      event_id: eventId,
      status,
      by,
    });
  },

  // Response shape beyond {ok, run_id} is unconfirmed with Japit (see §6.3 vs
  // his definition-of-done, which promises visible pattern-surfacing). Treat
  // `patterns` as optional until that's pinned down.
  consolidateMemories(patientId: string): Promise<ConsolidateResult> {
    return postJson("/memory/consolidate", { patient_id: patientId });
  },

  async deleteMemory(patientId: string, eventId?: string): Promise<{ ok: boolean }> {
    const response = await fetch(`${API_BASE_URL}/memory`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_id: patientId, event_id: eventId }),
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`DELETE /memory failed with status ${response.status}`);
    }

    return response.json() as Promise<{ ok: boolean }>;
  },
};
