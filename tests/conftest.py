"""
Pytest configuration shared across the tests/ package.

Pre-populates sys.modules with stubs so that anomaly_detection's __init__.py
can be imported without triggering gRPC/mutex deadlocks or requiring live
infrastructure (databases, message brokers, etc.).

Covers: deep-model tests, AAD reweighter tests (pure numpy + sklearn),
calibration tests, and drift tests.

NOTE: torch is intentionally NOT stubbed — deep-model tests need real torch.
Packages that need real __path__ navigation (anomaly_detection sub-packages)
use _pkg_stub to preserve file-system discovery of un-stubbed sub-modules.
"""

import os
import sys
import types
import pathlib
from unittest.mock import MagicMock

# Stop langchain / langsmith from opening gRPC connections at import time
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_API_KEY", "disabled")

_root = pathlib.Path(__file__).parent.parent


class _AutoMockModule(types.ModuleType):
    """Stub module returning MagicMock for any undefined attribute access.

    Also satisfies importlib.util.find_spec checks (needs __spec__ and __path__).
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.__spec__ = types.SimpleNamespace(
            name=name, submodule_search_locations=[]
        )
        self.__path__: list = []
        self.__package__ = name

    def __getattr__(self, item: str):
        mock = MagicMock(name=f"{self.__name__}.{item}")
        setattr(self, item, mock)
        return mock


def _pkg_stub(rel_path: str) -> MagicMock:
    """MagicMock stub with __path__ pointing at the real directory on disk."""
    stub = MagicMock()
    stub.__path__ = [str(_root / rel_path)]
    stub.__package__ = rel_path.replace("/", ".")
    return stub


# Stub gRPC-pulling framework packages.
# torch is intentionally NOT stubbed — deep-model tests (test_deep_iforest,
# test_deep_sad) require real torch to run.
_framework_stubs = [
    "langgraph",
    "langchain_core",
    "langsmith",
    "ollama",
    "transformers",
    "sentence_transformers",
]
for _name in _framework_stubs:
    if _name not in sys.modules:
        sys.modules[_name] = _AutoMockModule(_name)

# Infrastructure stubs — psycopg2, kafka, elasticsearch are not installed
# in the test environment; mock them so unit tests don't import-fail.
_infra_stubs = [
    "psycopg2",
    "psycopg2.pool",
    "psycopg2.extras",
    "kafka",
    "kafka.consumer",
    "kafka.consumer.consumer_record",
    "kafka.errors",
    "elasticsearch",
]
for _name in _infra_stubs:
    if _name not in sys.modules:
        sys.modules[_name] = _AutoMockModule(_name)

# Stub heavy anomaly_detection sub-packages not under test.
# Give models a real __path__ so deep_iforest.py / deep_sad_model.py are found.
_pkg_stubs: dict = {
    "anomaly_detection.agents":               _pkg_stub("anomaly_detection/agents"),
    "anomaly_detection.alerts":               _pkg_stub("anomaly_detection/alerts"),
    "anomaly_detection.collectors":           _pkg_stub("anomaly_detection/collectors"),
    "anomaly_detection.storage":              _pkg_stub("anomaly_detection/storage"),
    # Keep models package navigable but stub its __init__ (avoids eager torch imports)
    "anomaly_detection.models":               _pkg_stub("anomaly_detection/models"),
    # Stub heavy model files that import torch at module level
    "anomaly_detection.models.autoencoder":   MagicMock(),
    "anomaly_detection.models.ganbased":      MagicMock(),
    "anomaly_detection.models.ensemble":      MagicMock(),
    "anomaly_detection.models.one_class_svm": MagicMock(),
    "anomaly_detection.models.statistical":   MagicMock(),
    "anomaly_detection.models.isolation_forest": MagicMock(),
    "anomaly_detection.models.lstm_model":    MagicMock(),
}
for _name, _stub in _pkg_stubs.items():
    if _name not in sys.modules:
        sys.modules[_name] = _stub
