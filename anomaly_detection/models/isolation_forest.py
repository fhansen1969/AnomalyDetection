"""
Isolation Forest Model for Anomaly Detection

This model uses the Isolation Forest algorithm for unsupervised anomaly detection.
When AAD weights are present on disk (written by AADReweighter after analyst
feedback), scoring uses the weighted tree-path formulation instead of sklearn's
default uniform-weight decision_function.
"""

import logging
import pickle
import numpy as np
from typing import Dict, List, Any, Tuple

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not installed. IsolationForestModel will not work.")

from anomaly_detection.models.base import AnomalyDetectionModel


class IsolationForestModel(AnomalyDetectionModel):
    """
    IMPROVED Isolation Forest anomaly detection model.
    
    Uses Isolation Forest algorithm with proper score normalization
    and evaluation support.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize Isolation Forest model."""
        super().__init__(name, config)
        
        if not SKLEARN_AVAILABLE:
            self.logger.error("scikit-learn not installed")
            return
        
        # Model hyperparameters
        self.n_estimators = int(config.get("n_estimators", 100))
        self.max_samples = config.get("max_samples", "auto")
        self.contamination = float(config.get("contamination", 0.01))
        self.random_state_param = int(config.get("random_state", 42))
        
        # Feature selection
        self.feature_prefix = config.get("feature_prefix", None)
        
        # Create model
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            contamination=self.contamination,
            random_state=self.random_state_param,
            n_jobs=-1
        )
        
        self.training_feature_names = None
        
        self.logger.info(f"Initialized Isolation Forest with {self.n_estimators} estimators")
    
    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train the Isolation Forest model."""
        if not SKLEARN_AVAILABLE:
            self.logger.error("scikit-learn not installed")
            return
        
        # Extract features
        feature_matrix, feature_names = self._extract_features(data)
        
        if feature_matrix.shape[0] == 0:
            self.logger.error("No features in training data")
            return
        
        self.training_feature_names = feature_names
        
        self.logger.info(f"Training on {feature_matrix.shape[0]} samples "
                        f"with {feature_matrix.shape[1]} features")
        
        # Fit the model
        self.model.fit(feature_matrix)
        
        # Save model state
        try:
            self.model_state = {
                "model_pickle": pickle.dumps(self.model),
                "feature_names": feature_names
            }
            self.logger.info("Training completed")
        except Exception as e:
            self.logger.error(f"Error saving model state: {e}")
    
    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies using Isolation Forest.
        
        Args:
            data: List of data items with 'features' key
            
        Returns:
            List of anomaly dictionaries
        """
        if not SKLEARN_AVAILABLE:
            self.logger.error("scikit-learn not installed")
            return []
        
        if not data:
            return []
        
        # Load model if needed
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
        
        # Extract features with alignment
        feature_matrix, _ = self._extract_features_aligned(data, self.training_feature_names)
        
        if feature_matrix.shape[0] == 0:
            return []
        
        # Prefer AAD-weighted scores if a sidecar weight file is present.
        # Fall back to sklearn's decision_function on any error — weight-file
        # corruption must never break live scoring.
        inverted_scores = None
        try:
            from anomaly_detection.active_learning.aad_reweighter import AADReweighter
            from anomaly_detection.active_learning.aad import compute_tree_scores
            weights = AADReweighter.load_weights(self.name)
            if weights is not None and len(weights) == self.model.n_estimators:
                phi = compute_tree_scores(self.model, feature_matrix)
                inverted_scores = phi @ weights
                self.logger.debug("Using AAD-weighted scores")
        except Exception as _aad_exc:
            self.logger.warning(f"AAD scoring unavailable, falling back: {_aad_exc}")

        if inverted_scores is None:
            # Standard sklearn path: decision_function < 0 means anomalous
            decision_scores = self.model.decision_function(feature_matrix)
            inverted_scores = -decision_scores
        
        # Normalize scores to 0-1 range
        normalized_scores = self._normalize_scores(inverted_scores)
        
        # Create anomalies for scores above threshold
        anomalies = []
        for i, score in enumerate(normalized_scores):
            if score >= self.threshold:
                try:
                    anomaly = self.create_anomaly(
                        item=data[i],
                        score=float(score),
                        details={
                            "raw_score": float(inverted_scores[i]),
                            "normalized_score": float(score)
                        }
                    )
                    anomalies.append(anomaly)
                except Exception as e:
                    self.logger.error(f"Error creating anomaly for item {i}: {e}")
        
        self.logger.info(f"Detected {len(anomalies)} anomalies from {len(data)} samples")
        return anomalies
    
    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """
        Normalize scores to 0-1 range using min-max normalization.
        
        Args:
            scores: Raw anomaly scores
            
        Returns:
            Normalized scores in 0-1 range
        """
        if len(scores) == 0:
            return scores
        
        scores = np.array(scores, dtype=np.float64)
        
        # Handle NaN and inf values
        scores = np.nan_to_num(scores, nan=0.0, posinf=1.0, neginf=0.0)
        
        min_score = np.min(scores)
        max_score = np.max(scores)
        
        # Avoid division by zero
        if max_score - min_score < 1e-10:
            # All scores are the same
            if max_score > 0:
                return np.ones_like(scores)
            else:
                return np.zeros_like(scores)
        
        # Min-max normalization
        normalized = (scores - min_score) / (max_score - min_score)
        
        # Ensure values are in [0, 1]
        normalized = np.clip(normalized, 0.0, 1.0)
        
        return normalized
    
    def _extract_features(self, data: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[str]]:
        """Extract feature vectors from data."""
        if not data:
            return np.array([]), []
        
        # Collect all feature names
        all_features = set()
        
        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                for feature_name in item["features"]:
                    if self.feature_prefix is None or feature_name.startswith(self.feature_prefix):
                        all_features.add(feature_name)
        
        feature_names = sorted(all_features)
        
        if not feature_names:
            self.logger.warning("No features found in data")
            return np.array([]), []
        
        # Create feature matrix
        n_samples = len(data)
        n_features = len(feature_names)
        feature_matrix = np.zeros((n_samples, n_features))
        
        # Fill feature matrix
        for i, item in enumerate(data):
            if "features" in item and isinstance(item["features"], dict):
                for j, feature_name in enumerate(feature_names):
                    value = item["features"].get(feature_name, 0.0)
                    feature_matrix[i, j] = self._safe_float(value)
        
        return feature_matrix, feature_names
    
    def _extract_features_aligned(self, data: List[Dict[str, Any]], 
                                  target_feature_names: List[str]) -> Tuple[np.ndarray, List[str]]:
        """Extract features aligned with target feature names."""
        if not data or not target_feature_names:
            return np.array([]), []
        
        # Check for feature mismatches
        all_available_features = set()
        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                all_available_features.update(item["features"].keys())
        
        missing = set(target_feature_names) - all_available_features
        extra = all_available_features - set(target_feature_names)
        
        if missing or extra:
            self.logger.warning(f"Feature mismatch: missing {len(missing)}, extra {len(extra)}")
        
        # Create feature matrix with target dimensions
        n_samples = len(data)
        n_features = len(target_feature_names)
        feature_matrix = np.zeros((n_samples, n_features))
        
        # Fill feature matrix (missing features default to 0.0)
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
        """Set model state."""
        super().set_state(state)
        
        if "model_pickle" in self.model_state and SKLEARN_AVAILABLE:
            try:
                self.model = pickle.loads(self.model_state["model_pickle"])
                if "feature_names" in self.model_state:
                    self.training_feature_names = self.model_state["feature_names"]
                self.logger.info("Loaded model from saved state")
            except Exception as e:
                self.logger.error(f"Error loading model: {e}")