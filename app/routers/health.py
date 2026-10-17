from fastapi import APIRouter
from app.schemas.transaction import HealthResponse
from app.utils.time import now_ist

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="HEALTHY",
        current_time=now_ist().isoformat()
    )