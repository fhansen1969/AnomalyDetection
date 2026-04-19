"""Smoke tests for DeepIsolationForestModel.

Requires deepod>=0.4 and torch>=2.1 (deepod's minimum).
Tests are skipped when deepod is absent or the installed torch is too old.
"""

import sys
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Availability guards
# ---------------------------------------------------------------------------

def _deepod_usable() -> bool:
    """Return True only if deepod can actually instantiate a model."""
    try:
        import torch
        from packaging.version import Version
        if Version(torch.__version__) < Version("2.1"):
            return False
        from deepod.models import DeepIsolationForest  # noqa: F401
        return True
    except Exception:
        return False


DEEPOD_AVAILABLE = _deepod_usable()
skip_no_deepod = pytest.mark.skipif(
    not DEEPOD_AVAILABLE,
    reason="deepod not usable (not installed or torch<2.1)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data(n: int, d: int = 10) -> list:
    rng = np.random.default_rng(0)
    return [
        {
            "id": str(i),
            "timestamp": "2024-01-01T00:00:00",
            "features": {f"f{j}": float(v) for j, v in enumerate(rng.standard_normal(d))},
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeepIsolationForestModel:

    @pytest.fixture
    def model(self):
        from anomaly_detection.models.deep_iforest import DeepIsolationForestModel
        return DeepIsolationForestModel(
            name="deep_iforest_test",
            config={
                "n_ensemble": 2,
                "hidden_dims": "16",
                "rep_dim": 8,
                "epochs": 3,
                "batch_size": 32,
                "device": "cpu",
                "threshold": 0.0,
            },
        )

    def test_instantiation(self, model):
        assert model.name == "deep_iforest_test"
        assert model.is_trained is False

    @skip_no_deepod
    def test_fit_and_detect(self, model):
        train_data = _make_data(100)
        model.train(train_data)
        assert model.is_trained

        test_data = _make_data(10)
        results = model.detect(test_data)
        assert isinstance(results, list)
        for a in results:
            assert 0.0 <= a["score"] <= 1.0

    @skip_no_deepod
    def test_score_array_shape(self, model):
        """detect() output length must be ≤ input length."""
        train_data = _make_data(100)
        model.train(train_data)
        model.threshold = 0.0
        results = model.detect(_make_data(10))
        assert len(results) <= 10

    @skip_no_deepod
    def test_state_roundtrip(self, model):
        train_data = _make_data(100)
        model.train(train_data)

        state = model.get_state()
        from anomaly_detection.models.deep_iforest import DeepIsolationForestModel
        model2 = DeepIsolationForestModel("deep_iforest_test", {"threshold": 0.0, "device": "cpu"})
        model2.set_state(state)
        assert model2.is_trained
        assert model2.training_feature_names == model.training_feature_names
