import base64
import binascii
import re
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.memory import engine
from app.schemas.ingest import VoiceNoteIngestRequest, VoiceNoteIngestResponse
from app.schemas.memory import Appointment, Entities, Medication, MemoryEvent, ObjectItem, Person, Place

_TIME_REFERENCES = (
    "this morning",
    "this afternoon",
    "this evening",
    "after dinner",
    "last night",
    "every day",
    "today",
    "yesterday",
    "tomorrow",
    "tonight",
)
_LOCATION_PREFIXES = ("next to", "inside", "behind", "under", "near", "on", "in", "by")
_OBJECT_NAMES = (
    "wallet",
    "keys",
    "glasses",
    "phone",
    "remote",
    "purse",
    "bag",
    "notebook",
    "cane",
    "hearing aid",
    "medication",
)
_RELATIONSHIP_WORDS = ("son", "daughter", "friend", "husband", "wife", "caregiver", "nurse", "doctor")
_MEDICATION_FORMS = ("pill", "tablet", "capsule")
_MIME_EXTENSIONS = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "text/plain": "txt",
}


def ingest_voice_note(request: VoiceNoteIngestRequest) -> VoiceNoteIngestResponse:
    transcript, stt_provider = _transcribe(request)
    event = _build_event(request, transcript)
    result = engine.ingest_memory_event(event)
    stored = event if event.event_id else event.model_copy(update={"event_id": result["event_id"]})
    return VoiceNoteIngestResponse(
        event_id=result["event_id"],
        status=result["status"],
        transcript=transcript,
        stt_provider=stt_provider,
        memory_event=stored,
        warning=result["warning"],
    )


def _transcribe(request: VoiceNoteIngestRequest) -> tuple[str, str]:
    if request.transcript and request.transcript.strip():
        return request.transcript.strip(), "inline_transcript"

    if request.audio_mime_type == "text/plain":
        return _transcribe_text_payload(request.audio_base64)

    if settings.STT_BACKEND == "openai":
        return _transcribe_openai(request)

    if settings.STT_BACKEND != "offline":
        raise ValueError(f"unsupported STT_BACKEND {settings.STT_BACKEND!r}")

    raise ValueError(
        "binary audio transcription requires STT_BACKEND='openai'; offline mode only supports "
        "audio_mime_type='text/plain'"
    )


def _transcribe_text_payload(audio_base64: str | None) -> tuple[str, str]:
    try:
        decoded = _decode_base64(audio_base64).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("audio_base64 must decode to UTF-8 text for text/plain payloads") from exc

    transcript = decoded.strip()
    if not transcript:
        raise ValueError("decoded transcript was empty")
    return transcript, "text_payload"


def _transcribe_openai(request: VoiceNoteIngestRequest) -> tuple[str, str]:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required when STT_BACKEND='openai'")

    if request.audio_mime_type not in _MIME_EXTENSIONS:
        raise ValueError(f"unsupported audio_mime_type {request.audio_mime_type!r}")

    audio_bytes = _decode_base64(request.audio_base64)
    transcript = _post_openai_transcription(audio_bytes, request.audio_mime_type or "audio/wav")
    cleaned = transcript.strip()
    if not cleaned:
        raise ValueError("transcription provider returned an empty transcript")
    return cleaned, "openai_audio_transcribe"


def _decode_base64(audio_base64: str | None) -> bytes:
    try:
        return base64.b64decode(audio_base64 or "", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("audio_base64 must be valid base64") from exc


def _post_openai_transcription(audio_bytes: bytes, audio_mime_type: str) -> str:
    extension = _MIME_EXTENSIONS.get(audio_mime_type)
    if extension is None:
        raise ValueError(f"unsupported audio_mime_type {audio_mime_type!r}")

    with httpx.Client(timeout=settings.STT_TIMEOUT_SEC) as client:
        try:
            response = client.post(
                settings.OPENAI_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                data={"model": settings.STT_MODEL},
                files={"file": (f"voice-note.{extension}", audio_bytes, audio_mime_type)},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValueError(f"transcription provider request failed: {exc}") from exc

    payload = response.json()
    transcript = payload.get("text")
    if not isinstance(transcript, str):
        raise ValueError("transcription provider response did not include a text field")
    return transcript

def _build_event(request: VoiceNoteIngestRequest, transcript: str) -> MemoryEvent:
    event_type = _classify_event_type(transcript)
    entities = _extract_entities(event_type, transcript)
    recorded_at = request.recorded_at or _utc_now_iso()
    return MemoryEvent(
        patient_id=request.patient_id,
        event_id=request.event_id,
        source=request.source,
        recorded_at=recorded_at,
        transcript=transcript,
        event_type=event_type,
        entities=entities,
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _classify_event_type(transcript: str) -> str:
    text = transcript.lower()

    if _looks_like_medication(text):
        return "medication_intake"
    if _looks_like_object_location(text):
        return "object_location"
    if "appointment" in text or "doctor" in text or "dr." in text or "dr " in text:
        return "appointment"
    if _looks_like_person_mention(transcript):
        return "person_mention"
    if any(phrase in text for phrase in ("every day", "usually", "always", "routine")):
        return "routine"
    if any(phrase in text for phrase in ("feel", "felt", "confused", "worried", "tired", "pain")):
        return "observation"
    return "general"


def _extract_entities(event_type: str, transcript: str) -> Entities:
    text = transcript.strip()
    time_reference = _extract_time_reference(text)

    if event_type == "medication_intake":
        medication = _extract_medication(text)
        return Entities(
            medications=[medication] if medication else [],
            time_reference=time_reference,
        )

    if event_type == "object_location":
        obj = _extract_object_name(text)
        location = _extract_location(text)
        places = [Place(name=location)] if location else []
        objects = [ObjectItem(name=obj, location=location)] if obj else []
        return Entities(objects=objects, places=places, time_reference=time_reference)

    if event_type == "person_mention":
        person = _extract_person(text)
        return Entities(people=[person] if person else [], time_reference=time_reference)

    if event_type == "appointment":
        appointment = _extract_appointment(text, time_reference)
        return Entities(appointments=[appointment], time_reference=time_reference)

    return Entities(time_reference=time_reference)


def _looks_like_medication(text: str) -> bool:
    return bool(re.search(r"\b(took|take|taken|had|used)\b", text)) and any(
        token in text for token in (*_MEDICATION_FORMS, "medicine", "medication", "insulin")
    )


def _looks_like_object_location(text: str) -> bool:
    has_named_object = any(re.search(rf"\b{re.escape(name)}\b", text) for name in _OBJECT_NAMES)
    has_generic_object = bool(
        re.search(
            r"\b(?:my|the)\s+[a-z][a-z\s]{0,30}\s+(?:is|was|are|were|kept|left|put|placed|stored|near|on|in|under|by|inside|behind)\b",
            text,
        )
    )
    has_location = any(re.search(rf"\b{re.escape(prefix)}\b", text) for prefix in _LOCATION_PREFIXES)
    has_placement_verb = any(verb in text for verb in ("kept", "left", "put", "placed", "stored", "is", "was"))
    return (has_named_object or has_generic_object) and (has_location or has_placement_verb)


def _looks_like_person_mention(text: str) -> bool:
    lowered = text.lower()
    if any(verb in lowered for verb in ("visited", "called", "came by", "saw", "talked to", "spoke with")):
        return True
    return bool(re.search(r"\bmy\s+(?:" + "|".join(_RELATIONSHIP_WORDS) + r")\b", lowered))


def _extract_time_reference(text: str) -> str | None:
    lowered = text.lower()
    for phrase in _TIME_REFERENCES:
        if phrase in lowered:
            return phrase
    return None


def _extract_medication(text: str) -> Medication | None:
    lowered = text.lower()
    if "insulin" in lowered:
        return Medication(name="insulin")

    match = re.search(
        r"\b(?:took|take|taken|had|used)\b\s+(?:my\s+)?(?P<name>[a-z0-9][a-z0-9\s-]{0,40}?)\s+(?P<form>pill|tablet|capsule)\b",
        lowered,
    )
    if match:
        form = match.group("form")
        name = f"{match.group('name').strip()} {form}".strip()
        return Medication(name=name, form=form)

    if "medicine" in lowered or "medication" in lowered:
        return Medication(name="medication")
    return None


def _extract_object_name(text: str) -> str | None:
    lowered = text.lower()
    for name in _OBJECT_NAMES:
        if name in lowered:
            return name

    match = re.search(
        r"\bmy\s+(?P<object>[a-z][a-z\s]{0,30}?)\s+(?:is|was|are|were|near|on|in|under|by|inside|behind)\b",
        lowered,
    )
    if match:
        return match.group("object").strip()
    return None


def _extract_location(text: str) -> str | None:
    for prefix in _LOCATION_PREFIXES:
        match = re.search(rf"\b{re.escape(prefix)}\b\s+([^.,;!?]+)", text, flags=re.IGNORECASE)
        if match:
            return f"{prefix} {match.group(1).strip()}"

    match = re.search(
        r"\b(?:is|was|are|were|kept|left|put|placed|stored)\b\s+([^.,;!?]+)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        candidate = match.group(1).strip()
        for prefix in _LOCATION_PREFIXES:
            if candidate.lower().startswith(prefix):
                return candidate
    return None


def _extract_person(text: str) -> Person | None:
    relationship_match = re.search(
        r"\b(?:my|My)\s+(?P<relationship>" + "|".join(_RELATIONSHIP_WORDS) + r")\s+(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        text,
    )
    if relationship_match:
        return Person(
            name=relationship_match.group("name"),
            relationship=relationship_match.group("relationship").lower(),
        )

    name_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text)
    if name_match:
        return Person(name=name_match.group(1))
    return None


def _extract_appointment(text: str, time_reference: str | None) -> Appointment:
    title_match = re.search(r"\b([A-Za-z]+\s+appointment)\b", text)
    doctor_match = re.search(r"\b(Dr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text)
    datetime_match = re.search(r"\b(?:on|at)\s+([^.,;!?]+)", text, flags=re.IGNORECASE)

    title = title_match.group(1) if title_match else "appointment"
    doctor = doctor_match.group(1) if doctor_match else None
    when = time_reference or (datetime_match.group(1).strip() if datetime_match else None)
    return Appointment(title=title, doctor=doctor, datetime=when)