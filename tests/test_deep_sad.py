"""Smoke tests for DeepSADModel (vendored — only requires torch).

All tests require torch; skipped when torch is absent.
"""

import numpy as np
import pytest

try:
    import torch  # noqa: F401
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

skip_no_torch = pytest.mark.skipif(not TORCH_AVAILABLE, reason="torch not installed")


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

class TestDeepSADModel:

    @pytest.fixture
    def model(self):
        from anomaly_detection.models.deep_sad_model import DeepSADModel
        return DeepSADModel(
            name="deep_sad_test",
            config={
                "hidden_dims": [16, 8],
                "rep_dim": 4,
                "lr": 1e-3,
                "n_epochs": 3,
                "batch_size": 32,
                "device": "cpu",
                "threshold": 0.0,
            },
        )

    def test_instantiation(self, model):
        assert model.name == "deep_sad_test"
        assert model.is_trained is False

    @skip_no_torch
    def test_unsupervised_fit_and_detect(self, model):
        train_data = _make_data(100)
        model.train(train_data)
        assert model.is_trained

        test_data = _make_data(10)
        results = model.detect(test_data)
        assert isinstance(results, list)
        for a in results:
            assert 0.0 <= a["score"] <= 1.0

    @skip_no_torch
    def test_score_array_shape(self, model):
        """score() must return an array whose length equals input length."""
        train_data = _make_data(100)
        model.train(train_data)
        scores = model.score(_make_data(10))
        assert scores.shape == (10,), f"Expected (10,), got {scores.shape}"

    @skip_no_torch
    def test_semisupervised_fit_with_labels(self, model):
        """Training with a label vector must complete without error."""
        data = _make_data(100)
        labels = [1] * 10 + [-1] * 5 + [0] * 85
        model.fit(data, labels=labels)
        assert model.is_trained
        scores = model.score(_make_data(10))
        assert scores.shape == (10,)

    @skip_no_torch
    def test_retrain_on_feedback(self, model):
        """retrain_on_feedback should refit without raising."""
        model.train(_make_data(100))
        feedback = _make_data(20)
        fb_labels = [1] * 10 + [-1] * 10
        model.retrain_on_feedback(feedback, fb_labels, unlabeled_corpus=_make_data(30))
        assert model.is_trained

    @skip_no_torch
    def test_state_roundtrip(self, model):
        model.train(_make_data(100))
        state = model.get_state()

        from anomaly_detection.models.deep_sad_model import DeepSADModel
        model2 = DeepSADModel(
            "deep_sad_test",
            {"hidden_dims": [16, 8], "rep_dim": 4, "n_epochs": 3, "device": "cpu", "threshold": 0.0},
        )
        model2.set_state(state)
        assert model2.is_trained
        scores = model2.score(_make_data(5))
        assert scores.shape == (5,)
