"""Deep Isolation Forest Model.

Wraps ``deepod.models.DeepIsolationForest`` (DeepOD ≥ 0.4).

Typical training time: ~30-90 s on CPU for n=10 000, d=20, n_ensemble=6.
GPU reduces this to ~5-15 s.

Import of deepod is deferred to __init__ to avoid a hard import-time failure
when the package is not installed.
"""

import logging
import pickle
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from anomaly_detection.models.base import AnomalyDetectionModel

logger = logging.getLogger(__name__)


def _autodetect_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class DeepIsolationForestModel(AnomalyDetectionModel):
    """Anomaly detector backed by Deep Isolation Forest (DeepOD).

    Configuration keys (all optional):
        n_ensemble      int   Number of ensemble members.       Default: 6
        hidden_dims     str   Comma-separated MLP widths.       Default: "64"
        rep_dim         int   Representation dimension.         Default: 64
        epochs          int   Training epochs per member.       Default: 100
        batch_size      int   Mini-batch size.                  Default: 64
        lr              float Learning rate.                    Default: 1e-3
        threshold       float Detection threshold (0-1).        Default: 0.7
        device          str   "cpu" or "cuda"; auto-detected if omitted.
        feature_prefix  str   Restrict to features with this prefix. Default: None
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        super().__init__(name, config, storage_manager)

        # deepod is imported lazily in train/detect to avoid grpc/abseil
        # mutex deadlocks when sentence-transformers is loaded in the same process.
        self._deepod_available: Optional[bool] = None  # None = not yet checked

        self.n_ensemble = int(config.get("n_ensemble", 6))
        # deepod hidden_dims is a comma-separated string e.g. "64" or "128,64"
        _hd = config.get("hidden_dims", 64)
        self.hidden_dims: str = str(_hd) if not isinstance(_hd, str) else _hd
        self.rep_dim = int(config.get("rep_dim", 64))
        self.epochs = int(config.get("epochs", 100))
        self.batch_size = int(config.get("batch_size", 64))
        self.lr = float(config.get("lr", 1e-3))
        self.feature_prefix: Optional[str] = config.get("feature_prefix", None)
        self.device: str = config.get("device") or _autodetect_device()

        self._dif = None  # deepod model instance
        self.training_feature_names: Optional[List[str]] = None

    # ------------------------------------------------------------------
    # Primary interface
    # ------------------------------------------------------------------

    def _check_deepod(self) -> bool:
        """Lazily check (and cache) deepod availability."""
        if self._deepod_available is None:
            try:
                from deepod.models import DeepIsolationForest  # noqa: F401
                self._deepod_available = True
            except (ImportError, Exception):
                self._deepod_available = False
                logger.warning(
                    "deepod unavailable. Install with: pip install deepod>=0.4  "
                    "DeepIsolationForestModel will not work."
                )
        return bool(self._deepod_available)

    def train(self, data: List[Dict[str, Any]]) -> None:
        """Fit Deep Isolation Forest on feature data."""
        if not self._check_deepod():
            logger.error("deepod not installed; cannot train.")
            return

        X, feature_names = self._extract_features(data)
        if X.shape[0] == 0:
            logger.error("No features found in training data.")
            return

        self.training_feature_names = feature_names
        self._dif = self._make_dif()
        logger.info(
            "Training DeepIsolationForest on %d samples, %d features (device=%s).",
            X.shape[0], X.shape[1], self.device,
        )
        self._dif.fit(X)
        self.is_trained = True
        self.model_state = {
            "model_pickle": pickle.dumps(self._dif),
            "feature_names": feature_names,
        }
        logger.info("DeepIsolationForest training complete.")

    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score data and return anomalies above threshold."""
        if not self._check_deepod():
            logger.error("deepod not installed; cannot detect.")
            return []
        if not data:
            return []

        self._ensure_loaded()
        if self._dif is None:
            logger.error("Model not trained.")
            return []

        X, _ = self._extract_features_aligned(data, self.training_feature_names or [])
        if X.shape[0] == 0:
            return []

        raw_scores = self._dif.decision_function(X)
        # deepod decision_function: higher → more anomalous (unlike sklearn)
        norm_scores = self._normalize_scores(raw_scores)

        anomalies = []
        for i, score in enumerate(norm_scores):
            if score >= self.threshold:
                anomalies.append(
                    self.create_anomaly(
                        item=data[i],
                        score=float(score),
                        details={"raw_score": float(raw_scores[i])},
                    )
                )
        logger.info("DeepIsolationForest: %d/%d anomalies detected.", len(anomalies), len(data))
        return anomalies

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def set_state(self, state: Dict[str, Any]) -> None:
        super().set_state(state)
        if not self._check_deepod():
            return
        if "model_pickle" in self.model_state:
            try:
                self._dif = pickle.loads(self.model_state["model_pickle"])
                self.training_feature_names = self.model_state.get("feature_names")
            except Exception as exc:
                logger.error("Failed to restore DeepIsolationForest from pickle: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_dif(self):
        from deepod.models import DeepIsolationForest
        return DeepIsolationForest(
            n_ensemble=self.n_ensemble,
            hidden_dims=self.hidden_dims,
            rep_dim=self.rep_dim,
            epochs=self.epochs,
            batch_size=self.batch_size,
            lr=self.lr,
            device=self.device,
            verbose=0,
        )

    def _ensure_loaded(self) -> None:
        if self._dif is None and "model_pickle" in self.model_state:
            try:
                self._dif = pickle.loads(self.model_state["model_pickle"])
                self.training_feature_names = self.model_state.get("feature_names")
            except Exception as exc:
                logger.error("Could not deserialize DeepIsolationForest: %s", exc)

    @staticmethod
    def _normalize_scores(scores: np.ndarray) -> np.ndarray:
        scores = np.nan_to_num(np.asarray(scores, dtype=np.float64), nan=0.0, posinf=1.0, neginf=0.0)
        lo, hi = scores.min(), scores.max()
        if hi - lo < 1e-10:
            return np.ones_like(scores) if hi > 0 else np.zeros_like(scores)
        return np.clip((scores - lo) / (hi - lo), 0.0, 1.0)

    def _extract_features(self, data: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[str]]:
        all_names: set = set()
        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                for k in item["features"]:
                    if self.feature_prefix is None or k.startswith(self.feature_prefix):
                        all_names.add(k)
        names = sorted(all_names)
        if not names:
            return np.empty((0, 0)), []
        mat = np.zeros((len(data), len(names)), dtype=np.float32)
        for i, item in enumerate(data):
            feats = item.get("features", {})
            for j, n in enumerate(names):
                try:
                    mat[i, j] = float(feats.get(n, 0.0))
                except (TypeError, ValueError):
                    pass
        return mat, names

    def _extract_features_aligned(
        self, data: List[Dict[str, Any]], target_names: List[str]
    ) -> Tuple[np.ndarray, List[str]]:
        if not target_names:
            return np.empty((0, 0)), []
        mat = np.zeros((len(data), len(target_names)), dtype=np.float32)
        for i, item in enumerate(data):
            feats = item.get("features", {})
            for j, n in enumerate(target_names):
                try:
                    mat[i, j] = float(feats.get(n, 0.0))
                except (TypeError, ValueError):
                    pass
        return mat, target_names
