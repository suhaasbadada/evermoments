from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile

from app.schemas.ingest import STTExtractRequest, STTExtractResponse
from app.services.voice_pipeline import classify_and_extract

router = APIRouter()


def _clean_transcript(value: str) -> str:
    transcript = value.strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="transcript must not be empty")
    return transcript


@router.post("/stt", response_model=STTExtractResponse)
async def stt_extract(request: Request) -> STTExtractResponse:
    content_type = request.headers.get("content-type", "").lower()

    transcript = ""
    if "application/json" in content_type:
        try:
            body = STTExtractRequest.model_validate(await request.json())
            transcript = body.transcript
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"invalid JSON payload: {exc}") from exc
    elif "multipart/form-data" in content_type:
        form = await request.form()
        transcript_field = form.get("transcript")
        if isinstance(transcript_field, str) and transcript_field.strip():
            transcript = transcript_field
        else:
            upload = form.get("audio") or form.get("file")
            if not isinstance(upload, UploadFile):
                raise HTTPException(status_code=422, detail="expected multipart field 'audio' or 'file'")
            if upload.content_type and not upload.content_type.startswith("text/plain"):
                raise HTTPException(
                    status_code=415,
                    detail="demo STT endpoint accepts text/plain uploads or a transcript form field",
                )
            transcript = (await upload.read()).decode("utf-8", errors="ignore")
    else:
        raise HTTPException(
            status_code=415,
            detail="unsupported content type; use application/json or multipart/form-data",
        )

    transcript = _clean_transcript(transcript)
    event_type, entities = classify_and_extract(transcript)
    return STTExtractResponse(transcript=transcript, event_type=event_type, entities=entities)


# Backward-compatible alias for older integration docs.
@router.post("/ingest/voice", response_model=STTExtractResponse)
async def ingest_voice_alias(request: Request) -> STTExtractResponse:
    return await stt_extract(request)
