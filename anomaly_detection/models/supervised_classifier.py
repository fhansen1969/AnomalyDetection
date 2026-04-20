"""Supervised anomaly classifier — stub (not yet implemented)."""
from pathlib import Path
from typing import Any, Dict

FEEDBACK_DIR = Path("storage/feedback")


class _SupervisedClassifierStub:
    MIN_SAMPLES_EACH_CLASS = 50
    is_trained = False
    _version = 0
    training_stats: Dict[str, Any] = {}

    def retrain(self, max_features: int = 90) -> Dict[str, Any]:
        return {"status": "skipped", "message": "supervised_classifier not yet implemented"}


_instance: _SupervisedClassifierStub | None = None


def get_classifier() -> _SupervisedClassifierStub:
    global _instance
    if _instance is None:
        _instance = _SupervisedClassifierStub()
    return _instance
