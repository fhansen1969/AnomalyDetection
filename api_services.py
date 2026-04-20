"""
Enhanced Anomaly Detection API Server — Entry Point.

This is the slim entry point for the API. All route handlers, Pydantic models,
background jobs, and utility functions have been decomposed into the api/ package:

  api/state.py         — AppState singleton (replaces 13 global variables)
  api/schemas.py       — All Pydantic request/response models
  api/helpers.py       — Shared utility functions
  api/extractors.py    — ConcreteFeatureExtractor class
  api/lifespan.py      — Lifespan handler, initialize_system(), sync_jobs_to_database()
  api/routers/         — 14 domain-specific router modules

Original monolithic version backed up to: backups/api_services_monolithic.py
"""
import argparse
import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_services")

# Ensure current directory is on sys.path for anomaly_detection package
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# ---------------------------------------------------------------------------
# Application state & lifespan
# ---------------------------------------------------------------------------
from api.state import app_state
from api.lifespan import lifespan
from api.helpers import load_config, get_default_agent_workflow

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from api.routers import (
    health,
    system,
    models,
    detection,
    jobs,
    anomalies,
    correlation,
    agents,
    data,
    alerts,
    database,
    websocket,
    export,
    triage,
)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Enhanced Anomaly Detection API",
    description="API for anomaly detection system with real-time notifications and correlation analysis",
    version="2.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(health.router)
app.include_router(system.router)
app.include_router(models.router)
app.include_router(detection.router)
app.include_router(jobs.router)
app.include_router(anomalies.router)
app.include_router(correlation.router)
app.include_router(agents.router)
app.include_router(data.router)
app.include_router(alerts.router)
app.include_router(database.router)
app.include_router(websocket.router)
app.include_router(export.router)
app.include_router(triage.router)

# ---------------------------------------------------------------------------
# React SPA static file serving
# Must come AFTER all API routers so /api/* routes take priority.
# ---------------------------------------------------------------------------
_UI_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "dist")
if os.path.isdir(_UI_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_UI_DIST, "assets")), name="assets")

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        return FileResponse(os.path.join(_UI_DIST, "favicon.svg"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(os.path.join(_UI_DIST, "index.html"))

# ---------------------------------------------------------------------------
# Backward-compatible exports
# Used by: utils/test_agents.py
#   from api_services import agent_manager, config, get_default_agent_workflow
# ---------------------------------------------------------------------------
# These are module-level references that reflect the current state of app_state.
# After lifespan startup runs, app_state.config and app_state.agent_manager are populated.
# For import compatibility, we expose property-like access via the module namespace.

config = None  # Populated during CLI startup / lifespan
agent_manager = None  # Populated during lifespan


def _update_compat_exports():
    """Update backward-compatible module-level exports from app_state."""
    global config, agent_manager
    config = app_state.config
    agent_manager = app_state.agent_manager


# get_default_agent_workflow is re-exported from api.helpers (imported above)

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="Enhanced Anomaly Detection API Server")
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--auto-init",
        action="store_true",
        default=True,
        help="Automatically initialize the system (default: True)"
    )
    parser.add_argument(
        "--ensure-db",
        action="store_true",
        default=True,
        help="Ensure database is connected before starting (default: True)"
    )

    args = parser.parse_args()

    # Set up logging level
    if args.verbose:
        logging.getLogger("api_services").setLevel(logging.DEBUG)

    # Load config but DO NOT initialize system in main thread
    # System initialization (including StorageManager creation) must happen in async context
    if args.config:
        try:
            config_dict = load_config(args.config)

            # Store config in app_state and module-level export
            app_state.config = config_dict
            config = config_dict

            # Store config path in environment for lifespan fallback
            os.environ["CONFIG_PATH"] = args.config

            logging.info(f"Configuration loaded from {args.config}")
            logging.info("CRITICAL: System initialization deferred to async startup to prevent mutex deadlock")

        except Exception as e:
            logging.error(f"Failed to load configuration: {str(e)}")
            if args.auto_init:
                logging.error("Exiting due to configuration load failure")
                sys.exit(1)
            else:
                logging.info("Server will start but system components are not initialized")

    # Start the server
    # NOTE: Using string format for reload compatibility. Config is loaded via
    # environment variable fallback in lifespan function.
    uvicorn.run(
        "api_services:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.verbose else "info"
    )
