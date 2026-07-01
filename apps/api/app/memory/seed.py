"""Dummy data + scripted demo for patient p_001.

Emits events in the exact `MemoryEvent` contract shape, so swapping in the real
extraction feed later needs zero code change. Includes the deliberate double-dose
(two unverified "blue pill" intakes ~40 min apart) and the repeated
"confused after dinner" observation (x3).

Run against the active backend:
    PYTHONPATH=. python -m app.memory.seed
    MEMORY_BACKEND=graph PYTHONPATH=. python -m app.memory.seed   # once graph exists

The demo talks to the MemoryStore directly (the engine + contradiction detector
arrive in later slices). At the double-dose step it shows the two clustered
unverified intakes — the condition the Slice-4 `possible_double_dose` warning fires on.
"""

from app.memory.store import MemoryStore, reset_store, store
from app.schemas.memory import MemoryEvent

PATIENT_ID = "p_001"

# Stable ids so the demo/tests can reference specific notes deterministically.
WALLET_ID = "evt_wallet"
RAVI_ID = "evt_ravi"
BLUE_PILL_1_ID = "evt_bluepill_1"
BLUE_PILL_2_ID = "evt_bluepill_2"
CONFUSED_IDS = ("evt_confused_1", "evt_confused_2", "evt_confused_3")
APPT_ID = "evt_appt"
ROUTINE_ID = "evt_routine"


def baseline_events() -> list[MemoryEvent]:
    """The starting dataset — everything except the live-ingested 2nd blue pill."""
    return [
        MemoryEvent(
            patient_id=PATIENT_ID,
            event_id=WALLET_ID,
            source="voice_note",
            recorded_at="2026-07-01T08:15:00Z",
            event_type="object_location",
            transcript="I kept my wallet near the TV.",
            entities={"objects": [{"name": "wallet", "location": "near the TV"}]},
        ),
        MemoryEvent(
            patient_id=PATIENT_ID,
            event_id=RAVI_ID,
            source="voice_note",
            recorded_at="2026-06-28T17:00:00Z",  # a Sunday
            event_type="person_mention",
            transcript="My son Ravi came to visit me. He visits every Sunday.",
            entities={
                "people": [{"name": "Ravi", "relationship": "son"}],
                "time_reference": "Sunday",
            },
        ),
        MemoryEvent(
            patient_id=PATIENT_ID,
            event_id=BLUE_PILL_1_ID,
            source="voice_note",
            recorded_at="2026-07-01T08:30:00Z",
            event_type="medication_intake",
            transcript="I took my blue pill after breakfast.",
            entities={"medications": [{"name": "blue pill", "form": "tablet"}]},
        ),
        MemoryEvent(
            patient_id=PATIENT_ID,
            event_id=CONFUSED_IDS[0],
            source="caregiver_note",
            recorded_at="2026-06-29T20:30:00Z",
            event_type="observation",
            transcript="I felt confused after dinner.",
        ),
        MemoryEvent(
            patient_id=PATIENT_ID,
            event_id=CONFUSED_IDS[1],
            source="caregiver_note",
            recorded_at="2026-06-30T20:30:00Z",
            event_type="observation",
            transcript="I felt confused after dinner.",
        ),
        MemoryEvent(
            patient_id=PATIENT_ID,
            event_id=CONFUSED_IDS[2],
            source="caregiver_note",
            recorded_at="2026-07-01T20:30:00Z",
            event_type="observation",
            transcript="I felt confused after dinner.",
        ),
        MemoryEvent(
            patient_id=PATIENT_ID,
            event_id=APPT_ID,
            source="caregiver_note",
            recorded_at="2026-07-01T09:00:00Z",
            event_type="appointment",
            transcript="I have a cardiology check-up with Dr. Mehta on Friday.",
            entities={
                "appointments": [
                    {
                        "title": "cardiology check-up",
                        "datetime": "2026-07-05T10:00:00Z",
                        "doctor": "Dr. Mehta",
                    }
                ]
            },
        ),
        MemoryEvent(
            patient_id=PATIENT_ID,
            event_id=ROUTINE_ID,
            source="voice_note",
            recorded_at="2026-07-01T07:45:00Z",
            event_type="routine",
            transcript="I water the plants every morning.",
            entities={
                "objects": [{"name": "plants"}],
                "time_reference": "every morning",
            },
        ),
    ]


def second_blue_pill() -> MemoryEvent:
    """The 2nd blue-pill intake ~40 min after the first — the deliberate double-dose."""
    return MemoryEvent(
        patient_id=PATIENT_ID,
        event_id=BLUE_PILL_2_ID,
        source="voice_note",
        recorded_at="2026-07-01T09:10:00Z",
        event_type="medication_intake",
        transcript="I think I should take my blue pill now.",
        entities={"medications": [{"name": "blue pill", "form": "tablet"}]},
    )


def all_events() -> list[MemoryEvent]:
    """The full set (baseline + 2nd blue pill)."""
    return baseline_events() + [second_blue_pill()]


def load_baseline(target: MemoryStore) -> None:
    """Reset the patient and load the baseline dataset (idempotent)."""
    target.forget(PATIENT_ID)
    for event in baseline_events():
        target.add_event(event)


# --- pretty printing ---------------------------------------------------------


def _section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 60 - len(title)))


def _show(rows) -> None:
    if not rows:
        print("   (no results)")
        return
    for r in rows:
        verified = f" by {r.verified_by}" if r.verified_by else ""
        print(
            f"   • {r.fact}  [{r.node_type}] "
            f"({r.source}, {r.verification_status}{verified}, {r.recorded_at}, {r.note_id})"
        )


# --- scripted demo -----------------------------------------------------------


def demo() -> dict:
    """Run the end-to-end demo on the active backend; print a trace, return a summary."""
    reset_store()
    s = store()
    _section(f"Evermoments memory demo  (backend = {s.backend_name})")

    load_baseline(s)
    ingested = len(baseline_events())
    print(f"   loaded {ingested} baseline events for {PATIENT_ID}")

    _section('Ask: "where is my wallet?"  (before verification)')
    before = s.query(PATIENT_ID, "where is my wallet")
    _show(before)
    wallet_status_before = before[0].verification_status if before else None

    _section("Caregiver confirms the wallet note")
    s.set_verification(PATIENT_ID, WALLET_ID, "confirmed", "nurse_amy")
    print("   set_verification(evt_wallet) -> confirmed by nurse_amy")

    _section('Ask again: "where is my wallet?"  (after verification)')
    after = s.query(PATIENT_ID, "where is my wallet")
    _show(after)
    wallet_status_after = after[0].verification_status if after else None

    _section('Ask: "who is Ravi?"  (people-graph boost)')
    ravi = s.query(PATIENT_ID, "who is Ravi")
    _show(ravi)
    ravi_found = bool(ravi) and ravi[0].node_type == "PersonMention"

    _section("Ingest a 2nd blue pill ~40 min later (deliberate double-dose)")
    s.add_event(second_blue_pill())
    print(f"   ingested {BLUE_PILL_2_ID}")

    _section("Recent blue-pill intakes within 180 min")
    recent = s.recent_intake_events(PATIENT_ID, "blue pill", 180)
    _show(recent)
    unverified = [r for r in recent if r.verification_status != "confirmed"]
    print(
        f"   ⚠ {len(recent)} intakes clustered; {len(unverified)} unverified -> "
        "the Slice-4 possible_double_dose warning fires on this condition."
    )

    _section("Consolidate: surface repeated patterns")
    consolidated = s.consolidate(PATIENT_ID)
    patterns = consolidated["patterns"]
    for p in patterns:
        print(f"   pattern: \"{p['pattern']}\" x{p['count']}  notes={p['related_note_ids']}")

    _section("Forget one note (privacy / correction)")
    forgot = s.forget(PATIENT_ID, ROUTINE_ID)
    print(f"   forget({ROUTINE_ID}) -> {forgot}")
    print('   re-ask "water the plants":')
    _show(s.query(PATIENT_ID, "water the plants"))

    g = s.graph(PATIENT_ID)
    _section("Typed memory graph")
    print(f"   {len(g['nodes'])} nodes, {len(g['edges'])} edges")

    return {
        "backend": s.backend_name,
        "ingested": ingested,
        "wallet_status_before": wallet_status_before,
        "wallet_status_after": wallet_status_after,
        "ravi_found": ravi_found,
        "recent_intakes": len(recent),
        "patterns": len(patterns),
        "forgot": forgot,
        "nodes": len(g["nodes"]),
        "edges": len(g["edges"]),
    }


if __name__ == "__main__":
    demo()
