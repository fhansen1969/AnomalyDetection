"""
Centralized application state container.
Replaces scattered global variables with a single typed object.
"""
import threading
from typing import Dict, Any, Optional


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


# Singleton instance — imported by all routers
app_state = AppState()
