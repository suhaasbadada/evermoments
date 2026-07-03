from fastapi import APIRouter, HTTPException

from app.schemas.ingest import VoiceNoteIngestRequest, VoiceNoteIngestResponse
from app.services.voice_pipeline import ingest_voice_note

router = APIRouter()


@router.post("/voice-note", response_model=VoiceNoteIngestResponse)
def ingest_voice_note_route(req: VoiceNoteIngestRequest) -> VoiceNoteIngestResponse:
    """Turn a raw voice-note payload into a structured MemoryEvent and store it."""
    try:
        return ingest_voice_note(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc