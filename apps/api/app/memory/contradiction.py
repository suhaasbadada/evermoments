"""Pure-Python contradiction detection — the double-dose safety feature.

When a medication_intake event arrives, warn if the same medication looks like it
was recorded again within a short window and no caregiver has confirmed either
intake. This is intentionally PURE Python (query recent events + compare
timestamps) with ZERO dependency on any cognee feature, so it behaves identically
on every backend (guardrail #5).
"""

from datetime import datetime, timedelta, timezone

from app.memory.store import MemoryStore
from app.schemas.memory import MemoryEvent, MemoryWarning

# Interim default; Slice 6 (which owns config.py) will resolve this from
# settings.CONTRADICTION_WINDOW_MIN. Same value, isolated to the config-owning slice.
DEFAULT_WINDOW_MIN = 180


def _parse_ts(value: str) -> datetime:
    """ISO-8601 -> timezone-aware datetime (naive treated as UTC). Kept local so this
    module stays backend-agnostic. recorded_at is already validated at the contract."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def check_double_dose(
    store: MemoryStore,
    event: MemoryEvent,
    within_minutes: int | None = None,
) -> MemoryWarning | None:
    """Return a possible_double_dose warning, or None if there's nothing to flag."""
    if event.event_type != "medication_intake":
        return None
    med_names = [m.name for m in event.entities.medications]
    if not med_names:
        return None

    window_min = within_minutes if within_minutes is not None else DEFAULT_WINDOW_MIN
    window = timedelta(minutes=window_min)
    new_ts = _parse_ts(event.recorded_at)
    new_confirmed = event.verification.status == "confirmed"

    conflicting_ids: list[str] = []
    conflicting_meds: set[str] = set()

    for name in med_names:
        for row in store.recent_intake_events(event.patient_id, name, window_min):
            if event.event_id is not None and row.note_id == event.event_id:
                continue  # don't compare the new event with itself
            # Pure-Python timestamp comparison, relative to the new event.
            if abs(new_ts - _parse_ts(row.recorded_at)) > window:
                continue
            # A conflict only if NEITHER intake was confirmed by a caregiver.
            if new_confirmed or row.verification_status == "confirmed":
                continue
            if row.note_id not in conflicting_ids:
                conflicting_ids.append(row.note_id)
            conflicting_meds.add(name)

    if not conflicting_ids:
        return None

    related: list[str] = []
    if event.event_id:
        related.append(event.event_id)
    for note_id in conflicting_ids:
        if note_id not in related:
            related.append(note_id)

    meds_label = ", ".join(sorted(conflicting_meds))
    message = (
        f"It looks like {meds_label} may have been taken more than once within "
        f"{window_min} minutes, and a caregiver hasn't confirmed it yet. "
        "Please check with your caregiver."
    )
    return MemoryWarning(
        type="possible_double_dose",
        message=message,
        related_note_ids=related,
    )
