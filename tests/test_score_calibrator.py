"""Tests for ScoreCalibrator — tier bounds, ECDF, Platt/isotonic paths, save/load."""
import numpy as np
import pytest

from anomaly_detection.calibration.score_calibrator import (
    DEFAULT_TIER_CUTOFFS,
    ScoreCalibrator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fitted_cal(n: int = 100, seed: int = 0) -> ScoreCalibrator:
    """Return a fully fitted calibrator built from synthetic data."""
    rng = np.random.default_rng(seed)
    scores = rng.uniform(0, 1, n)
    labels = (scores > 0.5).astype(float)
    cal = ScoreCalibrator()
    cal.fit_ecdf(scores)
    cal.fit_isotonic(scores, labels)
    return cal


# ---------------------------------------------------------------------------
# ECDF
# ---------------------------------------------------------------------------

class TestECDF:
    def test_ecdf_rank_in_unit_interval(self):
        cal = ScoreCalibrator()
        cal.fit_ecdf(np.linspace(0, 1, 100))
        for s in [0.0, 0.25, 0.5, 0.75, 1.0]:
            r = cal.transform(s)["ecdf_rank"]
            assert r is not None
            assert 0.0 <= r <= 1.0

    def test_ecdf_rank_monotone(self):
        cal = ScoreCalibrator()
        cal.fit_ecdf(np.linspace(0, 1, 200))
        ranks = [cal.transform(s)["ecdf_rank"] for s in [0.1, 0.5, 0.9]]
        assert ranks[0] < ranks[1] < ranks[2]

    def test_ecdf_none_before_fit(self):
        cal = ScoreCalibrator()
        assert cal.transform(0.5)["ecdf_rank"] is None


# ---------------------------------------------------------------------------
# Isotonic / Platt selection
# ---------------------------------------------------------------------------

class TestProbabilityModel:
    def test_isotonic_chosen_with_30_or_more_labels(self):
        rng = np.random.default_rng(42)
        scores = rng.uniform(0, 1, 50)
        labels = (scores > 0.5).astype(float)
        cal = ScoreCalibrator()
        path = cal.fit_isotonic(scores, labels)
        assert path == "isotonic"

    def test_platt_chosen_below_30_labels(self):
        scores = np.array([0.1, 0.3, 0.5, 0.7, 0.9] * 5)  # 25 samples
        labels = (scores > 0.5).astype(float)
        cal = ScoreCalibrator()
        path = cal.fit_isotonic(scores, labels)
        assert path == "platt"

    def test_calibrated_prob_in_unit_interval(self):
        cal = _fitted_cal()
        for s in [0.0, 0.5, 1.0]:
            p = cal.transform(s)["calibrated_prob"]
            assert p is not None
            assert 0.0 <= p <= 1.0

    def test_calibrated_prob_none_before_fit(self):
        cal = ScoreCalibrator()
        cal.fit_ecdf(np.linspace(0, 1, 50))
        assert cal.transform(0.5)["calibrated_prob"] is None


# ---------------------------------------------------------------------------
# Tier assignment
# ---------------------------------------------------------------------------

class TestTierAssignment:
    def _tier_from_prob(self, prob: float, cutoffs=None) -> str:
        cutoffs = cutoffs or DEFAULT_TIER_CUTOFFS
        cal = ScoreCalibrator(tier_cutoffs=cutoffs)
        # Patch _compute_calibrated_prob to return a fixed value.
        cal._prob_model = object()
        cal._prob_method = "isotonic"
        cal._compute_calibrated_prob = lambda s: prob  # type: ignore[method-assign]
        return cal.transform(0.5)["severity_tier"]

    def test_low_tier(self):
        assert self._tier_from_prob(0.0) == "low"
        assert self._tier_from_prob(0.29) == "low"

    def test_medium_tier(self):
        assert self._tier_from_prob(0.30) == "medium"
        assert self._tier_from_prob(0.59) == "medium"

    def test_high_tier(self):
        assert self._tier_from_prob(0.60) == "high"
        assert self._tier_from_prob(0.84) == "high"

    def test_critical_tier(self):
        assert self._tier_from_prob(0.85) == "critical"
        assert self._tier_from_prob(1.0) == "critical"

    def test_custom_cutoffs(self):
        cutoffs = {"medium": 0.2, "high": 0.5, "critical": 0.9}
        assert self._tier_from_prob(0.19, cutoffs) == "low"
        assert self._tier_from_prob(0.45, cutoffs) == "medium"
        assert self._tier_from_prob(0.70, cutoffs) == "high"
        assert self._tier_from_prob(0.95, cutoffs) == "critical"

    def test_tier_falls_back_to_ecdf_when_no_prob_model(self):
        cal = ScoreCalibrator()
        cal.fit_ecdf(np.linspace(0, 1, 100))
        # Without fit_isotonic, calibrated_prob is None → ecdf_rank drives tier.
        result = cal.transform(0.95)  # near the top → high ecdf_rank → critical
        assert result["calibrated_prob"] is None
        assert result["severity_tier"] == "critical"

    def test_tier_falls_back_to_raw_score_when_both_none(self):
        cal = ScoreCalibrator()  # nothing fitted
        result = cal.transform(0.05)
        assert result["ecdf_rank"] is None
        assert result["calibrated_prob"] is None
        assert result["severity_tier"] == "low"


# ---------------------------------------------------------------------------
# Transform dict structure
# ---------------------------------------------------------------------------

class TestTransformOutput:
    def test_keys_present(self):
        cal = _fitted_cal()
        result = cal.transform(0.7)
        assert set(result.keys()) == {"ecdf_rank", "calibrated_prob", "severity_tier"}

    def test_severity_tier_is_valid_string(self):
        cal = _fitted_cal()
        valid = {"low", "medium", "high", "critical"}
        for s in np.linspace(0, 1, 20):
            assert cal.transform(float(s))["severity_tier"] in valid


# ---------------------------------------------------------------------------
# Save / load round-trip
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_round_trip_isotonic(self, tmp_path):
        cal = _fitted_cal(n=100)
        path = str(tmp_path / "cal.joblib")
        cal.save(path)
        loaded = ScoreCalibrator.load(path)

        for s in [0.1, 0.5, 0.9]:
            orig = cal.transform(s)
            back = loaded.transform(s)
            assert orig["ecdf_rank"] == pytest.approx(back["ecdf_rank"])
            assert orig["calibrated_prob"] == pytest.approx(back["calibrated_prob"])
            assert orig["severity_tier"] == back["severity_tier"]

    def test_round_trip_platt(self, tmp_path):
        scores = np.array([0.1, 0.3, 0.5, 0.7, 0.9] * 4)  # 20 samples < 30
        labels = (scores > 0.5).astype(float)
        cal = ScoreCalibrator()
        cal.fit_ecdf(scores)
        cal.fit_isotonic(scores, labels)
        assert cal._prob_method == "platt"

        path = str(tmp_path / "platt_cal.joblib")
        cal.save(path)
        loaded = ScoreCalibrator.load(path)
        assert loaded._prob_method == "platt"

        orig = cal.transform(0.8)
        back = loaded.transform(0.8)
        assert orig["calibrated_prob"] == pytest.approx(back["calibrated_prob"])

    def test_load_wrong_type_raises(self, tmp_path):
        import joblib

        path = str(tmp_path / "bad.joblib")
        joblib.dump({"not": "a calibrator"}, path)
        with pytest.raises(TypeError):
            ScoreCalibrator.load(path)
