import { realMemoryClient } from "@/lib/memory/api";
import { mockMemoryClient } from "@/lib/memory/mock";
import type { MemoryClient } from "@/types/memory";

// Flip to "false" in .env.local once Japit's /memory/* endpoints are live —
// no component changes needed, both clients satisfy the same MemoryClient contract.
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_MEMORY !== "false";

export const memoryClient: MemoryClient = USE_MOCK ? mockMemoryClient : realMemoryClient;
