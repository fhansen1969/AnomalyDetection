"""
Score Normalizer for Anomaly Detection Models

Provides standardized score normalization across all models to ensure
comparable anomaly scores regardless of the underlying algorithm.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from sklearn.preprocessing import MinMaxScaler
import logging
from datetime import datetime

class Normalizer:
    """
    Data normalizer for ensuring consistent data structure.
    
    This is DIFFERENT from ScoreNormalizer (which normalizes anomaly scores).
    This class normalizes RAW DATA before processing.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """
        Initialize data normalizer.
        
        Args:
            name: Normalizer name
            config: Configuration dictionary
            storage_manager: Optional storage manager
        """
        self.name = name
        self.config = config
        self.storage_manager = storage_manager
        self.logger = logging.getLogger(f"Normalizer.{name}")
        
        # Extract configuration
        self.timestamp_field = config.get('timestamp_field', 'timestamp')
        self.timestamp_format = config.get('timestamp_format', '%Y-%m-%dT%H:%M:%S.%fZ')
        self.default_timezone = config.get('default_timezone', 'UTC')
        
        self.logger.info(f"Data normalizer '{name}' initialized")
    
    def process(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process and normalize data to ensure consistent structure.
        
        Args:
            data: List of dictionaries with raw data
            
        Returns:
            List of normalized data dictionaries
        """
        if not data:
            self.logger.warning("No data to normalize")
            return []
        
        normalized = []
        
        for item in data:
            if not isinstance(item, dict):
                self.logger.warning(f"Skipping non-dict item: {type(item)}")
                continue
            
            # Create normalized copy
            norm_item = item.copy()
            
            # Ensure timestamp field exists
            if self.timestamp_field not in norm_item:
                # Try common timestamp field names
                for ts_field in ['createdAt', 'created_at', 'timestamp', 'time', 'date']:
                    if ts_field in norm_item:
                        norm_item[self.timestamp_field] = norm_item[ts_field]
                        break
                else:
                    # Use current time if no timestamp found
                    norm_item[self.timestamp_field] = datetime.utcnow().isoformat()
                    self.logger.debug("No timestamp found, using current time")
            
            # Ensure id field exists
            if 'id' not in norm_item:
                # Try common id field names
                for id_field in ['_id', 'uuid', 'identifier']:
                    if id_field in norm_item:
                        norm_item['id'] = str(norm_item[id_field])
                        break
                else:
                    # Generate ID from hash if not found
                    norm_item['id'] = str(hash(str(norm_item)))
                    self.logger.debug(f"No ID found, generated: {norm_item['id']}")
            
            normalized.append(norm_item)
        
        self.logger.info(f"Normalized {len(normalized)} items (from {len(data)} input)")
        return normalized
    
    def __repr__(self):
        return f"Normalizer(name='{self.name}')"

class ScoreNormalizer:
    """
    Normalizes anomaly scores to a consistent [0, 1] range using various methods.
    
    All methods ensure:
    - 0 = definitely normal
    - 1 = definitely anomalous
    - Scores are comparable across different models
    """
    
    def __init__(self, method: str = "sigmoid", calibration_percentile: float = 99.0):
        """
        Initialize score normalizer.
        
        Args:
            method: Normalization method - 'sigmoid', 'minmax', 'percentile', 'zscore'
            calibration_percentile: For percentile method, scores above this are clamped to 1.0
        """
        self.method = method
        self.calibration_percentile = calibration_percentile
        self.logger = logging.getLogger("ScoreNormalizer")
        
        # Fitted parameters
        self.min_score = None
        self.max_score = None
        self.percentile_threshold = None
        self.mean_score = None
        self.std_score = None
        self.fitted = False
        
    def fit(self, raw_scores: np.ndarray):
        """
        Fit normalizer on training scores.
        
        Args:
            raw_scores: Array of raw anomaly scores from training
        """
        if len(raw_scores) == 0:
            self.logger.warning("Cannot fit on empty scores")
            return
        
        self.min_score = float(np.min(raw_scores))
        self.max_score = float(np.max(raw_scores))
        self.mean_score = float(np.mean(raw_scores))
        self.std_score = float(np.std(raw_scores))
        
        if self.method == "percentile":
            self.percentile_threshold = float(np.percentile(raw_scores, self.calibration_percentile))
        
        self.fitted = True
        self.logger.info(f"Fitted {self.method} normalizer: "
                        f"min={self.min_score:.4f}, max={self.max_score:.4f}, "
                        f"mean={self.mean_score:.4f}, std={self.std_score:.4f}")
    
    def normalize(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Normalize raw scores to [0, 1] range.
        
        Args:
            raw_scores: Array of raw anomaly scores
            
        Returns:
            Normalized scores in [0, 1] range
        """
        if self.method == "sigmoid":
            return self._sigmoid_normalize(raw_scores)
        elif self.method == "minmax":
            return self._minmax_normalize(raw_scores)
        elif self.method == "percentile":
            return self._percentile_normalize(raw_scores)
        elif self.method == "zscore":
            return self._zscore_normalize(raw_scores)
        else:
            self.logger.warning(f"Unknown method '{self.method}', using sigmoid")
            return self._sigmoid_normalize(raw_scores)
    
    def _sigmoid_normalize(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Sigmoid normalization: maps (-inf, +inf) to (0, 1).
        
        Good for scores that can be negative (like Isolation Forest decision function).
        """
        # Standard sigmoid with adjustable steepness
        if self.fitted and self.std_score > 0:
            # Center around mean and scale by std
            centered = (raw_scores - self.mean_score) / (self.std_score + 1e-10)
            return 1.0 / (1.0 + np.exp(-centered))
        else:
            # Simple sigmoid without fitting
            return 1.0 / (1.0 + np.exp(-raw_scores))
    
    def _minmax_normalize(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Min-max normalization: maps [min, max] to [0, 1].
        
        Good for bounded scores. Requires fitting.
        """
        if not self.fitted:
            # Fallback: use current batch statistics
            min_val = np.min(raw_scores)
            max_val = np.max(raw_scores)
        else:
            min_val = self.min_score
            max_val = self.max_score
        
        # Handle edge case where all scores are the same
        if max_val - min_val < 1e-10:
            return np.full_like(raw_scores, 0.5, dtype=float)
        
        normalized = (raw_scores - min_val) / (max_val - min_val)
        
        # Clip to [0, 1]
        return np.clip(normalized, 0.0, 1.0)
    
    def _percentile_normalize(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Percentile normalization: scores above Nth percentile map to 1.0.
        
        Good for handling outliers. Requires fitting.
        """
        if not self.fitted or self.percentile_threshold is None:
            # Fallback: use current batch
            threshold = np.percentile(raw_scores, self.calibration_percentile)
        else:
            threshold = self.percentile_threshold
        
        # Normalize to [0, 1] with threshold as max
        if threshold < 1e-10:
            return np.full_like(raw_scores, 0.5, dtype=float)
        
        normalized = raw_scores / threshold
        
        # Clip to [0, 1]
        return np.clip(normalized, 0.0, 1.0)
    
    def _zscore_normalize(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Z-score normalization: converts to z-scores then applies sigmoid.
        
        Good for normally distributed scores.
        """
        if not self.fitted:
            # Fallback: use current batch statistics
            mean = np.mean(raw_scores)
            std = np.std(raw_scores)
        else:
            mean = self.mean_score
            std = self.std_score
        
        if std < 1e-10:
            return np.full_like(raw_scores, 0.5, dtype=float)
        
        # Convert to z-scores
        z_scores = (raw_scores - mean) / std
        
        # Apply sigmoid to map to [0, 1]
        # Use steeper sigmoid: scores 3 std away map to ~0.95
        return 1.0 / (1.0 + np.exp(-z_scores / 1.5))
    
    def get_threshold_for_fpr(self, raw_scores: np.ndarray, labels: np.ndarray, 
                             target_fpr: float = 0.01) -> float:
        """
        Calculate normalized threshold for a target false positive rate.
        
        Args:
            raw_scores: Raw anomaly scores from validation set
            labels: True labels (0=normal, 1=anomaly)
            target_fpr: Target false positive rate (e.g., 0.01 = 1%)
            
        Returns:
            Normalized threshold value
        """
        # Normalize scores
        normalized_scores = self.normalize(raw_scores)
        
        # Get scores for normal samples
        normal_scores = normalized_scores[labels == 0]
        
        if len(normal_scores) == 0:
            self.logger.warning("No normal samples for FPR calculation")
            return 0.5
        
        # Find threshold where FPR equals target
        threshold = np.percentile(normal_scores, (1 - target_fpr) * 100)
        
        self.logger.info(f"Threshold for {target_fpr:.1%} FPR: {threshold:.4f}")
        
        return float(threshold)


def create_model_normalizer(model_type: str) -> ScoreNormalizer:
    """
    Create appropriate normalizer for a given model type.
    
    Args:
        model_type: Type of anomaly detection model
        
    Returns:
        Configured ScoreNormalizer
    """
    # Model-specific default normalization strategies
    if model_type in ["IsolationForestModel", "isolation_forest"]:
        # Isolation Forest decision_function returns negative values for anomalies
        # Sigmoid normalization works well
        return ScoreNormalizer(method="sigmoid")
    
    elif model_type in ["OneClassSVMModel", "one_class_svm"]:
        # One-class SVM also returns signed distance
        return ScoreNormalizer(method="sigmoid")
    
    elif model_type in ["StatisticalModel", "statistical"]:
        # Z-score based model, percentile normalization works well
        return ScoreNormalizer(method="percentile", calibration_percentile=95.0)
    
    elif model_type in ["AutoencoderModel", "autoencoder"]:
        # Reconstruction error, use minmax or percentile
        return ScoreNormalizer(method="percentile", calibration_percentile=99.0)
    
    elif model_type in ["GANAnomalyDetector", "gan"]:
        # Discriminator score, use sigmoid
        return ScoreNormalizer(method="sigmoid")
    
    else:
        # Default: sigmoid normalization (works for most cases)
        return ScoreNormalizer(method="sigmoid")


class MultiModelNormalizer:
    """
    Manages normalization for multiple models in an ensemble.
    
    Ensures all models output scores in the same [0, 1] range
    with consistent meaning.
    """
    
    def __init__(self):
        """Initialize multi-model normalizer."""
        self.normalizers = {}
        self.logger = logging.getLogger("MultiModelNormalizer")
    
    def add_model(self, model_name: str, model_type: str):
        """
        Add a model to be normalized.
        
        Args:
            model_name: Name of the model
            model_type: Type/class of the model
        """
        self.normalizers[model_name] = create_model_normalizer(model_type)
        self.logger.info(f"Added normalizer for {model_name} ({model_type})")
    
    def fit(self, model_name: str, raw_scores: np.ndarray):
        """
        Fit normalizer for a specific model.
        
        Args:
            model_name: Name of the model
            raw_scores: Raw scores from training/validation
        """
        if model_name not in self.normalizers:
            self.logger.warning(f"Model {model_name} not registered, using default normalizer")
            self.normalizers[model_name] = ScoreNormalizer()
        
        self.normalizers[model_name].fit(raw_scores)
    
    def normalize(self, model_name: str, raw_scores: np.ndarray) -> np.ndarray:
        """
        Normalize scores for a specific model.
        
        Args:
            model_name: Name of the model
            raw_scores: Raw anomaly scores
            
        Returns:
            Normalized scores in [0, 1]
        """
        if model_name not in self.normalizers:
            self.logger.warning(f"Model {model_name} not registered, using simple sigmoid")
            normalizer = ScoreNormalizer()
            return normalizer.normalize(raw_scores)
        
        return self.normalizers[model_name].normalize(raw_scores)
    
    def get_normalizer(self, model_name: str) -> Optional[ScoreNormalizer]:
        """Get normalizer for a specific model."""
        return self.normalizers.get(model_name)


# Helper functions for common use cases

def normalize_isolation_forest_scores(decision_function_output: np.ndarray) -> np.ndarray:
    """
    Normalize Isolation Forest decision function output to [0, 1].
    
    Isolation Forest returns negative values for anomalies.
    This inverts and normalizes them properly.
    
    Args:
        decision_function_output: Output from IsolationForest.decision_function()
        
    Returns:
        Normalized scores where higher = more anomalous
    """
    # Invert (more negative = more anomalous)
    inverted = -decision_function_output
    
    # Sigmoid normalization
    normalizer = ScoreNormalizer(method="sigmoid")
    return normalizer.normalize(inverted)


def normalize_reconstruction_error(reconstruction_errors: np.ndarray, 
                                   percentile: float = 99.0) -> np.ndarray:
    """
    Normalize reconstruction errors (from Autoencoder) to [0, 1].
    
    Args:
        reconstruction_errors: Raw reconstruction errors
        percentile: Errors above this percentile map to ~1.0
        
    Returns:
        Normalized scores
    """
    normalizer = ScoreNormalizer(method="percentile", calibration_percentile=percentile)
    normalizer.fit(reconstruction_errors)
    return normalizer.normalize(reconstruction_errors)


def normalize_zscore_based(z_scores: np.ndarray) -> np.ndarray:
    """
    Normalize Z-score based anomaly scores to [0, 1].
    
    Args:
        z_scores: Absolute Z-scores or similar metrics
        
    Returns:
        Normalized scores
    """
    normalizer = ScoreNormalizer(method="zscore")
    normalizer.fit(z_scores)
    return normalizer.normalize(z_scores)