"""Tier 1 — hybrid query() routing (Fix 1). FREE, offline, no cognee network.

`_is_relational` decides whether query() traverses the graph (GRAPH_COMPLETION) or stays on
the CHUNKS + provenance path. It is a pure function, so we assert the routing table directly
without touching cognee/OpenAI. Importing graph_store imports cognee but opens NO socket (it
only connects on cloud store instantiation), so the Tier 1 network guard stays satisfied.
"""

import pytest

from app.memory.stores.graph_store import _completion_prose, _is_relational


@pytest.mark.parametrize(
    "query",
    [
        "who is Ravi",
        "Who visited me on Sunday?",
        "whose wallet is this",
        "how are Ravi and the confusion related?",
        "why did I feel confused after dinner?",
        "what relates to the confusion?",
        "what is the relationship between Ravi and my confusion",
        "tell me about my son",
        "who's my doctor",
        "is Ravi connected to the confusion",
    ],
)
def test_relational_questions_route_to_graph(query):
    assert _is_relational(query) is True, f"expected relational routing for {query!r}"


@pytest.mark.parametrize(
    "query",
    [
        "where is my wallet",
        "Where did I leave my keys?",
        "when is my dentist appointment",
        "what time is my appointment",
        "how many pills did I take today",
        "how much water should I drink",
        "did I take my blue pill",
        "my wallet",
        "",
        "   ",
    ],
)
def test_factual_questions_stay_on_chunks(query):
    assert _is_relational(query) is False, f"expected factual routing for {query!r}"


def test_factual_lead_word_overrides_relational_token():
    # A leading factual wh-word wins even when a relational token ("related"/"who") appears,
    # because these ask for an exact, source-backed answer the provenance join must give.
    assert _is_relational("where is the wallet related to Ravi") is False
    assert _is_relational("when did Ravi visit") is False


def test_completion_prose_flattens_markdown_and_ignores_envelope_siblings():
    # Cloud envelope: only search_result is the answer; dataset_id/name must NOT leak in.
    raw = [
        {
            "dataset_id": "907c8da5-e584-505f-9c90-f489d8921b41",
            "dataset_name": "patient_p_001",
            "dataset_tenant_id": "5b279be3",
            "search_result": ["**Ravi**\n\n- son of the speaker\n- visited on Sunday"],
        }
    ]
    prose = _completion_prose(raw)
    assert "907c8da5" not in prose and "patient_p_001" not in prose
    assert "\n" not in prose and "**" not in prose
    assert "Ravi" in prose and "son of the speaker" in prose


def test_completion_prose_empty_on_no_answer():
    assert _completion_prose([]) == ""
    assert _completion_prose([{"dataset_id": "x", "search_result": []}]) == ""
