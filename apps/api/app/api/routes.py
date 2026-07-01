from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", tags=["system"])
def ping() -> dict[str, str]:
    return {"message": "pong"}
