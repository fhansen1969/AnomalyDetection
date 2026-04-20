"""Health check routes."""
import logging
from datetime import datetime
from typing import Any, Dict

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


def check_score_distribution() -> Dict[str, Any]:
    """Check anomaly score distribution across trained models for health sentinel RC-04.

    Returns a dict with at minimum:
      healthy: bool
      message: str
    """
    if not app_state.models:
        return {"healthy": True, "message": "no models loaded — skipping distribution check"}

    issues = []
    for name, model in app_state.models.items():
        perf = getattr(model, "performance", {})
        if perf:
            precision = perf.get("precision", 1.0)
            recall = perf.get("recall", 1.0)
            if precision < 0.1 and recall < 0.1:
                issues.append(f"{name}: both precision and recall near zero")

    if issues:
        return {
            "healthy": False,
            "message": "Score distribution check: " + "; ".join(issues),
        }
    return {
        "healthy": True,
        "message": f"{len(app_state.models)} model(s) OK",
    }
