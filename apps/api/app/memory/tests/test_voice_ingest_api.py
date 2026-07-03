import base64

from app.core.config import settings

BASE = "/api/ingest"
MEMORY_BASE = "/api/memory"


def test_voice_note_ingest_extracts_object_location_and_stores_memory(client):
    r = client.post(
        f"{BASE}/voice-note",
        json={
            "patient_id": "p_001",
            "recorded_at": "2026-07-01T08:15:00Z",
            "transcript": "I kept my wallet near the TV.",
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "stored"
    assert body["stt_provider"] == "inline_transcript"
    assert body["memory_event"]["event_type"] == "object_location"
    assert body["memory_event"]["entities"]["objects"] == [{"name": "wallet", "location": "near the TV"}]
    assert body["warning"] is None

    query = client.post(
        f"{MEMORY_BASE}/query",
        json={"patient_id": "p_001", "query": "where is my wallet"},
    )
    assert query.status_code == 200
    top = query.json()["results"][0]
    assert "wallet" in top["fact"].lower()
    assert "near the tv" in top["fact"].lower()


def test_voice_note_ingest_surfaces_double_dose_warning(client):
    seed = client.post(f"{MEMORY_BASE}/seed")
    assert seed.status_code == 200

    r = client.post(
        f"{BASE}/voice-note",
        json={
            "patient_id": "p_001",
            "recorded_at": "2026-07-01T09:10:00Z",
            "transcript": "I took my blue pill after breakfast.",
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["memory_event"]["event_type"] == "medication_intake"
    assert body["warning"] is not None
    assert body["warning"]["type"] == "possible_double_dose"


def test_voice_note_ingest_accepts_text_payload_for_offline_stt(client):
    transcript = "My son Ravi visited me yesterday."
    payload = base64.b64encode(transcript.encode("utf-8")).decode("ascii")

    r = client.post(
        f"{BASE}/voice-note",
        json={
            "patient_id": "p_001",
            "recorded_at": "2026-07-01T11:15:00Z",
            "audio_base64": payload,
            "audio_mime_type": "text/plain",
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["transcript"] == transcript
    assert body["stt_provider"] == "text_payload"
    assert body["memory_event"]["event_type"] == "person_mention"
    assert body["memory_event"]["entities"]["people"][0]["name"] == "Ravi"
    assert body["memory_event"]["entities"]["people"][0]["relationship"] == "son"


def test_voice_note_ingest_rejects_unsupported_audio_payload(client):
    payload = base64.b64encode(b"binary-audio").decode("ascii")

    r = client.post(
        f"{BASE}/voice-note",
        json={
            "patient_id": "p_001",
            "audio_base64": payload,
            "audio_mime_type": "audio/wav",
        },
    )

    assert r.status_code == 422
    assert "STT_BACKEND='openai'" in r.json()["detail"]


def test_voice_note_ingest_uses_openai_backend_for_binary_audio(client, monkeypatch):
    payload = base64.b64encode(b"fake wav bytes").decode("ascii")

    monkeypatch.setattr(settings, "STT_BACKEND", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    called = {}

    def fake_post(audio_bytes: bytes, audio_mime_type: str) -> str:
        called["audio_bytes"] = audio_bytes
        called["audio_mime_type"] = audio_mime_type
        return "I left my keys on the kitchen table."

    monkeypatch.setattr("app.services.voice_pipeline._post_openai_transcription", fake_post)

    r = client.post(
        f"{BASE}/voice-note",
        json={
            "patient_id": "p_001",
            "recorded_at": "2026-07-01T12:15:00Z",
            "audio_base64": payload,
            "audio_mime_type": "audio/wav",
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["stt_provider"] == "openai_audio_transcribe"
    assert body["transcript"] == "I left my keys on the kitchen table."
    assert body["memory_event"]["event_type"] == "object_location"
    assert body["memory_event"]["entities"]["objects"][0]["name"] == "keys"
    assert called == {"audio_bytes": b"fake wav bytes", "audio_mime_type": "audio/wav"}


def test_voice_note_ingest_requires_openai_key_for_binary_audio(client, monkeypatch):
    payload = base64.b64encode(b"fake wav bytes").decode("ascii")

    monkeypatch.setattr(settings, "STT_BACKEND", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    r = client.post(
        f"{BASE}/voice-note",
        json={
            "patient_id": "p_001",
            "audio_base64": payload,
            "audio_mime_type": "audio/wav",
        },
    )

    assert r.status_code == 422
    assert "OPENAI_API_KEY" in r.json()["detail"]