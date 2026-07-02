"""Tier 2 — GATED live-cognee tests (Slice 8d). COSTS MONEY. NOT run by default.

Marked ``cognee`` and deselected by ``pytest.ini`` (``addopts = -m "not cognee"``); run
explicitly with:

    MEMORY_BACKEND=graph PYTHONPATH=. pytest -m cognee -s app/memory

These cover ONLY what can't be proven on LocalStore: real cognee connect, live
ingest -> cognify, SearchType.CHUNKS retrieval joined back to the authoritative record for
correct provenance, verification reflected in recall, and live forget. A single tiny 3-event
fixture is ingested and cognified ONCE and reused by every test (no cognify in loops), and the
dataset is pruned on teardown. Total OpenAI token usage is printed at the end (best-effort).
"""

import os

# Mirror graph_store.py's guards BEFORE cognee is imported, so even collection in the default
# (deselected) run never triggers cognee's pre-flight LLM connection test / any network.
os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")

import pytest

from app.core.config import settings
from app.schemas.memory import MemoryEvent

pytestmark = pytest.mark.cognee

# Skip the whole module unless cognee is installed AND a key is available.
pytest.importorskip("cognee")
if not (
    settings.COGNEE_LLM_API_KEY
    or os.getenv("OPENAI_API_KEY")
    or os.getenv("COGNEE_LLM_API_KEY")
):
    pytest.skip(
        "no COGNEE_LLM_API_KEY/OPENAI_API_KEY set — skipping live cognee suite",
        allow_module_level=True,
    )

# Isolated patient id so this never collides with demo/local data.
PATIENT = "p_cognee_test"
WALLET_ID = "evt_ct_wallet"
RAVI_ID = "evt_ct_ravi"
FORGET_ID = "evt_ct_forgettable"


def _fixture_events() -> list[MemoryEvent]:
    """Three tiny events — the entire live-cognee corpus for this suite."""
    return [
        MemoryEvent(
            patient_id=PATIENT, event_id=WALLET_ID, source="voice_note",
            recorded_at="2026-07-01T08:15:00Z", event_type="object_location",
            transcript="I kept my wallet on the kitchen counter.",
            entities={"objects": [{"name": "wallet", "location": "kitchen counter"}]},
        ),
        MemoryEvent(
            patient_id=PATIENT, event_id=RAVI_ID, source="voice_note",
            recorded_at="2026-06-28T17:00:00Z", event_type="person_mention",
            transcript="My son Ravi visited me on Sunday.",
            entities={"people": [{"name": "Ravi", "relationship": "son"}]},
        ),
        MemoryEvent(
            patient_id=PATIENT, event_id=FORGET_ID, source="caregiver_note",
            recorded_at="2026-06-30T10:00:00Z", event_type="appointment",
            transcript="Dentist appointment with Dr. Lee on Wednesday.",
            entities={"appointments": [{"title": "dentist appointment", "doctor": "Dr. Lee"}]},
        ),
    ]


@pytest.fixture(scope="session")
def graph_store(request):
    """Build a CogneeGraphStore, ingest the 3-event fixture ONCE, cognify ONCE; reuse.

    Teardown forgets the whole patient (prunes cognee + record) and prints the session's
    OpenAI token usage to the real terminal (bypasses pytest capture, so it shows without -s).
    """
    usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "on": False}

    # Best-effort token/cost accounting via litellm (cognee's LLM layer).
    try:
        import litellm

        def _track(kwargs, completion_response, start_time, end_time):
            try:
                usage["on"] = True
                usage["calls"] += 1
                u = getattr(completion_response, "usage", None)
                if u is not None:
                    usage["prompt_tokens"] += int(getattr(u, "prompt_tokens", 0) or 0)
                    usage["completion_tokens"] += int(getattr(u, "completion_tokens", 0) or 0)
                cost = kwargs.get("response_cost")
                if cost:
                    usage["cost_usd"] += float(cost)
            except Exception:
                pass

        litellm.success_callback = list(getattr(litellm, "success_callback", []) or []) + [_track]
    except Exception:
        pass

    from app.memory.stores.graph_store import CogneeGraphStore

    store = CogneeGraphStore()
    for ev in _fixture_events():
        store.add_event(ev)
    store._ensure_cognified(PATIENT)  # the ONE cognify for the whole suite

    yield store

    # Prune the dataset (record + best-effort cognee side).
    try:
        store.forget(PATIENT)
    except Exception:
        pass

    # Print usage to the real terminal so it's visible even without -s.
    reporter = request.config.pluginmanager.get_plugin("terminalreporter")
    if usage["on"]:
        line = (
            f"Tier 2 cognee usage: {usage['calls']} LLM/embedding calls, "
            f"{usage['prompt_tokens']} prompt + {usage['completion_tokens']} completion tokens, "
            f"~${usage['cost_usd']:.4f}"
        )
    else:
        line = "Tier 2 cognee usage: not captured (litellm callback saw no calls)."
    if reporter is not None:
        reporter.write_sep("=", "Tier 2 cognee usage")
        reporter.write_line(line)
    else:  # pragma: no cover
        print(line)


# NOTE: these tests share one cognified dataset and run in file order — keep
# test_cognee_connects_and_cognifies first (asserts all 3 present) and
# test_forget_deletes_from_recall last (removes one). Tests 2 and 3 touch disjoint events.


def test_cognee_connects_and_cognifies(graph_store):
    """Fixture setup proves connect + live add + cognify all succeeded."""
    import sys

    assert "cognee" in sys.modules
    assert set(graph_store._events[PATIENT]) == {WALLET_ID, RAVI_ID, FORGET_ID}
    assert PATIENT not in graph_store._dirty  # cognify ran (else it'd still be dirty)


def test_chunks_recall_joins_provenance(graph_store):
    """CHUNKS retrieval joined to the record returns correct provenance (unmutated event)."""
    rows = graph_store.query(PATIENT, "who is Ravi", top_k=5)
    assert rows, "cognee CHUNKS recall returned nothing for Ravi"
    ravi = next((r for r in rows if r.note_id == RAVI_ID), None)
    assert ravi is not None
    assert ravi.node_type == "PersonMention"
    assert ravi.source == "voice_note"
    assert ravi.verification_status == "unverified"
    assert "ravi" in ravi.fact.lower()


def test_verification_reflected_in_recall(graph_store):
    """Verifying an event is reflected in the next recall (join reads the CURRENT record)."""
    assert graph_store.set_verification(PATIENT, WALLET_ID, "confirmed", "nurse_amy") is True
    rows = graph_store.query(PATIENT, "where is my wallet", top_k=5)
    wallet = next((r for r in rows if r.note_id == WALLET_ID), None)
    assert wallet is not None, "cognee CHUNKS recall returned nothing for the wallet"
    assert wallet.verification_status == "confirmed"
    assert wallet.verified_by == "nurse_amy"


def test_forget_deletes_from_recall(graph_store):
    """Live forget removes an event from both list and recall (record-join gating)."""
    assert graph_store.forget(PATIENT, FORGET_ID) is True
    assert FORGET_ID not in {r.note_id for r in graph_store.list_memories(PATIENT)}
    rows = graph_store.query(PATIENT, "dentist appointment", top_k=5)
    assert all(r.note_id != FORGET_ID for r in rows)
