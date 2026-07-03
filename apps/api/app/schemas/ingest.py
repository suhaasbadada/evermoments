from pydantic import BaseModel, model_validator

from app.schemas.memory import MemoryEvent, MemoryWarning, SourceType


class VoiceNoteIngestRequest(BaseModel):
    patient_id: str
    transcript: str | None = None
    audio_base64: str | None = None
    audio_mime_type: str | None = None
    recorded_at: str | None = None
    event_id: str | None = None
    source: SourceType = "voice_note"

    @model_validator(mode="after")
    def _validate_payload(self) -> "VoiceNoteIngestRequest":
        has_transcript = bool(self.transcript and self.transcript.strip())
        has_audio = bool(self.audio_base64 and self.audio_base64.strip())

        if has_transcript == has_audio:
            raise ValueError("provide exactly one of transcript or audio_base64")
        if has_audio and not (self.audio_mime_type and self.audio_mime_type.strip()):
            raise ValueError("audio_mime_type is required when audio_base64 is provided")
        return self


class VoiceNoteIngestResponse(BaseModel):
    event_id: str
    status: str
    transcript: str
    stt_provider: str
    memory_event: MemoryEvent
    warning: MemoryWarning | None = None