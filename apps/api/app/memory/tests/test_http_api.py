"""HTTP integration / E2E tests for the memory API (Slice 8d).

Boots the real FastAPI app via TestClient (see the ``client`` fixture in conftest.py) on
MEMORY_BACKEND=local and drives the frozen /api/memory contract end to end — status codes,
response shapes, provenance, the double-dose warning, and the full demo spine. Tier 1: free
and offline; the autouse socket guard in conftest.py fails the test on any network call.
"""

import socket

import pytest

from app.memory.seed import baseline_events
from app.schemas.memory import MemoryResult

BASE = "/api/memory"


# -- Tier 1 offline guarantee -------------------------------------------------


def test_tier1_network_is_blocked():
    """The autouse socket guard (conftest.py) makes outbound calls fail — so a green Tier 1
    run proves ZERO network / no OpenAI spend. Fails loudly if the guard is ever removed."""
    with pytest.raises(RuntimeError):
        socket.create_connection(("8.8.8.8", 53), timeout=0.1)
    with pytest.raises(RuntimeError):
        socket.getaddrinfo("example.com", 443)

# The serialized MemoryResult key set == the contract model's fields (HTTP-layer drift alarm).
RESULT_FIELDS = set(MemoryResult.model_fields)
ANSWER_FIELDS = {"query", "answer", "results", "warnings"}


def _seed(client) -> dict:
    r = client.post(f"{BASE}/seed")
    assert r.status_code == 200
    return r.json()


# -- health -------------------------------------------------------------------


def test_health_reports_local_backend(client):
    r = client.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json() == {"backend": "local", "status": "ok"}


# -- seed ---------------------------------------------------------------------


def test_seed_loads_p001(client):
    assert _seed(client) == {"patient_id": "p_001", "loaded": len(baseline_events())}


def test_seed_rejects_other_patient(client):
    assert client.post(f"{BASE}/seed", json={"patient_id": "p_999"}).status_code == 400


# -- events (ingest) ----------------------------------------------------------


def test_ingest_event_ok(client):
    r = client.post(
        f"{BASE}/events",
        json={
            "patient_id": "p_001",
            "recorded_at": "2026-07-01T08:15:00Z",
            "event_type": "object_location",
            "transcript": "Wallet is on the shelf.",
            "entities": {"objects": [{"name": "wallet", "location": "on the shelf"}]},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["event_id"].startswith("evt_")
    assert body["status"] == "stored"
    assert body["warning"] is None


def test_ingest_rejects_bad_event_type(client):
    r = client.post(
        f"{BASE}/events",
        json={"patient_id": "p_001", "recorded_at": "2026-07-01T08:15:00Z", "event_type": "telepathy"},
    )
    assert r.status_code == 422


def test_ingest_rejects_non_iso_recorded_at(client):
    r = client.post(
        f"{BASE}/events",
        json={"patient_id": "p_001", "recorded_at": "not-a-date", "event_type": "general"},
    )
    assert r.status_code == 422


# -- query --------------------------------------------------------------------


def test_query_returns_answer_with_provenance(client):
    _seed(client)
    r = client.post(f"{BASE}/query", json={"patient_id": "p_001", "query": "where is my wallet"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == ANSWER_FIELDS
    assert body["answer"]
    assert body["results"]
    top = body["results"][0]
    assert set(top) == RESULT_FIELDS
    assert "wallet" in top["fact"].lower()
    assert top["source"] == "voice_note"
    assert top["verification_status"] == "unverified"


def test_query_empty_recall_is_deterministic(client):
    _seed(client)
    r = client.post(f"{BASE}/query", json={"patient_id": "p_001", "query": "xyzzy quux"})
    assert r.status_code == 200
    assert r.json()["results"] == []


# -- list ---------------------------------------------------------------------


def test_list_returns_all_as_memory_results(client):
    _seed(client)
    r = client.post(f"{BASE}/list", json={"patient_id": "p_001"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == len(baseline_events())
    assert all(set(row) == RESULT_FIELDS for row in results)
    times = [row["recorded_at"] for row in results]
    assert times == sorted(times, reverse=True)  # default: newest first


def test_list_filter_medication_intake(client):
    _seed(client)
    r = client.post(f"{BASE}/list", json={"patient_id": "p_001", "filters": {"event_type": "medication_intake"}})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results and all(row["node_type"] == "MedicationIntake" for row in results)


def test_list_filter_unverified_date_and_limit(client):
    _seed(client)
    r = client.post(
        f"{BASE}/list",
        json={
            "patient_id": "p_001",
            "filters": {
                "verification_status": "unverified",
                "date_from": "2026-06-29T00:00:00Z",
                "date_to": "2026-07-01T23:59:59Z",
            },
            "sort": "recorded_at_asc",
            "limit": 3,
        },
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 3
    times = [row["recorded_at"] for row in results]
    assert times == sorted(times)  # ascending


def test_list_rejects_bad_sort_and_limit(client):
    assert client.post(f"{BASE}/list", json={"patient_id": "p_001", "sort": "nope"}).status_code == 422
    assert client.post(f"{BASE}/list", json={"patient_id": "p_001", "limit": 0}).status_code == 422


# -- verify -------------------------------------------------------------------


def test_verify_ok_and_reflected_in_list(client):
    _seed(client)
    r = client.post(
        f"{BASE}/verify",
        json={"patient_id": "p_001", "event_id": "evt_wallet", "status": "confirmed", "by": "nurse_amy"},
    )
    assert r.status_code == 200
    assert r.json() == {"updated": True}

    confirmed = client.post(
        f"{BASE}/list", json={"patient_id": "p_001", "filters": {"verification_status": "confirmed"}}
    ).json()["results"]
    assert [row["note_id"] for row in confirmed] == ["evt_wallet"]
    assert confirmed[0]["verified_by"] == "nurse_amy"


def test_verify_missing_event_404(client):
    _seed(client)
    r = client.post(f"{BASE}/verify", json={"patient_id": "p_001", "event_id": "nope", "status": "confirmed"})
    assert r.status_code == 404


# -- consolidate --------------------------------------------------------------


def test_consolidate_surfaces_pattern(client):
    _seed(client)
    r = client.post(f"{BASE}/consolidate", json={"patient_id": "p_001"})
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"]
    assert len(body["patterns"]) == 1
    assert body["patterns"][0]["count"] == 3
    assert "confused after dinner" in body["patterns"][0]["pattern"].lower()


# -- forget -------------------------------------------------------------------


def test_forget_is_idempotent(client):
    _seed(client)
    first = client.post(f"{BASE}/forget", json={"patient_id": "p_001", "event_id": "evt_routine"})
    assert first.status_code == 200 and first.json() == {"forgot": True}
    second = client.post(f"{BASE}/forget", json={"patient_id": "p_001", "event_id": "evt_routine"})
    assert second.status_code == 200 and second.json() == {"forgot": False}


# -- graph --------------------------------------------------------------------


def test_graph_is_typed_and_labelled(client):
    _seed(client)
    r = client.get(f"{BASE}/graph/p_001")
    assert r.status_code == 200
    body = r.json()
    assert "Patient" in {n["type"] for n in body["nodes"]}
    assert body["edges"] and all("label" in e for e in body["edges"])


# -- double-dose warning surfaced over HTTP -----------------------------------


def test_double_dose_warning_in_ingest_response(client):
    _seed(client)  # includes evt_bluepill_1 at 08:30, unverified
    r = client.post(
        f"{BASE}/events",
        json={
            "patient_id": "p_001",
            "event_id": "evt_bluepill_2",
            "source": "voice_note",
            "recorded_at": "2026-07-01T09:10:00Z",
            "event_type": "medication_intake",
            "entities": {"medications": [{"name": "blue pill", "form": "tablet"}]},
        },
    )
    assert r.status_code == 200
    warning = r.json()["warning"]
    assert warning is not None
    assert warning["type"] == "possible_double_dose"
    assert {"evt_bluepill_1", "evt_bluepill_2"} <= set(warning["related_note_ids"])


# -- full demo spine (one E2E test) -------------------------------------------


def test_demo_spine_end_to_end(client):
    # 1. seed
    assert _seed(client)["loaded"] == len(baseline_events())

    # 2. ask before verification -> answer notes it's unconfirmed
    before = client.post(f"{BASE}/query", json={"patient_id": "p_001", "query": "where is my wallet"}).json()
    assert before["results"][0]["verification_status"] == "unverified"
    assert "caregiver" in before["answer"].lower()

    # 3. caregiver confirms the wallet note
    assert client.post(
        f"{BASE}/verify",
        json={"patient_id": "p_001", "event_id": "evt_wallet", "status": "confirmed", "by": "nurse_amy"},
    ).json() == {"updated": True}

    # 4. ask again -> answer reflects confirmed + who confirmed it
    after = client.post(f"{BASE}/query", json={"patient_id": "p_001", "query": "where is my wallet"}).json()
    assert after["results"][0]["verification_status"] == "confirmed"
    assert "confirmed" in after["answer"].lower()
    assert "nurse_amy" in after["answer"]

    # 5. ingest a 2nd blue pill ~40 min later -> double-dose warning
    warning = client.post(
        f"{BASE}/events",
        json={
            "patient_id": "p_001",
            "event_id": "evt_bluepill_2",
            "recorded_at": "2026-07-01T09:10:00Z",
            "event_type": "medication_intake",
            "entities": {"medications": [{"name": "blue pill"}]},
        },
    ).json()["warning"]
    assert warning and warning["type"] == "possible_double_dose"

    # 6. consolidate -> the repeated "confused after dinner" x3 pattern
    patterns = client.post(f"{BASE}/consolidate", json={"patient_id": "p_001"}).json()["patterns"]
    assert len(patterns) == 1 and patterns[0]["count"] == 3

    # 7. forget the routine note -> it stops being recalled
    assert client.post(
        f"{BASE}/forget", json={"patient_id": "p_001", "event_id": "evt_routine"}
    ).json() == {"forgot": True}
    routine = client.post(f"{BASE}/query", json={"patient_id": "p_001", "query": "water the plants"}).json()
    assert all(row["note_id"] != "evt_routine" for row in routine["results"])
