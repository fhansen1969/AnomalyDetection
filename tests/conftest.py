"""
Pytest configuration for deep-model unit tests.

anomaly_detection/models/__init__.py eagerly imports AutoencoderModel and
EnsembleModel (both pull in PyTorch), plus anomaly_detection/__init__.py
pulls in AgentManager (langchain/gRPC). These trigger an abseil mutex
deadlock on torch 1.13 / macOS ARM when langsmith's gRPC also initialises.

We stub those sub-modules with MagicMock BEFORE collection so that the
deep-model tests can run without paying that cost.  The stubs preserve
__path__ so Python can still descend into real sub-module files.

Modules we need to work (deep_iforest, deep_sad_model, deep_sad/) are
intentionally left un-stubbed so they load from disk normally.
"""

import os
import sys
import pathlib
from unittest.mock import MagicMock

# Stop langchain / langsmith from opening gRPC connections at import time
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_API_KEY", "disabled")

_root = pathlib.Path(__file__).parent.parent


def _pkg_stub(rel_path: str) -> MagicMock:
    """MagicMock stub with __path__ pointing at the real directory."""
    stub = MagicMock()
    stub.__path__ = [str(_root / rel_path)]
    stub.__package__ = rel_path.replace("/", ".")
    return stub


# Stub gRPC-pulling framework packages (no torch — tests need real torch)
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
        sys.modules[_name] = MagicMock()

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
}
for _name, _stub in _pkg_stubs.items():
    if _name not in sys.modules:
        sys.modules[_name] = _stub
