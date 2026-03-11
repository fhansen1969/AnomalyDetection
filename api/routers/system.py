"""System management routes."""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.state import app_state
from api.schemas import ConfigModel
from api.helpers import load_config

logger = logging.getLogger("api_services")
router = APIRouter()


@router.post("/init", tags=["System"], response_model=Dict[str, Any])
async def initialize(config_model: ConfigModel):
    """
    Initialize the system with configuration.

    Args:
        config_model: Configuration model with path to config file

    Returns:
        System status
    """
    try:
        config_dict = load_config(config_model.config_path)

        # Import initialize_system from lifespan module
        from api.lifespan import initialize_system
        initialize_system(config_dict)

        return {
            "status": "initialized",
            "models": list(app_state.models.keys()),
            "processors": list(app_state.processors.keys()),
            "collectors": list(app_state.collectors.keys()),
            "agent_manager": app_state.agent_manager is not None,
            "alert_manager": app_state.alert_manager is not None,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Error initializing system: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error initializing system: {str(e)}")


@router.get("/config", tags=["System"], response_model=Dict[str, Any])
async def get_config():
    """
    Get the current system configuration.

    Returns:
        Current configuration
    """
    if app_state.config is None:
        raise HTTPException(status_code=404, detail="System not initialized")

    # Remove any sensitive information
    filtered_config = app_state.config.copy()
    if "database" in filtered_config and "connection" in filtered_config["database"]:
        if "password" in filtered_config["database"]["connection"]:
            filtered_config["database"]["connection"]["password"] = "****"

    if "alerts" in filtered_config and "webhook" in filtered_config["alerts"]:
        if "auth_token" in filtered_config["alerts"]["webhook"]:
            filtered_config["alerts"]["webhook"]["auth_token"] = "****"

    return filtered_config


@router.get("/system/status", tags=["System"], response_model=Dict[str, Any])
async def get_system_status():
    """
    Get the current status of the system components.

    Returns:
        System status information
    """
    status = {
        "status": "healthy" if app_state.config is not None else "not_initialized",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.1.0",
        "initialized": app_state.config is not None,
        "components": {
            "models": {
                "count": len(app_state.models),
                "available": list(app_state.models.keys())
            },
            "processors": {
                "count": len(app_state.processors),
                "available": list(app_state.processors.keys())
            },
            "collectors": {
                "count": len(app_state.collectors),
                "available": list(app_state.collectors.keys())
            },
            "storage": {
                "available": app_state.storage_manager is not None,
                "type": app_state.storage_manager.type if app_state.storage_manager else None
            },
            "agents": {
                "available": app_state.agent_manager is not None
            },
            "alerts": {
                "available": app_state.alert_manager is not None,
                "enabled": app_state.alert_manager.enabled if app_state.alert_manager else False
            }
        },
        "jobs": {
            "total": len(app_state.background_jobs),
            "running": sum(1 for job in app_state.background_jobs.values() if job["status"] == "running"),
            "completed": sum(1 for job in app_state.background_jobs.values() if job["status"] == "completed"),
            "failed": sum(1 for job in app_state.background_jobs.values() if job["status"] == "failed")
        }
    }

    return status


@router.post("/system/cleanup", tags=["System"], response_model=Dict[str, Any])
async def cleanup_system():
    """
    Clean up temporary files and completed jobs.

    Returns:
        Cleanup status
    """
    try:
        # Clean up background jobs
        old_jobs = {}
        for job_id, job in app_state.background_jobs.items():
            if job["status"] in ["completed", "failed"]:
                if job.get("created_at") and (
                    datetime.fromisoformat(job["created_at"])
                    < (datetime.utcnow() - timedelta(days=7))
                ):
                    old_jobs[job_id] = job

        # Remove old jobs
        for job_id in old_jobs:
            del app_state.background_jobs[job_id]

        return {
            "status": "success",
            "jobs_cleaned": len(old_jobs),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Error cleaning up system: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error cleaning up system: {str(e)}")


@router.post("/system/shutdown", tags=["System"], response_model=Dict[str, Any])
async def shutdown_system():
    """
    Gracefully shut down the system.

    Returns:
        Shutdown status
    """
    if app_state.storage_manager:
        try:
            await asyncio.to_thread(lambda: app_state.storage_manager.close())
        except Exception as e:
            logging.error(f"Error closing storage manager: {str(e)}")

    return {
        "status": "shutdown_initiated",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/status/realtime", tags=["Status"])
async def get_realtime_status():
    """
    Get real-time status of the system as a streaming response.
    This endpoint continuously sends system status updates.
    """
    async def generate():
        while True:
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "initialized": app_state.config is not None,
                "models": {
                    "count": len(app_state.models),
                    "active": sum(1 for model in app_state.models.values() if hasattr(model, 'model_state') and model.model_state)
                },
                "jobs": {
                    "total": len(app_state.background_jobs),
                    "running": sum(1 for job in app_state.background_jobs.values() if job["status"] == "running"),
                    "completed": sum(1 for job in app_state.background_jobs.values() if job["status"] == "completed"),
                    "failed": sum(1 for job in app_state.background_jobs.values() if job["status"] == "failed")
                },
                "alerts_enabled": app_state.alert_manager.enabled if app_state.alert_manager else False
            }

            yield f"data: {json.dumps(status)}\n\n"

            await asyncio.sleep(2)

    return StreamingResponse(generate(), media_type="text/event-stream")
