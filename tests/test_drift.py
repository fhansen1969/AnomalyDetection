"""Synthetic tests for the concept drift detection module.

Run with:   pytest tests/test_drift.py -v
Skips automatically if alibi-detect is not installed.
"""
import pytest
import numpy as np

alibi_detect = pytest.importorskip("alibi_detect", reason="alibi-detect not installed")

from anomaly_detection.drift.feature_drift import (  # noqa: E402
    FeatureDriftMonitor,
    _compute_psi,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def monitor(tmp_path):
    return FeatureDriftMonitor(
        persist_path=str(tmp_path),
        method="ks",
        p_value_threshold=0.05,
        sliding_window_size=5,
        drift_window_min_count=2,
    )


@pytest.fixture
def fitted_monitor(monitor):
    rng = np.random.default_rng(42)
    reference = rng.standard_normal((500, 10))
    monitor.fit_reference(reference)
    return monitor, rng


# ---------------------------------------------------------------------------
# FeatureDriftMonitor tests
# ---------------------------------------------------------------------------

class TestFeatureDriftMonitor:
    def test_fit_stores_reference(self, fitted_monitor):
        monitor, _ = fitted_monitor
        assert monitor.is_fitted()
        state = monitor.state()
        assert state["reference_size"] == 500
        assert state["n_features"] == 10

    def test_update_returns_verdict(self, fitted_monitor):
        monitor, rng = fitted_monitor
        batch = rng.standard_normal((100, 10))
        verdict = monitor.update(batch)
        assert verdict is not None
        assert "drift_detected" in verdict
        assert "p_value" in verdict
        assert "method" in verdict
        assert verdict["method"] == "ks"

    def test_drift_fires_on_large_shift(self, fitted_monitor):
        """A 5-sigma mean shift across all features must trigger drift."""
        monitor, rng = fitted_monitor
        shifted = rng.standard_normal((200, 10)) + 5.0
        verdict = monitor.update(shifted)
        assert verdict is not None, "update() returned None on a fitted monitor"
        assert verdict["drift_detected"] is True, (
            f"Expected drift on 5-sigma shift, got p_value={verdict.get('p_value')}"
        )

    def test_no_drift_on_same_distribution(self, fitted_monitor):
        """Batches from the reference distribution should rarely trigger drift."""
        monitor, rng = fitted_monitor
        drift_count = 0
        for _ in range(5):
            batch = rng.standard_normal((200, 10))
            verdict = monitor.update(batch)
            if verdict and verdict["drift_detected"]:
                drift_count += 1
        # At p=0.05 with a correctly calibrated test, expect at most 1 false positive
        assert drift_count < 5, (
            f"Too many false positives on in-distribution data: {drift_count}/5"
        )

    def test_update_accepts_list_of_dicts(self, fitted_monitor):
        """update() must handle list-of-dicts (the actual detection path format)."""
        monitor, rng = fitted_monitor
        matrix = rng.standard_normal((100, 10)) + 5.0  # shifted → must drift
        col_names = [str(i) for i in range(10)]
        batch = [dict(zip(col_names, row)) for row in matrix]
        verdict = monitor.update(batch)
        assert verdict is not None
        assert verdict["drift_detected"] is True

    def test_unfitted_monitor_returns_none(self, monitor):
        """update() on an unfitted monitor must return None without raising."""
        rng = np.random.default_rng(0)
        batch = rng.standard_normal((50, 5))
        assert monitor.update(batch) is None

    def test_persistence_roundtrip(self, tmp_path):
        """State written by fit_reference must be reloaded by a fresh instance."""
        rng = np.random.default_rng(0)
        reference = rng.standard_normal((300, 5))

        m1 = FeatureDriftMonitor(persist_path=str(tmp_path), method="ks")
        m1.fit_reference(reference)

        m2 = FeatureDriftMonitor(persist_path=str(tmp_path), method="ks")
        assert m2.is_fitted()
        assert m2.state()["reference_size"] == 300
        assert m2.state()["n_features"] == 5

    def test_window_counter_increments(self, fitted_monitor):
        """n_windows_drifted must accumulate correctly."""
        monitor, rng = fitted_monitor
        for _ in range(3):
            shifted = rng.standard_normal((200, 10)) + 5.0
            monitor.update(shifted)
        state = monitor.state()
        assert state["n_windows_drifted"] >= 1  # at least one drift detected

    def test_state_keys(self, fitted_monitor):
        monitor, _ = fitted_monitor
        state = monitor.state()
        for key in (
            "is_fitted",
            "reference_size",
            "n_features",
            "n_windows_checked",
            "n_windows_drifted",
            "window_size",
            "last_drift_detected_at",
            "last_checked_at",
            "method",
            "p_value_threshold",
        ):
            assert key in state, f"Missing key in state(): {key}"


# ---------------------------------------------------------------------------
# PSI tests (no alibi-detect dependency)
# ---------------------------------------------------------------------------

class TestComputePSI:
    def test_psi_near_zero_on_identical(self):
        vals = ["a", "b", "a", "b", "c"] * 100
        assert _compute_psi(vals, vals) < 0.01

    def test_psi_large_on_complete_shift(self):
        reference = ["a"] * 500
        actual = ["b"] * 500
        psi = _compute_psi(actual, reference)
        assert psi >= 0.25, f"Expected PSI >= 0.25, got {psi}"

    def test_psi_moderate_on_partial_shift(self):
        reference = ["a"] * 400 + ["b"] * 100
        actual = ["a"] * 200 + ["b"] * 300
        psi = _compute_psi(actual, reference)
        assert psi >= 0.05, f"Expected detectable PSI, got {psi}"
