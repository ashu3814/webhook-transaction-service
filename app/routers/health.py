from fastapi import APIRouter
from app.utils.time import now_ist
from app.utils.logger import logger

router = APIRouter(tags=["health"])

@router.get("/")
async def health_check():
    """Simple health check"""
    logger.info("✅ Health check")
    return {
        "status": "HEALTHY",
        "current_time": now_ist().isoformat()
    }