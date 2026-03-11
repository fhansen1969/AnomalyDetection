"""Database status and health check routes."""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter

from api.state import app_state

logger = logging.getLogger("api_services")
router = APIRouter()


def _check_database_status_sync() -> Dict[str, Any]:
    """Synchronous helper to check database connectivity."""
    if hasattr(app_state.storage_manager, 'conn') and app_state.storage_manager.conn:
        try:
            cursor = app_state.storage_manager.conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return {
                "status": "healthy",
                "message": "Database connection is active",
                "connected": True,
                "type": app_state.storage_manager.type
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Database query failed: {str(e)}",
                "connected": False,
                "type": app_state.storage_manager.type
            }
    else:
        return {
            "status": "warning",
            "message": "No active database connection",
            "connected": False,
            "type": getattr(app_state.storage_manager, 'type', 'unknown')
        }


@router.get("/database/status", tags=["System"], response_model=Dict[str, Any])
async def check_database_status():
    """
    Check database connectivity and status.

    Returns:
        Database status information
    """
    if app_state.storage_manager is None:
        return {
            "status": "error",
            "message": "Storage manager not initialized",
            "connected": False
        }

    try:
        return await asyncio.to_thread(_check_database_status_sync)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error checking database status: {str(e)}",
            "connected": False
        }


def _get_database_metrics_sync() -> Dict[str, Any]:
    """
    Synchronous helper to get database metrics.
    Runs in thread executor to avoid blocking async event loop.
    """
    metrics = {}
    try:
        with app_state.storage_manager.get_connection() as conn:
            if conn:
                cursor = conn.cursor()

                # Count records in key tables
                tables = ["anomalies", "models", "processed_data", "jobs", "agent_activities"]
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        metrics[f"{table}_count"] = count
                    except Exception as e:
                        logging.error(f"Error counting {table}: {str(e)}")
                        metrics[f"{table}_count"] = -1

                # Check for recent activity
                try:
                    cursor.execute("""
                        SELECT MAX(created_at) as last_activity FROM anomalies
                        UNION ALL
                        SELECT MAX(created_at) FROM processed_data
                        UNION ALL
                        SELECT MAX(updated_at) FROM jobs
                        ORDER BY last_activity DESC LIMIT 1
                    """)
                    result = cursor.fetchone()
                    if result and result[0]:
                        metrics["last_activity"] = result[0].isoformat()
                except Exception as e:
                    logging.error(f"Error getting last activity: {str(e)}")
    except Exception as e:
        logging.error(f"Error getting database metrics: {str(e)}")

    return metrics


@router.get("/database/health", tags=["System"], response_model=Dict[str, Any])
async def database_health_check():
    """
    Comprehensive database health check with auto-recovery attempt.
    FIXED: Uses thread executor for synchronous database operations.

    Returns:
        Database health status and metrics
    """
    health = {
        "status": "unknown",
        "connected": False,
        "tables_verified": False,
        "connection_pool_status": None,
        "recent_activity": None,
        "storage_metrics": {},
        "timestamp": datetime.utcnow().isoformat()
    }

    if not app_state.storage_manager:
        health["status"] = "not_initialized"
        return health

    # Check connection (run blocking call in thread)
    is_connected = await asyncio.to_thread(app_state.storage_manager.check_connection)
    if is_connected:
        health["connected"] = True
        health["status"] = "healthy"

        # Get connection pool status
        if hasattr(app_state.storage_manager, 'connection_pool') and app_state.storage_manager.connection_pool:
            health["connection_pool_status"] = {
                "min_connections": app_state.storage_manager.connection_pool.minconn,
                "max_connections": app_state.storage_manager.connection_pool.maxconn,
                "closed": app_state.storage_manager.connection_pool.closed
            }

        # Check recent activity using thread executor
        try:
            metrics = await asyncio.to_thread(_get_database_metrics_sync)
            health["storage_metrics"] = metrics
            health["recent_activity"] = metrics.get("last_activity")
            health["tables_verified"] = True
        except Exception as e:
            health["error"] = str(e)
            health["status"] = "degraded"
    else:
        health["status"] = "disconnected"

        # Attempt reconnection (run blocking call in thread)
        logging.warning("Database disconnected, attempting reconnection...")
        reconnected = await asyncio.to_thread(app_state.storage_manager.reconnect)
        if reconnected:
            health["status"] = "recovered"
            health["connected"] = True
            health["recovery_time"] = datetime.utcnow().isoformat()
        else:
            health["status"] = "failed"

    return health
