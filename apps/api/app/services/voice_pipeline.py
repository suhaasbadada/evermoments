import re

from app.schemas.memory import Appointment, Entities, EventType, Medication, ObjectItem, Person

_MEDICATION_RE = re.compile(r"\b(pill|tablet|capsule|medicine|medication|dose|took|take|taken)\b", re.I)
_OBJECT_RE = re.compile(r"\b(wallet|keys|phone|glasses|remote|bag|purse)\b", re.I)
_LOCATION_RE = re.compile(r"\b(near|in|on|at|under|by)\b\s+([^,.!?]+)", re.I)
_APPOINTMENT_RE = re.compile(r"\b(appointment|doctor|clinic|checkup|check-up|visit)\b", re.I)
_TIME_REF_RE = re.compile(
    r"\b(today|yesterday|tomorrow|this morning|this evening|after breakfast|after lunch|after dinner|morning|evening|night|\d{1,2}(?::\d{2})?\s?(?:am|pm))\b",
    re.I,
)
_PERSON_RE = re.compile(r"\b([A-Z][a-z]{1,20})\b")


def _time_reference(text: str) -> str | None:
    match = _TIME_REF_RE.search(text)
    return match.group(1).strip() if match else None


def _extract_medication(transcript: str) -> tuple[str, str | None]:
    m = re.search(r"\b(the\s+)?([a-z]+\s+pill)\b", transcript, re.I)
    if m:
        return m.group(2).strip(), "tablet"
    m = re.search(r"\b([a-z]+\s+(medicine|medication))\b", transcript, re.I)
    if m:
        return m.group(1).strip(), None
    return "medication", None


def _extract_object_location(transcript: str) -> tuple[str, str | None]:
    object_match = _OBJECT_RE.search(transcript)
    object_name = object_match.group(1).lower() if object_match else "item"
    location_match = _LOCATION_RE.search(transcript)
    location = None
    if location_match:
        location = f"{location_match.group(1).lower()} {location_match.group(2).strip()}"
    return object_name, location


def classify_and_extract(transcript: str) -> tuple[EventType, Entities]:
    text = transcript.strip()

    if _MEDICATION_RE.search(text):
        medication_name, medication_form = _extract_medication(text)
        return (
            "medication_intake",
            Entities(
                medications=[Medication(name=medication_name, form=medication_form)],
                time_reference=_time_reference(text),
            ),
        )

    object_match = _OBJECT_RE.search(text)
    location_match = _LOCATION_RE.search(text)
    if object_match and location_match:
        object_name, location = _extract_object_location(text)
        return (
            "object_location",
            Entities(objects=[ObjectItem(name=object_name, location=location)]),
        )

    if _APPOINTMENT_RE.search(text):
        doctor_match = re.search(r"\bDr\.?\s+([A-Z][a-z]+)\b", text)
        title = "Doctor appointment" if doctor_match else "Appointment"
        doctor = f"Dr. {doctor_match.group(1)}" if doctor_match else None
        return (
            "appointment",
            Entities(
                appointments=[Appointment(title=title, doctor=doctor)],
                time_reference=_time_reference(text),
            ),
        )

    person_matches = [name for name in _PERSON_RE.findall(text) if name.lower() not in {"i"}]
    if person_matches:
        return (
            "person_mention",
            Entities(people=[Person(name=person_matches[0])], time_reference=_time_reference(text)),
        )

    return (
        "general",
        Entities(time_reference=_time_reference(text)),
    )
