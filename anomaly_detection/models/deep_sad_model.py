"""Deep SAD Model (semi-supervised anomaly detection).

Vendored implementation of Ruff et al., ICLR 2020:
  "Deep Semi-Supervised Anomaly Detection"

Typical training time: ~20-60 s on CPU for n=10 000, d=20, 50 epochs.

Usage:
  Unsupervised (labels=None): equivalent to Deep SVDD — all samples
  treated as normal; anomaly score = distance from hypersphere center.

  Semi-supervised (labels provided): labeled normals are pushed toward
  the center; labeled anomalies are pushed away.  Unlabeled samples are
  treated as normal during training.

Retrain hook:
  Call ``retrain_on_feedback(labeled_data, unlabeled_data)`` from your
  retrain pipeline to refit the model with fresh TP/FP labels without
  touching any other model.
"""

import io
import logging
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from anomaly_detection.models.base import AnomalyDetectionModel

# torch, MLPEncoder and DeepSADTrainer are imported lazily inside methods
# to avoid grpc/abseil mutex deadlocks when the models package is imported
# in processes that have already loaded sentence-transformers.

logger = logging.getLogger(__name__)


def _autodetect_device():
    import torch
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


class DeepSADModel(AnomalyDetectionModel):
    """Semi-supervised anomaly detector using the Deep SAD objective.

    Configuration keys (all optional):
        hidden_dims     list[int]  Hidden layer widths.          Default: [32, 16]
        rep_dim         int        Representation dimension.      Default: 16
        lr              float      Learning rate.                 Default: 1e-3
        n_epochs        int        Training epochs.               Default: 50
        batch_size      int        Mini-batch size.               Default: 64
        weight_decay    float      L2 regularisation.             Default: 1e-6
        eps             float      Numerical stability for loss.  Default: 1e-6
        threshold       float      Detection threshold (0-1).     Default: 0.7
        device          str        "cpu" or "cuda"; auto-detected if omitted.
        feature_prefix  str        Restrict to features with this prefix.
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        super().__init__(name, config, storage_manager)

        self.hidden_dims: List[int] = list(config.get("hidden_dims", [32, 16]))
        self.rep_dim: int = int(config.get("rep_dim", 16))
        self.lr: float = float(config.get("lr", 1e-3))
        self.n_epochs: int = int(config.get("n_epochs", 50))
        self.batch_size: int = int(config.get("batch_size", 64))
        self.weight_decay: float = float(config.get("weight_decay", 1e-6))
        self.eps: float = float(config.get("eps", 1e-6))
        self.feature_prefix: Optional[str] = config.get("feature_prefix", None)
        self._device_str: Optional[str] = config.get("device")
        # Actual torch.device resolved lazily in fit() / _restore_trainer()

        self._trainer = None  # DeepSADTrainer, instantiated lazily
        self._input_dim: Optional[int] = None
        self.training_feature_names: Optional[List[str]] = None

    # ------------------------------------------------------------------
    # Primary interface (matches existing model contract)
    # ------------------------------------------------------------------

    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train unsupervised (all labels = 0 / normal)."""
        self.fit(data, labels=None)

    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score data and return items whose score ≥ threshold."""
        if not data:
            return []
        if self._trainer is None:
            logger.error("DeepSADModel not trained.")
            return []

        X, _ = self._extract_features_aligned(data, self.training_feature_names or [])
        if X.shape[0] == 0:
            return []

        raw_scores = self._trainer.score_samples(X)
        norm_scores = self._normalize_scores(raw_scores)

        anomalies = []
        for i, score in enumerate(norm_scores):
            if score >= self.threshold:
                anomalies.append(
                    self.create_anomaly(
                        item=data[i],
                        score=float(score),
                        details={"distance_from_center": float(raw_scores[i])},
                    )
                )
        logger.info("DeepSAD: %d/%d anomalies detected.", len(anomalies), len(data))
        return anomalies

    # ------------------------------------------------------------------
    # Semi-supervised interface
    # ------------------------------------------------------------------

    def fit(
        self,
        data: List[Dict[str, Any]],
        labels: Optional[List[int]] = None,
    ) -> None:
        """Fit (or refit) the model.

        Args:
            data:   List of items with 'features' dict.
            labels: Optional per-item labels:
                      1  = known normal
                     -1  = known anomaly
                      0  = unlabeled  (same as passing None)
                    None = treat all as unlabeled.
        """
        X, feature_names = self._extract_features(data)
        if X.shape[0] == 0:
            logger.error("No features found in training data.")
            return

        self.training_feature_names = feature_names
        self._input_dim = X.shape[1]

        y: Optional[np.ndarray] = None
        if labels is not None:
            y = np.asarray(labels, dtype=np.int64)
            if y.shape[0] != X.shape[0]:
                logger.error("labels length %d ≠ data length %d; ignoring labels.", y.shape[0], X.shape[0])
                y = None

        import torch
        from anomaly_detection.models.deep_sad.network import MLPEncoder
        from anomaly_detection.models.deep_sad.trainer import DeepSADTrainer

        device = torch.device(self._device_str) if self._device_str else _autodetect_device()

        encoder = MLPEncoder(self._input_dim, self.hidden_dims, self.rep_dim)
        self._trainer = DeepSADTrainer(
            model=encoder,
            device=device,
            lr=self.lr,
            n_epochs=self.n_epochs,
            batch_size=self.batch_size,
            weight_decay=self.weight_decay,
            eps=self.eps,
        )

        mode = "semi-supervised" if (y is not None and np.any(y != 0)) else "unsupervised"
        logger.info(
            "Training DeepSAD (%s) on %d samples, %d features (device=%s).",
            mode, X.shape[0], X.shape[1], device,
        )
        self._trainer.fit(X, y)
        self.is_trained = True
        self._save_model_state()
        logger.info("DeepSAD training complete.")

    def score(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """Return raw anomaly scores (distance from center) for each item."""
        if self._trainer is None:
            raise RuntimeError("DeepSADModel not trained. Call fit() first.")
        X, _ = self._extract_features_aligned(data, self.training_feature_names or [])
        return self._trainer.score_samples(X)

    # ------------------------------------------------------------------
    # Retrain hook (called from the supervised retrain pipeline)
    # ------------------------------------------------------------------

    def retrain_on_feedback(
        self,
        labeled_feedback: List[Dict[str, Any]],
        feedback_labels: List[int],
        unlabeled_corpus: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Refit using TP/FP feedback plus an optional unlabeled corpus.

        This is called as a sibling hook alongside the supervised retrain
        pipeline.  It does NOT replace the supervised classifier — these
        models coexist.

        Args:
            labeled_feedback: Items with known labels from TP/FP review.
            feedback_labels:  Corresponding labels (1=normal, -1=anomaly).
            unlabeled_corpus: Additional unlabeled items to include (treated
                              as unlabeled, i.e., y=0).
        """
        combined_data: List[Dict[str, Any]] = list(labeled_feedback)
        combined_labels: List[int] = list(feedback_labels)

        if unlabeled_corpus:
            combined_data.extend(unlabeled_corpus)
            combined_labels.extend([0] * len(unlabeled_corpus))

        if not combined_data:
            logger.warning("retrain_on_feedback: no data provided, skipping.")
            return

        logger.info(
            "DeepSAD retrain_on_feedback: %d labeled + %d unlabeled items.",
            len(labeled_feedback),
            len(unlabeled_corpus) if unlabeled_corpus else 0,
        )
        self.fit(combined_data, combined_labels)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["state"]["input_dim"] = self._input_dim
        state["state"]["feature_names"] = self.training_feature_names
        return state

    def set_state(self, state: Dict[str, Any]) -> None:
        super().set_state(state)
        self._restore_trainer()

    def _save_model_state(self) -> None:
        if self._trainer is None:
            return
        import torch
        buf = io.BytesIO()
        torch.save(self._trainer.state_dict(), buf)
        self.model_state = {
            "trainer_bytes": buf.getvalue(),
            "input_dim": self._input_dim,
            "feature_names": self.training_feature_names,
            "hidden_dims": self.hidden_dims,
            "rep_dim": self.rep_dim,
        }

    def _restore_trainer(self) -> None:
        if not self.model_state or "trainer_bytes" not in self.model_state:
            return
        try:
            import torch
            from anomaly_detection.models.deep_sad.network import MLPEncoder
            from anomaly_detection.models.deep_sad.trainer import DeepSADTrainer

            input_dim = self.model_state.get("input_dim")
            if input_dim is None:
                return
            hidden_dims = self.model_state.get("hidden_dims", self.hidden_dims)
            rep_dim = self.model_state.get("rep_dim", self.rep_dim)
            self.training_feature_names = self.model_state.get("feature_names")
            self._input_dim = input_dim

            device = torch.device(self._device_str) if self._device_str else _autodetect_device()
            encoder = MLPEncoder(input_dim, hidden_dims, rep_dim)
            trainer = DeepSADTrainer(
                model=encoder,
                device=device,
                lr=self.lr,
                n_epochs=self.n_epochs,
                batch_size=self.batch_size,
                weight_decay=self.weight_decay,
                eps=self.eps,
            )
            buf = io.BytesIO(self.model_state["trainer_bytes"])
            trainer.load_state_dict(torch.load(buf, map_location=device))
            self._trainer = trainer
        except Exception as exc:
            logger.error("Failed to restore DeepSAD trainer: %s", exc)

    # ------------------------------------------------------------------
    # Feature extraction helpers
    # ------------------------------------------------------------------

    def _extract_features(self, data: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[str]]:
        all_names: set = set()
        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                for k in item["features"]:
                    if self.feature_prefix is None or k.startswith(self.feature_prefix):
                        all_names.add(k)
        names = sorted(all_names)
        if not names:
            return np.empty((0, 0), dtype=np.float32), []
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
            return np.empty((0, 0), dtype=np.float32), []
        mat = np.zeros((len(data), len(target_names)), dtype=np.float32)
        for i, item in enumerate(data):
            feats = item.get("features", {})
            for j, n in enumerate(target_names):
                try:
                    mat[i, j] = float(feats.get(n, 0.0))
                except (TypeError, ValueError):
                    pass
        return mat, target_names

    @staticmethod
    def _normalize_scores(scores: np.ndarray) -> np.ndarray:
        scores = np.nan_to_num(np.asarray(scores, dtype=np.float64), nan=0.0, posinf=1.0, neginf=0.0)
        lo, hi = scores.min(), scores.max()
        if hi - lo < 1e-10:
            return np.ones_like(scores) if hi > 0 else np.zeros_like(scores)
        return np.clip((scores - lo) / (hi - lo), 0.0, 1.0)
