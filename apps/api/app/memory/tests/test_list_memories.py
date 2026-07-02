"""Behaviour tests for list_memories() + the shared filter_sort_limit helper (Slice 8c)."""

import pytest

from app.memory.stores.local_store import LocalStore, filter_sort_limit
from app.schemas.memory import ListFilters, MemoryEvent, MemoryResult

PID = "p_001"

# Explicit ids + spread-out timestamps so order / date-range / limit assertions are exact.
WALLET = "e_wallet"
RAVI = "e_ravi"
PILL_EARLY = "e_pill_early"
PILL_LATE = "e_pill_late"
CONFUSED = "e_confused"


def _events() -> list[MemoryEvent]:
    return [
        MemoryEvent(
            patient_id=PID, event_id=WALLET, recorded_at="2026-07-01T09:00:00Z",
            event_type="object_location", transcript="Wallet is near the TV.",
            entities={"objects": [{"name": "wallet", "location": "near the TV"}]},
        ),
        MemoryEvent(
            patient_id=PID, event_id=RAVI, recorded_at="2026-06-28T17:00:00Z",
            event_type="person_mention", transcript="Ravi visited.",
            entities={"people": [{"name": "Ravi", "relationship": "son"}]},
        ),
        MemoryEvent(
            patient_id=PID, event_id=PILL_EARLY, recorded_at="2026-07-01T08:30:00Z",
            event_type="medication_intake", transcript="Took the blue pill.",
            entities={"medications": [{"name": "blue pill"}]},
        ),
        MemoryEvent(
            patient_id=PID, event_id=PILL_LATE, recorded_at="2026-07-01T09:10:00Z",
            event_type="medication_intake", transcript="Took the blue pill again.",
            entities={"medications": [{"name": "blue pill"}]},
        ),
        MemoryEvent(
            patient_id=PID, event_id=CONFUSED, recorded_at="2026-06-29T20:00:00Z",
            event_type="observation", transcript="Confused after dinner.",
        ),
    ]


# recorded_at, newest → oldest
DESC_IDS = [PILL_LATE, WALLET, PILL_EARLY, CONFUSED, RAVI]


@pytest.fixture()
def local() -> LocalStore:
    s = LocalStore()
    for ev in _events():
        s.add_event(ev)
    return s


def _ids(rows) -> list[str]:
    return [r.note_id for r in rows]


# -- filter_sort_limit (pure, backend-agnostic helper) ------------------------


def test_helper_default_sort_is_desc():
    assert [e.event_id for e in filter_sort_limit(_events())] == DESC_IDS


def test_helper_asc_sort():
    out = filter_sort_limit(_events(), sort="recorded_at_asc")
    assert [e.event_id for e in out] == list(reversed(DESC_IDS))


def test_helper_event_type_filter():
    out = filter_sort_limit(_events(), ListFilters(event_type="medication_intake"))
    assert [e.event_id for e in out] == [PILL_LATE, PILL_EARLY]


def test_helper_date_range_is_inclusive():
    # [06-29T00:00, 07-01T09:00]: upper bound inclusive keeps e_wallet, excludes the 09:10 pill.
    out = filter_sort_limit(
        _events(),
        ListFilters(date_from="2026-06-29T00:00:00Z", date_to="2026-07-01T09:00:00Z"),
    )
    assert [e.event_id for e in out] == [WALLET, PILL_EARLY, CONFUSED]


def test_helper_limit():
    out = filter_sort_limit(_events(), limit=2)
    assert [e.event_id for e in out] == [PILL_LATE, WALLET]


# -- LocalStore.list_memories -------------------------------------------------


def test_list_no_filters_returns_all_desc(local: LocalStore):
    rows = local.list_memories(PID)
    assert _ids(rows) == DESC_IDS
    assert all(isinstance(r, MemoryResult) for r in rows)
    top = rows[0]  # full provenance carried through
    assert top.node_type and top.source and top.recorded_at and top.verification_status


def test_list_filter_event_type(local: LocalStore):
    rows = local.list_memories(PID, ListFilters(event_type="medication_intake"))
    assert _ids(rows) == [PILL_LATE, PILL_EARLY]
    assert all(r.node_type == "MedicationIntake" for r in rows)


def test_list_filter_verification_status_reflects_current(local: LocalStore):
    local.set_verification(PID, WALLET, "confirmed", "nurse_amy")

    confirmed = local.list_memories(PID, ListFilters(verification_status="confirmed"))
    assert _ids(confirmed) == [WALLET]
    assert confirmed[0].verification_status == "confirmed"
    assert confirmed[0].verified_by == "nurse_amy"

    unverified = local.list_memories(PID, ListFilters(verification_status="unverified"))
    assert WALLET not in _ids(unverified)
    assert len(unverified) == 4


def test_list_filter_date_range(local: LocalStore):
    rows = local.list_memories(
        PID, ListFilters(date_from="2026-06-29T00:00:00Z", date_to="2026-07-01T09:00:00Z")
    )
    assert _ids(rows) == [WALLET, PILL_EARLY, CONFUSED]


def test_list_sort_asc(local: LocalStore):
    rows = local.list_memories(PID, sort="recorded_at_asc")
    assert _ids(rows) == list(reversed(DESC_IDS))


def test_list_limit(local: LocalStore):
    assert _ids(local.list_memories(PID, limit=2)) == [PILL_LATE, WALLET]


def test_list_empty_on_no_match(local: LocalStore):
    assert local.list_memories(PID, ListFilters(event_type="appointment")) == []


def test_list_empty_on_unknown_patient(local: LocalStore):
    assert local.list_memories("p_999") == []


# -- backend parity: graph reads the same authoritative record ----------------
# Skipped when cognee is not installed (importing graph_store pulls in cognee).


def test_graph_list_memories_matches_local():
    pytest.importorskip("cognee")
    from app.memory.stores.graph_store import CogneeGraphStore

    local_s = LocalStore()
    graph_s = CogneeGraphStore()
    for ev in _events():
        local_s.add_event(ev)
        # Seed the graph store's authoritative record directly: list_memories reads only that
        # record (never cognee), so this avoids the network round-trip in add_event while still
        # exercising the real CogneeGraphStore.list_memories code path.
        graph_s._events.setdefault(ev.patient_id, {})[ev.event_id] = ev

    for filters in (
        None,
        ListFilters(event_type="medication_intake"),
        ListFilters(verification_status="unverified"),
    ):
        for sort in ("recorded_at_desc", "recorded_at_asc"):
            lrows = local_s.list_memories(PID, filters, sort)
            grows = graph_s.list_memories(PID, filters, sort)
            assert [r.model_dump() for r in grows] == [r.model_dump() for r in lrows]
