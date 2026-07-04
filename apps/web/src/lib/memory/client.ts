import { realMemoryClient } from "@/lib/memory/api";
import { mockMemoryClient } from "@/lib/memory/mock";
import type { MemoryClient } from "@/types/memory";

// Mock is opt-in only; default to real backend so caregiver/patient stay in sync.
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_MEMORY === "true";

export const memoryClient: MemoryClient = USE_MOCK ? mockMemoryClient : realMemoryClient;
