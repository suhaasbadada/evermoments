from pydantic import BaseModel, Field

from app.schemas.memory import Entities, EventType


class STTExtractRequest(BaseModel):
    transcript: str = Field(min_length=1)


class STTExtractResponse(BaseModel):
    transcript: str
    event_type: EventType
    entities: Entities = Field(default_factory=Entities)