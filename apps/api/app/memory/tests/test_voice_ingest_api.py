"""HTTP tests for the Module-2 voice ingest extraction endpoint."""


def test_stt_extract_from_json(client):
    response = client.post(
        "/api/stt",
        json={"transcript": "I took the blue pill after breakfast"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event_type"] == "medication_intake"
    assert body["transcript"].startswith("I took")
    assert body["entities"]["medications"][0]["name"] == "blue pill"


def test_stt_extract_from_text_upload(client):
    response = client.post(
        "/api/stt",
        files={"audio": ("note.txt", "I kept my wallet near the TV", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event_type"] == "object_location"
    assert body["entities"]["objects"][0]["name"] == "wallet"


def test_stt_alias_route(client):
    response = client.post(
        "/api/ingest/voice",
        json={"transcript": "Ravi is picking me up at 5pm"},
    )

    assert response.status_code == 200
    assert response.json()["event_type"] == "person_mention"


def test_stt_visit_phrase_is_person_mention_not_appointment(client):
    response = client.post(
        "/api/stt",
        json={"transcript": "My mom came to visit me today and we watched a movie."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event_type"] == "person_mention"
    assert body["entities"]["people"][0]["name"].lower() == "mom"


def test_stt_rejects_empty_transcript(client):
    response = client.post("/api/stt", json={"transcript": "   "})
    assert response.status_code == 422
