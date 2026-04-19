"""
Score calibration for anomaly detection models.

Converts raw anomaly scores to ECDF percentile ranks, calibrated TP probabilities,
and human-readable severity tiers.

This module is intentionally self-contained.  Fitting is an offline step — see
anomaly_detection/calibration/fit_calibrator.py for the maintenance CLI.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Tier boundary keys: score < cutoffs["medium"] → "low", < "high" → "medium",
# < "critical" → "high", else "critical".
DEFAULT_TIER_CUTOFFS: Dict[str, float] = {
    "medium": 0.30,
    "high": 0.60,
    "critical": 0.85,
}


class ScoreCalibrator:
    """
    Per-model calibrator that maps raw anomaly scores to interpretable values.

    Workflow
    --------
    1. Offline: call fit_ecdf() with all training scores to build the ECDF.
    2. Offline: call fit_isotonic() with labeled (score, TP/FP) pairs to build
       the probability calibrator.  Falls back to Platt scaling when fewer than
       30 labeled samples are available.
    3. Persist with save(); load at runtime with load().
    4. At detection time: call transform(score) to get a stamped dict.
    """

    def __init__(self, tier_cutoffs: Optional[Dict[str, float]] = None) -> None:
        self.tier_cutoffs: Dict[str, float] = (
            tier_cutoffs if tier_cutoffs is not None else DEFAULT_TIER_CUTOFFS.copy()
        )
        self._sorted_scores: Optional[np.ndarray] = None
        self._prob_model: Any = None
        self._prob_method: Optional[str] = None  # "isotonic" or "platt"

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def fit_ecdf(self, scores: np.ndarray) -> None:
        """Fit a rolling ECDF from an array of raw training scores."""
        arr = np.asarray(scores, dtype=float)
        if arr.ndim != 1:
            raise ValueError("scores must be a 1-D array")
        self._sorted_scores = np.sort(arr)

    def fit_isotonic(self, scores: np.ndarray, labels: np.ndarray) -> str:
        """
        Fit a probability calibrator mapping raw score → P(true positive).

        Uses IsotonicRegression when n_labeled >= 30; falls back to Platt scaling
        (LogisticRegression on a single feature) otherwise.

        Parameters
        ----------
        scores : 1-D array of raw anomaly scores
        labels : 1-D binary array (1 = true positive, 0 = false positive)

        Returns
        -------
        "isotonic" or "platt" — which path was taken.
        """
        scores = np.asarray(scores, dtype=float)
        labels = np.asarray(labels, dtype=float)

        if scores.ndim != 1 or labels.ndim != 1:
            raise ValueError("scores and labels must be 1-D arrays")
        if len(scores) != len(labels):
            raise ValueError("scores and labels must have the same length")

        if len(labels) >= 30:
            from sklearn.isotonic import IsotonicRegression

            model = IsotonicRegression(out_of_bounds="clip")
            model.fit(scores, labels)
            self._prob_model = model
            self._prob_method = "isotonic"
        else:
            from sklearn.linear_model import LogisticRegression

            model = LogisticRegression(max_iter=500)
            model.fit(scores.reshape(-1, 1), labels)
            self._prob_model = model
            self._prob_method = "platt"

        return self._prob_method

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    def transform(self, score: float) -> Dict[str, Any]:
        """
        Transform a single raw score into calibrated values.

        Returns
        -------
        dict with keys:
            ecdf_rank      : float | None — percentile in [0, 1] from fitted ECDF
            calibrated_prob: float | None — P(TP) from isotonic/Platt model
            severity_tier  : str          — "low" | "medium" | "high" | "critical"
        """
        score = float(score)
        ecdf_rank = self._compute_ecdf_rank(score)
        calibrated_prob = self._compute_calibrated_prob(score)

        # Prefer calibrated_prob for tier assignment; fall back to ecdf_rank, then raw score.
        tier_base = (
            calibrated_prob
            if calibrated_prob is not None
            else (ecdf_rank if ecdf_rank is not None else score)
        )
        severity_tier = self._assign_tier(tier_base)

        return {
            "ecdf_rank": ecdf_rank,
            "calibrated_prob": calibrated_prob,
            "severity_tier": severity_tier,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Persist calibrator to disk using joblib."""
        import joblib

        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, dest)
        logger.info("Saved calibrator to %s", dest)

    @classmethod
    def load(cls, path: str) -> "ScoreCalibrator":
        """Load a calibrator saved with save()."""
        import joblib

        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(f"Expected ScoreCalibrator, got {type(obj)}")
        return obj

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_ecdf_rank(self, score: float) -> Optional[float]:
        if self._sorted_scores is None or len(self._sorted_scores) == 0:
            return None
        rank = np.searchsorted(self._sorted_scores, score, side="right") / len(
            self._sorted_scores
        )
        return float(rank)

    def _compute_calibrated_prob(self, score: float) -> Optional[float]:
        if self._prob_model is None:
            return None
        if self._prob_method == "isotonic":
            prob = float(self._prob_model.predict([score])[0])
        else:  # platt (LogisticRegression)
            prob = float(self._prob_model.predict_proba([[score]])[0][1])
        return float(np.clip(prob, 0.0, 1.0))

    def _assign_tier(self, value: float) -> str:
        if value < self.tier_cutoffs["medium"]:
            return "low"
        if value < self.tier_cutoffs["high"]:
            return "medium"
        if value < self.tier_cutoffs["critical"]:
            return "high"
        return "critical"
