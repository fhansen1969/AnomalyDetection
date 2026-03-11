"""
Statistical Model for Anomaly Detection

This model uses statistical methods (Z-scores) for anomaly detection.
"""

import logging
import numpy as np
from typing import Dict, List, Any, Tuple

from anomaly_detection.models.base import AnomalyDetectionModel


class StatisticalModel(AnomalyDetectionModel):
    """
    IMPROVED Statistical anomaly detection model.
    
    Uses statistical methods (Z-scores, moving averages) with proper
    score normalization and evaluation support.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize Statistical model."""
        super().__init__(name, config)
        
        # Model parameters
        self.window_size = int(config.get("window_size", 10))
        self.threshold_multiplier = float(config.get("threshold_multiplier", 3.0))
        
        # Feature selection
        self.feature_prefix = config.get("feature_prefix", None)
        
        # Statistics by feature
        self.feature_stats = {}
        self.training_feature_names = None
        
        self.logger.info(f"Initialized Statistical model with window size {self.window_size}")
    
    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train the Statistical model."""
        # Extract features
        feature_matrix, feature_names = self._extract_features(data)
        
        if feature_matrix.shape[0] == 0:
            self.logger.error("No features in training data")
            return
        
        self.training_feature_names = feature_names
        
        self.logger.info(f"Training on {feature_matrix.shape[0]} samples "
                        f"with {feature_matrix.shape[1]} features")
        
        # Calculate statistics for each feature
        self.feature_stats = {}
        
        for j, feature_name in enumerate(feature_names):
            values = feature_matrix[:, j]
            
            # Calculate statistics
            mean = float(np.mean(values))
            std = float(np.std(values))
            min_val = float(np.min(values))
            max_val = float(np.max(values))
            
            # Prevent division by zero
            if std < 1e-10:
                std = 1.0
            
            self.feature_stats[feature_name] = {
                "mean": mean,
                "std": std,
                "min": min_val,
                "max": max_val
            }
        
        # Save model state
        self.model_state = {
            "feature_stats": self.feature_stats,
            "feature_names": feature_names,
            "window_size": self.window_size,
            "threshold_multiplier": self.threshold_multiplier
        }
        
        # Mark model as trained
        self.is_trained = True
        
        self.logger.info("Training completed")
    
    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies using statistical Z-scores.
        
        Args:
            data: List of data items with 'features' key
            
        Returns:
            List of anomaly dictionaries
        """
        if not data:
            return []
        
        if not self.feature_stats:
            self.logger.error("Model not trained")
            return []
        
        # Extract features with alignment
        feature_matrix, _ = self._extract_features_aligned(data, self.training_feature_names)
        
        if feature_matrix.shape[0] == 0:
            return []
        
        # Calculate max absolute Z-score for each sample
        z_scores = np.zeros(feature_matrix.shape[0])
        
        for i in range(feature_matrix.shape[0]):
            max_z_score = 0.0
            
            for j, feature_name in enumerate(self.training_feature_names):
                if feature_name in self.feature_stats:
                    value = feature_matrix[i, j]
                    mean = self.feature_stats[feature_name]["mean"]
                    std = self.feature_stats[feature_name]["std"]
                    
                    # Calculate Z-score
                    z_score = (value - mean) / std
                    max_z_score = max(max_z_score, abs(z_score))
            
            z_scores[i] = max_z_score
        
        # Normalize scores to 0-1 range
        normalized_scores = self._normalize_scores(z_scores)
        
        # Diagnostic logging for detection rate analysis
        if len(normalized_scores) > 0:
            max_score = float(np.max(normalized_scores))
            min_score = float(np.min(normalized_scores))
            mean_score = float(np.mean(normalized_scores))
            scores_above_threshold = np.sum(normalized_scores >= self.threshold)
            self.logger.info(f"Detection stats: threshold={self.threshold}, "
                           f"max_score={max_score:.4f}, min_score={min_score:.4f}, "
                           f"mean_score={mean_score:.4f}, above_threshold={scores_above_threshold}/{len(normalized_scores)}")
        
        # Create anomalies for scores above threshold
        anomalies = []
        for i, score in enumerate(normalized_scores):
            if score >= self.threshold:
                try:
                    anomaly = self.create_anomaly(
                        item=data[i],
                        score=float(score),
                        details={
                            "raw_z_score": float(z_scores[i]),
                            "normalized_score": float(score)
                        }
                    )
                    anomalies.append(anomaly)
                except Exception as e:
                    self.logger.error(f"Error creating anomaly for item {i}: {e}")
        
        self.logger.info(f"Detected {len(anomalies)} anomalies from {len(data)} samples (threshold={self.threshold})")
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
        
        # Create feature matrix with target dimensions
        n_samples = len(data)
        n_features = len(target_feature_names)
        feature_matrix = np.zeros((n_samples, n_features))
        
        # Fill feature matrix
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
        
        # Restore feature_stats from model_state
        if "feature_stats" in self.model_state:
            self.feature_stats = self.model_state["feature_stats"]
        # Also check in state dict directly (for compatibility)
        elif "state" in state and "feature_stats" in state["state"]:
            self.feature_stats = state["state"]["feature_stats"]
            self.model_state["feature_stats"] = self.feature_stats
        
        if "feature_names" in self.model_state:
            self.training_feature_names = self.model_state["feature_names"]
        elif "state" in state and "feature_names" in state.get("state", {}):
            self.training_feature_names = state["state"]["feature_names"]
            self.model_state["feature_names"] = self.training_feature_names
        
        if "window_size" in self.model_state:
            self.window_size = int(self.model_state["window_size"])
        
        if "threshold_multiplier" in self.model_state:
            self.threshold_multiplier = float(self.model_state["threshold_multiplier"])
        
        # Ensure is_trained is set if we have feature_stats
        if self.feature_stats and not self.is_trained:
            self.is_trained = True
            self.logger.info("Set is_trained=True based on restored feature_stats")
        
        self.logger.info(f"Loaded model state, is_trained={self.is_trained}, has_feature_stats={bool(self.feature_stats)}")