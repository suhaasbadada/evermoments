import { NextRequest, NextResponse } from "next/server";
import {
  searchEvents,
  toMemoryResult,
  synthesizeAnswer,
  checkWarning,
} from "@/lib/mockStore";

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const patientId = body.patient_id as string | undefined;
  const query = body.query as string | undefined;

  if (!patientId || !query) {
    return NextResponse.json(
      { error: "patient_id and query are required" },
      { status: 422 }
    );
  }

  const topK = typeof body.top_k === "number" ? body.top_k : 5;

  const results = searchEvents(patientId, query, topK);
  const answer = synthesizeAnswer(query, results);

  // Surface any safety warnings from matched results (e.g. double-dose in results)
  const warnings = results
    .map((e) => checkWarning(e))
    .filter((w): w is NonNullable<typeof w> => w !== undefined);

  return NextResponse.json({
    query,
    answer,
    results: results.map(toMemoryResult),
    warnings,
  });
}
