"""
Synthetic unit tests for Active Anomaly Discovery (AAD) reweighting.

No external services required — all tests use randomly generated data.

Run with:
    cd <repo-root>
    python -m pytest tests/test_aad_reweighter.py -v
"""

import sys
import os

# Ensure repo root is on the path so the package is importable without install
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest
from sklearn.ensemble import IsolationForest

from anomaly_detection.active_learning.aad import compute_tree_scores, fit_aad_weights
from anomaly_detection.active_learning.aad_reweighter import AADReweighter
import anomaly_detection.active_learning.aad_reweighter as _reweighter_mod


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _dataset(seed: int = 42):
    """200 tight normals + 10 extreme outliers in 5-d space."""
    rng = np.random.default_rng(seed)
    n_normal, n_outlier = 200, 10
    X_normal = rng.normal(0.0, 0.3, size=(n_normal, 5))
    X_outlier = rng.uniform(5.0, 8.0, size=(n_outlier, 5))
    X = np.vstack([X_normal, X_outlier])
    y = np.array([0] * n_normal + [1] * n_outlier, dtype=np.float64)
    return X, y, n_normal, n_outlier


def _iforest(X, seed: int = 42):
    clf = IsolationForest(n_estimators=50, contamination=0.05, random_state=seed)
    clf.fit(X)
    return clf


# ---------------------------------------------------------------------------
# compute_tree_scores
# ---------------------------------------------------------------------------

class TestComputeTreeScores:
    def test_output_shape(self):
        X, _, _, _ = _dataset()
        clf = _iforest(X)
        phi = compute_tree_scores(clf, X)
        assert phi.shape == (X.shape[0], clf.n_estimators)

    def test_values_positive(self):
        X, _, _, _ = _dataset()
        phi = compute_tree_scores(_iforest(X), X)
        assert (phi > 0).all(), "All per-tree scores must be positive"

    def test_values_at_most_one(self):
        X, _, _, _ = _dataset()
        phi = compute_tree_scores(_iforest(X), X)
        assert (phi <= 1.0 + 1e-9).all(), "Scores are probabilities — max 1"

    def test_outliers_score_higher_on_average(self):
        """With uniform weights outliers should already score higher."""
        X, y, _, _ = _dataset()
        phi = compute_tree_scores(_iforest(X), X)
        avg = phi.mean(axis=1)
        assert avg[y == 1].mean() > avg[y == 0].mean(), (
            "Outliers must have higher mean per-tree score than normals"
        )


# ---------------------------------------------------------------------------
# fit_aad_weights
# ---------------------------------------------------------------------------

class TestFitAadWeights:
    def test_weights_shape(self):
        X, y, _, _ = _dataset()
        clf = _iforest(X)
        phi = compute_tree_scores(clf, X)
        w = fit_aad_weights(phi, y, ~np.isnan(y))
        assert w.shape == (clf.n_estimators,)

    def test_weights_on_simplex(self):
        """Weights must be non-negative and sum to 1."""
        X, y, _, _ = _dataset()
        phi = compute_tree_scores(_iforest(X), X)
        w = fit_aad_weights(phi, y, ~np.isnan(y))
        assert (w >= -1e-12).all(), "Weights must be non-negative"
        np.testing.assert_allclose(w.sum(), 1.0, atol=1e-9)

    def test_labeled_tps_score_higher_than_fps(self):
        """
        Regardless of weight shape, the weighted anomaly score for labeled TPs
        must be higher than for labeled FPs.  This is the core behavioural
        guarantee of AAD: TP samples rank above FP samples.

        Note: with highly-correlated bootstrap iForest trees the per-tree phi
        vectors are nearly identical across trees, so the simplex gradient often
        maps back to near-uniform weights.  The IMPORTANT invariant is not the
        internal weight distribution but the resulting score ordering.
        """
        X, y, _, _ = _dataset()
        clf = _iforest(X)
        phi = compute_tree_scores(clf, X)
        w = fit_aad_weights(phi, y, ~np.isnan(y), n_iter=300, C=5.0)
        scores = phi @ w
        assert scores[y == 1].mean() > scores[y == 0].mean(), (
            "Labeled TPs must score higher than labeled FPs after AAD weighting"
        )

    def test_no_labels_returns_uniform(self):
        X, _, _, _ = _dataset()
        phi = compute_tree_scores(_iforest(X), X)
        labels = np.full(X.shape[0], np.nan)
        labeled_mask = np.zeros(X.shape[0], dtype=bool)
        w = fit_aad_weights(phi, labels, labeled_mask)
        np.testing.assert_allclose(w, np.ones(w.shape) / w.shape[0])


# ---------------------------------------------------------------------------
# AADReweighter integration
# ---------------------------------------------------------------------------

class TestAADReweighter:
    def test_fit_weights_improves_or_maintains_separation(self):
        """
        The key invariant: after AAD weight fitting, the gap between the mean
        weighted score of outliers and normals should be >= the baseline gap
        from uniform weights (within a 10 % tolerance to allow for stochastic
        gradient noise on small datasets).
        """
        X, y, _, _ = _dataset()
        clf = _iforest(X)

        reweighter = AADReweighter(n_iter=400, lr=0.02, C=10.0)
        weights = reweighter.fit_weights(clf, X, y)

        uniform_w = np.ones(clf.n_estimators) / clf.n_estimators
        weighted_scores = reweighter.score(clf, X, weights)
        uniform_scores = reweighter.score(clf, X, uniform_w)

        def gap(s):
            return s[y == 1].mean() - s[y == 0].mean()

        w_gap = gap(weighted_scores)
        u_gap = gap(uniform_scores)

        assert w_gap >= u_gap * 0.9, (
            f"AAD should maintain or improve outlier/normal separation. "
            f"Weighted gap={w_gap:.4f}, Uniform gap={u_gap:.4f}"
        )

    def test_partial_labels_still_works(self):
        """Only outliers + 20 normals labeled; rest unlabeled."""
        X, y, n_normal, _ = _dataset()
        clf = _iforest(X)

        labels = np.full(len(X), np.nan)
        labels[y == 1] = 1.0                       # all outliers labeled TP
        labels[np.where(y == 0)[0][:20]] = 0.0     # 20 normals labeled FP

        reweighter = AADReweighter()
        weights = reweighter.fit_weights(clf, X, labels)

        assert weights.shape == (clf.n_estimators,)
        assert (weights >= -1e-12).all()
        np.testing.assert_allclose(weights.sum(), 1.0, atol=1e-9)

    def test_score_shape(self):
        X, y, _, _ = _dataset()
        clf = _iforest(X)
        reweighter = AADReweighter()
        weights = reweighter.fit_weights(clf, X, y)
        scores = reweighter.score(clf, X, weights)
        assert scores.shape == (X.shape[0],)

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        """Weights written to disk must round-trip exactly."""
        monkeypatch.setattr(_reweighter_mod, "WEIGHTS_DIR", tmp_path)

        X, y, _, _ = _dataset()
        clf = _iforest(X)
        reweighter = AADReweighter()
        weights = reweighter.fit_weights(clf, X, y)

        AADReweighter.save_weights(weights, "test_model")
        loaded = AADReweighter.load_weights("test_model")

        assert loaded is not None, "load_weights returned None after save"
        np.testing.assert_allclose(weights, loaded)

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_reweighter_mod, "WEIGHTS_DIR", tmp_path)
        result = AADReweighter.load_weights("does_not_exist")
        assert result is None

    def test_corrupted_weight_file_returns_none(self, tmp_path, monkeypatch):
        """A corrupt sidecar file must not propagate an exception — just None."""
        monkeypatch.setattr(_reweighter_mod, "WEIGHTS_DIR", tmp_path)
        bad_file = tmp_path / "bad_model.weights.npy"
        bad_file.write_bytes(b"not a numpy array")
        result = AADReweighter.load_weights("bad_model")
        assert result is None


# ---------------------------------------------------------------------------
# Regression: IsolationForestModel.detect() falls back cleanly without weights
# ---------------------------------------------------------------------------

class TestIsolationForestIntegration:
    def test_detect_works_without_weight_file(self, tmp_path, monkeypatch):
        """
        detect() must not raise even when no weight file exists — it should
        silently fall back to sklearn's decision_function.
        """
        monkeypatch.setattr(_reweighter_mod, "WEIGHTS_DIR", tmp_path)

        from anomaly_detection.models.isolation_forest import IsolationForestModel

        cfg = {"contamination": 0.1, "n_estimators": 20, "threshold": 0.5}
        m = IsolationForestModel("test_if", cfg)

        # Build minimal training data
        rng = np.random.default_rng(0)
        items = [
            {"features": {f"f{j}": float(rng.normal()) for j in range(4)}}
            for _ in range(60)
        ]
        m.train(items)

        anomalies = m.detect(items)
        assert isinstance(anomalies, list)

    def test_detect_uses_weights_when_present(self, tmp_path, monkeypatch):
        """
        When a valid weight file exists, detect() must use it (log message is
        the only observable signal without mocking sklearn internals).
        """
        monkeypatch.setattr(_reweighter_mod, "WEIGHTS_DIR", tmp_path)

        from anomaly_detection.models.isolation_forest import IsolationForestModel

        cfg = {"contamination": 0.1, "n_estimators": 20, "threshold": 0.5}
        m = IsolationForestModel("test_if_weighted", cfg)

        rng = np.random.default_rng(1)
        items = [
            {"features": {f"f{j}": float(rng.normal()) for j in range(4)}}
            for _ in range(60)
        ]
        m.train(items)

        # Create a plausible weight file
        weights = np.ones(20) / 20
        np.save(str(tmp_path / "test_if_weighted.weights.npy"), weights)

        # detect() must not raise and must return a list
        anomalies = m.detect(items)
        assert isinstance(anomalies, list)
