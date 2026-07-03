/**
 * mockVoiceBackend.ts — stands in for Module 2 (Speech-to-Text + Entity Extraction).
 *
 * Swap `mockTranscribeAndExtract` for a real fetch to apps/api when Module 2 is ready.
 * The return shape is Partial<MemoryEvent>; patient_id and recorded_at are intentionally
 * omitted — the caller fills them in right before calling ingestMemoryEvent.
 */

import type { MemoryEvent, EventType, Entities } from "./memoryClient";

interface MockExample {
  transcript: string;
  event_type: EventType;
  entities: Entities;
}

const MOCK_EXAMPLES: MockExample[] = [
  {
    transcript: "I kept my wallet near the TV in the living room.",
    event_type: "object_location",
    entities: {
      objects: [{ name: "wallet", location: "near the TV in the living room" }],
    },
  },
  {
    transcript: "I took the blue pill after breakfast this morning.",
    event_type: "medication_intake",
    entities: {
      medications: [{ name: "blue pill", form: "tablet" }],
      time_reference: "after breakfast",
    },
  },
  {
    transcript: "Ravi is picking me up at 5pm to take me to the doctor.",
    event_type: "person_mention",
    entities: {
      people: [{ name: "Ravi", relationship: "family" }],
      appointments: [{ title: "Doctor visit", datetime: "5:00 PM" }],
    },
  },
];

let mockIndex = 0;

/**
 * Simulates STT + entity extraction with a realistic delay.
 * Returns a partial MemoryEvent — caller must add patient_id and recorded_at.
 */
export async function mockTranscribeAndExtract(
  _audioBlob: Blob
): Promise<Partial<MemoryEvent>> {
  const delayMs = 800 + Math.random() * 700; // 800–1500 ms
  await new Promise<void>((resolve) => setTimeout(resolve, delayMs));

  const example = MOCK_EXAMPLES[mockIndex % MOCK_EXAMPLES.length];
  mockIndex++;

  return {
    transcript: example.transcript,
    event_type: example.event_type,
    entities: example.entities,
    // source and verification omitted — server defaults them
  };
}
