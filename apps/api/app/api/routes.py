from fastapi import APIRouter

from app.api.ingest_routes import router as ingest_router
from app.api.memory_routes import router as memory_router

router = APIRouter()
router.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
router.include_router(memory_router, prefix="/memory", tags=["memory"])


@router.get("/ping", tags=["system"])
def ping() -> dict[str, str]:
    return {"message": "pong"}
