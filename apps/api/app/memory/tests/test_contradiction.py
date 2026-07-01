"""Tests for the pure-Python double-dose detector (Slice 4).

Uses the seeded double-dose (two unverified "blue pill" intakes ~40 min apart) on
LocalStore; the logic is backend-agnostic, so parity across backends is covered later.
"""

from app.memory.contradiction import check_double_dose
from app.memory.seed import (
    BLUE_PILL_1_ID,
    BLUE_PILL_2_ID,
    PATIENT_ID,
    load_baseline,
    second_blue_pill,
)
from app.memory.stores.local_store import LocalStore
from app.schemas.memory import MemoryEvent


def _store_with_double_dose() -> tuple[LocalStore, MemoryEvent]:
    s = LocalStore()
    load_baseline(s)
    second = second_blue_pill()
    s.add_event(second)  # store first, matching the engine's future order
    return s, second


# -- fires --------------------------------------------------------------------


def test_double_dose_fires():
    s, second = _store_with_double_dose()
    warning = check_double_dose(s, second)
    assert warning is not None
    assert warning.type == "possible_double_dose"
    assert {BLUE_PILL_1_ID, BLUE_PILL_2_ID} <= set(warning.related_note_ids)


def test_warning_message_is_calm_and_not_prescriptive():
    s, second = _store_with_double_dose()
    msg = check_double_dose(s, second).message.lower()
    assert "blue pill" in msg
    assert "caregiver" in msg
    # non-medical-advice: does not tell the patient what to take
    assert "take another" not in msg
    assert "should take" not in msg


# -- no false positives -------------------------------------------------------


def test_non_medication_event_returns_none():
    s, _ = _store_with_double_dose()
    non_med = MemoryEvent(
        patient_id=PATIENT_ID,
        event_id="evt_obs",
        recorded_at="2026-07-01T09:15:00Z",
        event_type="observation",
        transcript="Feeling fine.",
    )
    assert check_double_dose(s, non_med) is None


def test_lone_intake_returns_none():
    s = LocalStore()
    only = MemoryEvent(
        patient_id=PATIENT_ID,
        event_id="evt_only",
        recorded_at="2026-07-01T08:30:00Z",
        event_type="medication_intake",
        entities={"medications": [{"name": "blue pill"}]},
    )
    s.add_event(only)
    assert check_double_dose(s, only) is None


def test_tight_window_returns_none():
    s, second = _store_with_double_dose()
    # the two intakes are 40 min apart; a 10-min window excludes the earlier one
    assert check_double_dose(s, second, within_minutes=10) is None


def test_different_medication_returns_none():
    s, _ = _store_with_double_dose()
    other = MemoryEvent(
        patient_id=PATIENT_ID,
        event_id="evt_redpill",
        recorded_at="2026-07-01T09:20:00Z",
        event_type="medication_intake",
        entities={"medications": [{"name": "red capsule"}]},
    )
    s.add_event(other)
    assert check_double_dose(s, other) is None


# -- caregiver verification suppresses ----------------------------------------


def test_confirmed_earlier_intake_suppresses_warning():
    s, second = _store_with_double_dose()
    s.set_verification(PATIENT_ID, BLUE_PILL_1_ID, "confirmed", "nurse_amy")
    assert check_double_dose(s, second) is None


def test_confirmed_new_event_suppresses_warning():
    s, _ = _store_with_double_dose()
    confirmed_new = second_blue_pill()
    confirmed_new.verification.status = "confirmed"
    assert check_double_dose(s, confirmed_new) is None


# -- isolation (no full baseline needed) --------------------------------------


def test_two_event_isolation():
    s = LocalStore()
    first = MemoryEvent(
        patient_id=PATIENT_ID,
        event_id="evt_a",
        recorded_at="2026-07-01T08:00:00Z",
        event_type="medication_intake",
        entities={"medications": [{"name": "blue pill"}]},
    )
    second = MemoryEvent(
        patient_id=PATIENT_ID,
        event_id="evt_b",
        recorded_at="2026-07-01T08:30:00Z",
        event_type="medication_intake",
        entities={"medications": [{"name": "blue pill"}]},
    )
    s.add_event(first)
    s.add_event(second)
    warning = check_double_dose(s, second)
    assert warning is not None
    assert set(warning.related_note_ids) == {"evt_a", "evt_b"}
