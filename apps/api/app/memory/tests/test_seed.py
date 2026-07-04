"""Seed-integrity and demo-smoke tests (Slice 3).

Locks the deliberate double-dose and repeated-observation invariants that Slice 4's
detector and consolidation depend on, and smoke-runs the scripted demo on LocalStore.
"""

from datetime import datetime, timezone

from app.memory.seed import (
    PATIENT_ID,
    all_events,
    baseline_events,
    demo,
    load_baseline,
    second_blue_pill,
)
from app.memory.store import reset_store
from app.memory.stores.local_store import LocalStore


def _ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_all_events_are_p001_and_count_reasonable():
    events = all_events()
    assert 7 <= len(events) <= 20
    assert all(e.patient_id == PATIENT_ID for e in events)


def test_deliberate_double_dose_invariant():
    intakes = [
        e
        for e in all_events()
        if e.event_type == "medication_intake"
        and any(m.name == "blue pill" for m in e.entities.medications)
    ]
    assert len(intakes) == 2
    assert all(e.verification.status == "unverified" for e in intakes)
    gap = abs((_ts(intakes[0].recorded_at) - _ts(intakes[1].recorded_at)).total_seconds()) / 60
    assert 0 < gap <= 180


def test_repeated_observation_invariant():
    observations = [e for e in all_events() if e.event_type == "observation"]
    assert len(observations) == 3
    normalized = {(e.transcript or "").strip().lower() for e in observations}
    assert normalized == {"i felt confused after dinner."}


def test_wallet_and_ravi_present():
    events = all_events()
    wallet = next(e for e in events if e.event_type == "object_location")
    assert wallet.entities.objects[0].name == "wallet"
    ravi = next(e for e in events if e.event_type == "person_mention")
    assert ravi.entities.people[0].name == "Ravi"
    assert ravi.entities.people[0].relationship == "son"


def test_localstore_reflects_double_dose_and_pattern():
    s = LocalStore()
    load_baseline(s)
    s.add_event(second_blue_pill())

    recent = s.recent_intake_events(PATIENT_ID, "blue pill", 180)
    assert len(recent) == 2

    patterns = s.consolidate(PATIENT_ID)["patterns"]
    assert len(patterns) == 1
    assert patterns[0]["count"] == 3


def test_demo_runs_on_local(monkeypatch):
    monkeypatch.delenv("MEMORY_BACKEND", raising=False)
    reset_store()
    summary = demo()
    reset_store()

    assert summary["backend"] == "local"
    assert summary["ingested"] == len(baseline_events())
    assert summary["wallet_status_before"] == "unverified"
    assert summary["wallet_status_after"] == "confirmed"
    assert summary["ravi_found"] is True
    assert summary["recent_intakes"] == 2
    assert summary["double_dose"] is True
    assert summary["patterns"] == 1
    assert summary["forgot"] is True
    assert summary["nodes"] > summary["ingested"]
