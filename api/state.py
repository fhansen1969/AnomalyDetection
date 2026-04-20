"""
Centralized application state container.
Replaces scattered global variables with a single typed object.
"""
import threading
from typing import Dict, Any, List, Optional, Set


class AppState:
    """Centralized application state. Single instance shared across all routers."""

    def __init__(self):
        self.config: Optional[Dict] = None
        self.storage_manager = None
        self.models: Dict[str, Any] = {}
        self.processors: Dict[str, Any] = {}
        self.collectors: Dict[str, Any] = {}
        self.agent_manager = None
        self.background_jobs: Dict[str, Any] = {}
        self.background_jobs_lock = threading.Lock()
        self.alert_manager = None
        self.last_training_data: Dict[str, Any] = {}
        self.websocket_connections: Dict[str, Any] = {}
        self.system_components: Dict[str, Any] = {}
        # Keyed by model_name → ScoreCalibrator (or None when load failed).
        # Populated lazily on first detection; None sentinel prevents repeated
        # filesystem probes when no calibrator has been fitted yet.
        self.calibrators: Dict[str, Any] = {}
        # In-memory alert log: populated by AlertManager.send_alert().
        # Supports GET /alerts, GET /alerts/stats, and per-alert actions.
        self.alert_store: List[Dict[str, Any]] = []
        self.alert_store_lock = threading.Lock()
        # Async tasks dispatching alerts (drained on shutdown by lifespan.py).
        self.alert_dispatch_tasks: Set[Any] = set()


# Singleton instance — imported by all routers
app_state = AppState()
