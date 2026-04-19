"""
ECOD Model for Anomaly Detection

Empirical Cumulative Distribution-based Outlier Detection (ECOD) via PyOD.
Parameter-free beyond contamination; no estimators or random state required.
"""

import logging
import pickle
import numpy as np
from typing import Dict, List, Any, Tuple, Optional

try:
    from pyod.models.ecod import ECOD
    PYOD_AVAILABLE = True
except ImportError:
    PYOD_AVAILABLE = False
    logging.warning("pyod not installed. ECODModel will not work.")

from anomaly_detection.models.base import AnomalyDetectionModel


class ECODModel(AnomalyDetectionModel):
    """
    ECOD anomaly detection model.

    Uses Empirical Cumulative Distribution-based Outlier Detection (Li et al., 2022).
    Unsupervised, parameter-free beyond contamination; no n_estimators or random_state.
    PyOD's decision_function returns higher scores for more anomalous points.
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """Initialize ECOD model."""
        super().__init__(name, config, storage_manager)

        if not PYOD_AVAILABLE:
            self.logger.error("pyod not installed")
            return

        self.contamination = float(config.get("contamination", 0.01))
        self.feature_prefix = config.get("feature_prefix", None)

        self.model = ECOD(contamination=self.contamination)
        self.training_feature_names = None

        self.logger.info(f"Initialized ECOD with contamination={self.contamination}")

    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train the ECOD model."""
        if not PYOD_AVAILABLE:
            self.logger.error("pyod not installed")
            return

        feature_matrix, feature_names = self._extract_features(data)

        if feature_matrix.shape[0] == 0:
            self.logger.error("No features in training data")
            return

        self.training_feature_names = feature_names

        self.logger.info(
            f"Training on {feature_matrix.shape[0]} samples "
            f"with {feature_matrix.shape[1]} features"
        )

        self.model.fit(feature_matrix)
        self.is_trained = True

        try:
            self.model_state = {
                "model_pickle": pickle.dumps(self.model),
                "feature_names": feature_names,
            }
            self.logger.info("Training completed")
        except Exception as e:
            self.logger.error(f"Error saving model state: {e}")

    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies using ECOD.

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
