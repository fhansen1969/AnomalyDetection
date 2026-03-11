"""Health check routes."""
import logging
from datetime import datetime

from fastapi import APIRouter

from api.state import app_state

logger = logging.getLogger("api_services")
router = APIRouter()


@router.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.1.0",
        "initialized": app_state.config is not None,
        "system_time": datetime.utcnow().isoformat()
    }


@router.get("/health", tags=["Health"])
async def health_check_detailed():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.1.0",
        "initialized": app_state.config is not None,
        "system_time": datetime.utcnow().isoformat()
    }
