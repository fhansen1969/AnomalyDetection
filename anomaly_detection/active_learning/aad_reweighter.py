"""
AADReweighter — stateful wrapper around the AAD core for IsolationForest models.

Handles:
  - Fitting per-tree weights from analyst TP/FP labels
  - Computing weighted anomaly scores
  - Persisting weights alongside the model as a sidecar .weights.npy file

Usage (training side):
    reweighter = AADReweighter()
    weights = reweighter.fit_weights(iforest, X, labels)
    AADReweighter.save_weights(weights, model_name)

Usage (scoring side):
    weights = AADReweighter.load_weights(model_name)   # None if not yet fitted
    if weights is not None:
        scores = reweighter.score(iforest, X, weights)
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional

from anomaly_detection.active_learning.aad import compute_tree_scores, fit_aad_weights

logger = logging.getLogger("aad_reweighter")

# Sidecar weight files live next to other model artefacts
WEIGHTS_DIR = Path("storage/models")


class AADReweighter:
    """
    Learns and applies per-tree IsolationForest weights from analyst feedback.

    Args:
        n_iter: Gradient descent iterations (default 200).
        lr:     Learning rate (default 0.01).
        C:      Hinge-loss coefficient — higher = more aggressive label fitting
                at the cost of potentially ignoring regularisation (default 1.0).
    """

    def __init__(self, n_iter: int = 200, lr: float = 0.01, C: float = 1.0):
        self.n_iter = n_iter
        self.lr = lr
        self.C = C

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def fit_weights(
        self,
        iforest,
        feature_matrix: np.ndarray,
        labels: np.ndarray,
        unlabeled_scores: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Fit per-tree weights from labeled feedback samples.

        Args:
            iforest:          Fitted sklearn IsolationForest (or wrapper's .model).
            feature_matrix:   (n_samples, n_features) — the rows that labels refer to.
            labels:           (n_samples,) — 1=TP (anomaly), 0=FP (normal),
                              np.nan for unlabeled rows.
            unlabeled_scores: Unused; reserved for future ordering constraints.

        Returns:
            weights: (n_trees,) non-negative array summing to 1.
        """
        labels = np.asarray(labels, dtype=np.float64)
        labeled_mask = ~np.isnan(labels)
        n_labeled = int(labeled_mask.sum())

        if n_labeled == 0:
            logger.warning("AAD: no labeled samples — returning uniform weights")
            return np.ones(len(iforest.estimators_), dtype=np.float64) / len(iforest.estimators_)

        n_tp = int((labels[labeled_mask] == 1).sum())
        n_fp = int((labels[labeled_mask] == 0).sum())
        logger.info(f"AAD: fitting weights — {n_labeled} labels ({n_tp} TP, {n_fp} FP)")

        phi = compute_tree_scores(iforest, feature_matrix)

        return fit_aad_weights(
            phi=phi,
            labels=labels,
            labeled_mask=labeled_mask,
            n_iter=self.n_iter,
            lr=self.lr,
            C=self.C,
        )

    def score(
        self,
        iforest,
        feature_matrix: np.ndarray,
        weights: np.ndarray,
    ) -> np.ndarray:
        """
        Compute weighted anomaly scores (higher = more anomalous).

        Args:
            iforest:        Fitted sklearn IsolationForest.
            feature_matrix: (n_samples, n_features).
            weights:        (n_trees,) from fit_weights.

        Returns:
            scores: (n_samples,) float array.
        """
        phi = compute_tree_scores(iforest, feature_matrix)
        return phi @ weights

    # ------------------------------------------------------------------
    # Persistence helpers (static — no instance state needed)
    # ------------------------------------------------------------------

    @staticmethod
    def weights_path(model_name: str) -> Path:
        """Return the sidecar weight file path for a given model name."""
        return WEIGHTS_DIR / f"{model_name}.weights.npy"

    @staticmethod
    def save_weights(weights: np.ndarray, model_name: str) -> None:
        """Persist weights to disk alongside the model artefacts."""
        WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        path = AADReweighter.weights_path(model_name)
        np.save(str(path), weights)
        logger.info(f"AAD weights saved → {path}  shape={weights.shape}")

    @staticmethod
    def load_weights(model_name: str) -> Optional[np.ndarray]:
        """
        Load weights from the sidecar file.  Returns None if the file does not
        exist — callers should fall back to standard sklearn scoring in that case.
        """
        path = AADReweighter.weights_path(model_name)
        if not path.exists():
            return None
        try:
            weights = np.load(str(path))
            logger.debug(f"AAD weights loaded ← {path}  shape={weights.shape}")
            return weights
        except Exception as exc:
            logger.error(f"AAD: failed to load weights from {path}: {exc}")
            return None
