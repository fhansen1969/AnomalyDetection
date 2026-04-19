"""
Extended Isolation Forest Model for Anomaly Detection

Extended Isolation Forest (EIF) via PyOD's IForest wrapper.

The `extension_level` config param follows the EIF paper convention:
  0            → standard axis-aligned IForest splits
  n_features-1 → full EIF (all dimensions participate in each hyperplane cut)

PyOD 1.x IForest wraps sklearn's IsolationForest, which uses axis-aligned splits
only. The extension_level is resolved at train time, recorded in model_state for
observability, and will be forwarded to the underlying estimator once PyOD exposes
native hyperplane-split EIF support.
"""

import logging
import pickle
import numpy as np
from typing import Dict, List, Any, Tuple, Optional

try:
    from pyod.models.iforest import IForest
    PYOD_AVAILABLE = True
except ImportError:
    PYOD_AVAILABLE = False
    logging.warning("pyod not installed. ExtendedIsolationForestModel will not work.")

from anomaly_detection.models.base import AnomalyDetectionModel


class ExtendedIsolationForestModel(AnomalyDetectionModel):
    """
    Extended Isolation Forest anomaly detection model via PyOD.

    Mirrors IsolationForestModel's interface exactly.  The extension_level
    parameter (default: n_features - 1 for full EIF) is stored in model_state;
    PyOD's decision_function returns higher scores for more anomalous points.
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """Initialize Extended Isolation Forest model."""
        super().__init__(name, config, storage_manager)

        if not PYOD_AVAILABLE:
            self.logger.error("pyod not installed")
            return

        self.n_estimators = int(config.get("n_estimators", 100))
        self.max_samples = config.get("max_samples", "auto")
        self.contamination = float(config.get("contamination", 0.01))
        self.random_state_param = int(config.get("random_state", 42))
        # None means "resolve to n_features - 1 at train time"
        self.extension_level: Optional[int] = config.get("extension_level", None)
        self.feature_prefix = config.get("feature_prefix", None)

        self.model = IForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            contamination=self.contamination,
            random_state=self.random_state_param,
            n_jobs=-1,
        )
        self.training_feature_names = None

        self.logger.info(
            f"Initialized ExtendedIsolationForest with {self.n_estimators} estimators"
        )

    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train the Extended Isolation Forest model."""
        if not PYOD_AVAILABLE:
            self.logger.error("pyod not installed")
            return

        feature_matrix, feature_names = self._extract_features(data)

        if feature_matrix.shape[0] == 0:
            self.logger.error("No features in training data")
            return

        self.training_feature_names = feature_names
        n_features = feature_matrix.shape[1]

        # Resolve extension_level: default to full EIF (n_features - 1)
        resolved_level = (
            int(self.extension_level)
            if self.extension_level is not None
            else max(0, n_features - 1)
        )

        self.logger.info(
            f"Training on {feature_matrix.shape[0]} samples "
            f"with {n_features} features (extension_level={resolved_level})"
        )

        self.model.fit(feature_matrix)
        self.is_trained = True

        try:
            self.model_state = {
                "model_pickle": pickle.dumps(self.model),
                "feature_names": feature_names,
                "extension_level": resolved_level,
            }
            self.logger.info("Training completed")
        except Exception as e:
            self.logger.error(f"Error saving model state: {e}")

    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies using Extended Isolation Forest.

        Args:
            data: List of data items with 'features' key

        Returns:
            List of anomaly dictionaries
        """
        if not PYOD_AVAILABLE:
            self.logger.error("pyod not installed")
            return []

        if not data:
            return []

        if self.model is None and "model_pickle" in self.model_state:
            try:
                self.model = pickle.loads(self.model_state["model_pickle"])
                if "feature_names" in self.model_state:
                    self.training_feature_names = self.model_state["feature_names"]
            except Exception as e:
                self.logger.error(f"Error loading model: {e}")
                return []

        if self.model is None:
            self.logger.error("Model not trained")
            return []

        feature_matrix, _ = self._extract_features_aligned(data, self.training_feature_names)

        if feature_matrix.shape[0] == 0:
            return []

        # PyOD decision_function: higher score = more anomalous (no inversion needed)
        raw_scores = self.model.decision_function(feature_matrix)
        normalized_scores = self._normalize_scores(raw_scores)

        anomalies = []
        for i, score in enumerate(normalized_scores):
            if score >= self.threshold:
                try:
                    anomaly = self.create_anomaly(
                        item=data[i],
                        score=float(score),
                        details={
                            "raw_score": float(raw_scores[i]),
                            "normalized_score": float(score),
                            "extension_level": self.model_state.get("extension_level"),
                        },
                    )
                    anomalies.append(anomaly)
                except Exception as e:
                    self.logger.error(f"Error creating anomaly for item {i}: {e}")

        self.logger.info(f"Detected {len(anomalies)} anomalies from {len(data)} samples")
        return anomalies

    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Normalize scores to [0, 1] via min-max, matching IsolationForestModel."""
        if len(scores) == 0:
            return scores

        scores = np.array(scores, dtype=np.float64)
        scores = np.nan_to_num(scores, nan=0.0, posinf=1.0, neginf=0.0)

        min_score = np.min(scores)
        max_score = np.max(scores)

        if max_score - min_score < 1e-10:
            return np.ones_like(scores) if max_score > 0 else np.zeros_like(scores)

        normalized = (scores - min_score) / (max_score - min_score)
        return np.clip(normalized, 0.0, 1.0)

    def _extract_features(
        self, data: List[Dict[str, Any]]
    ) -> Tuple[np.ndarray, List[str]]:
        """Extract feature vectors from data."""
        if not data:
            return np.array([]), []

        all_features: set = set()
        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                for feature_name in item["features"]:
                    if self.feature_prefix is None or feature_name.startswith(self.feature_prefix):
                        all_features.add(feature_name)

        feature_names = sorted(all_features)
        if not feature_names:
            self.logger.warning("No features found in data")
            return np.array([]), []

        n_samples = len(data)
        n_features = len(feature_names)
        feature_matrix = np.zeros((n_samples, n_features))

        for i, item in enumerate(data):
            if "features" in item and isinstance(item["features"], dict):
                for j, feature_name in enumerate(feature_names):
                    value = item["features"].get(feature_name, 0.0)
                    feature_matrix[i, j] = self._safe_float(value)

        return feature_matrix, feature_names

    def _extract_features_aligned(
        self, data: List[Dict[str, Any]], target_feature_names: List[str]
    ) -> Tuple[np.ndarray, List[str]]:
        """Extract features aligned with target feature names."""
        if not data or not target_feature_names:
            return np.array([]), []

        all_available: set = set()
        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                all_available.update(item["features"].keys())

        missing = set(target_feature_names) - all_available
        extra = all_available - set(target_feature_names)
        if missing or extra:
            self.logger.warning(f"Feature mismatch: missing {len(missing)}, extra {len(extra)}")

        n_samples = len(data)
        n_features = len(target_feature_names)
        feature_matrix = np.zeros((n_samples, n_features))

        for i, item in enumerate(data):
            if "features" in item and isinstance(item["features"], dict):
                for j, feature_name in enumerate(target_feature_names):
                    value = item["features"].get(feature_name, 0.0)
                    feature_matrix[i, j] = self._safe_float(value)

        return feature_matrix, target_feature_names

    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def set_state(self, state: Dict[str, Any]) -> None:
        """Restore model state."""
        super().set_state(state)

        if "model_pickle" in self.model_state and PYOD_AVAILABLE:
            try:
                self.model = pickle.loads(self.model_state["model_pickle"])
                if "feature_names" in self.model_state:
                    self.training_feature_names = self.model_state["feature_names"]
                self.logger.info("Loaded model from saved state")
            except Exception as e:
                self.logger.error(f"Error loading model: {e}")
