"""
Pytest configuration for unit tests.

anomaly_detection/__init__.py eagerly imports AgentManager (langchain/gRPC)
and AutoencoderModel (PyTorch), both of which block on mutexes during test
collection.  We stub those sub-modules with MagicMock BEFORE collection so
that the AAD unit tests (pure numpy + sklearn) don't pay that cost.

Sub-modules that the tests DO need (anomaly_detection.models.isolation_forest,
anomaly_detection.active_learning.*) are loaded normally from their files.
We achieve this by giving the stub packages a proper __path__ so that Python
can still find sub-module files on disk.
"""

import os
import sys
import pathlib
from unittest.mock import MagicMock

# Tell langsmith / langchain not to open any gRPC connections
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_API_KEY", "disabled")

_root = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Stub heavyweight framework packages so their import-time side-effects
# (gRPC init, CUDA init, etc.) don't run during collection.
# ---------------------------------------------------------------------------
_framework_stubs = [
    "torch",
    "torchvision",
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


# ---------------------------------------------------------------------------
# Stub anomaly_detection sub-packages that pull in heavy dependencies.
# Give each stub a __path__ pointing at the real directory on disk so that
# Python can still descend into sub-modules (e.g. .isolation_forest) using
# normal file-system discovery.
# ---------------------------------------------------------------------------
def _pkg_stub(rel_path: str) -> MagicMock:
    stub = MagicMock()
    stub.__path__ = [str(_root / rel_path)]
    stub.__package__ = rel_path.replace("/", ".")
    return stub


_pkg_stubs = {
    "anomaly_detection.agents":         _pkg_stub("anomaly_detection/agents"),
    "anomaly_detection.alerts":         _pkg_stub("anomaly_detection/alerts"),
    "anomaly_detection.collectors":     _pkg_stub("anomaly_detection/collectors"),
    "anomaly_detection.storage":        _pkg_stub("anomaly_detection/storage"),
    # stub models *package* but keep __path__ so isolation_forest.py is found
    "anomaly_detection.models":         _pkg_stub("anomaly_detection/models"),
    # stub the heavy model files that import torch/gRPC
    "anomaly_detection.models.autoencoder":  MagicMock(),
    "anomaly_detection.models.ganbased":     MagicMock(),
    "anomaly_detection.models.lstm_model":   MagicMock(),
    "anomaly_detection.models.ensemble":     MagicMock(),
}
for _name, _stub in _pkg_stubs.items():
    if _name not in sys.modules:
        sys.modules[_name] = _stub
