"""
Pytest configuration for the tests/ package.

Pre-populates sys.modules with lightweight stubs for heavy or network-dependent
packages so that anomaly_detection's __init__.py can be imported without
triggering native-extension deadlocks or requiring live infrastructure.
"""
import sys
import types
from unittest.mock import MagicMock


class _AutoMockModule(types.ModuleType):
    """A stub module that returns MagicMock for any undefined attribute access.

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
        # Return a MagicMock for anything not explicitly defined.
        mock = MagicMock(name=f"{self.__name__}.{item}")
        setattr(self, item, mock)
        return mock


_MOCK_PACKAGES = [
    # Database
    "psycopg2",
    "psycopg2.pool",
    "psycopg2.extras",
    # Messaging
    "kafka",
    "kafka.consumer",
    "kafka.consumer.consumer_record",
    "kafka.errors",
    # Deep learning
    "torch",
    "torch.nn",
    "torch.optim",
    "torch.utils",
    "torch.utils.data",
    # NLP / embeddings  (pulled in by feature_extractor → sentence_transformers)
    "sentence_transformers",
    "transformers",
    # Agent framework
    "langgraph",
    "langgraph.graph",
    "langgraph.graph.message",
    "langgraph.prebuilt",
    # LLM client
    "ollama",
    # Search
    "elasticsearch",
]

for _pkg in _MOCK_PACKAGES:
    if _pkg not in sys.modules:
        sys.modules[_pkg] = _AutoMockModule(_pkg)
