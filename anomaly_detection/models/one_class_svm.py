"""
One-Class SVM model for anomaly detection.

This module provides an implementation of the One-Class SVM algorithm
for unsupervised anomaly detection.
"""

import logging
import pickle
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple

try:
    from sklearn.svm import OneClassSVM
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not installed. OneClassSVMModel will not work.")

from anomaly_detection.models.base import AnomalyDetectionModel


class OneClassSVMModel(AnomalyDetectionModel):
    """
    Anomaly detection model using the One-Class SVM algorithm.
    
    One-Class SVM is an unsupervised anomaly detection algorithm that
    learns a decision boundary that maximizes the margin between the
    origin and the data points.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize One-Class SVM model with configuration.
        
        Args:
            name: Model name
            config: Model configuration
        """
        super().__init__(name, config)
        
        if not SKLEARN_AVAILABLE:
            self.logger.error("scikit-learn not installed. OneClassSVMModel will not work.")
            return
        
        # Model hyperparameters - convert to Python types
        self.kernel = str(config.get("kernel", "rbf"))
        self.nu = float(config.get("nu", 0.01))
        self.gamma = config.get("gamma", "scale")  # Can be "scale", "auto" or a float
        if isinstance(self.gamma, (int, float, np.number)):
            self.gamma = float(self.gamma)
        
        # Feature selection
        self.feature_prefix = config.get("feature_prefix", None)
        
        # Convert threshold to Python float (from parent class)
        self.threshold = float(self.threshold)
        
        # Create the model
        self.model = OneClassSVM(
            kernel=self.kernel,
            nu=self.nu,
            gamma=self.gamma
        )
        
        # Store training features
        self.training_feature_names = None
        
        self.logger.info(f"Initialized One-Class SVM model with kernel={self.kernel}, nu={self.nu}")
    
    def train(self, data: List[Dict[str, Any]]) -> None:
        """
        Train the One-Class SVM model on the provided data.
        
        Args:
            data: List of data items with features
        """
        if not SKLEARN_AVAILABLE:
            self.logger.error("scikit-learn not installed. Cannot train model.")
            return
        
        # Extract feature vectors
        feature_matrix, feature_names = self._extract_features(data)
        
        if feature_matrix.shape[0] == 0:
            self.logger.error("No features found in training data.")
            return
        
        # Store feature names for later use in detection
        self.training_feature_names = feature_names
        
        self.logger.info(f"Training One-Class SVM model on {feature_matrix.shape[0]} "
                       f"samples with {feature_matrix.shape[1]} features")
        
        # Fit the model
        self.model.fit(feature_matrix)
        
        # Save model state
        try:
            self.model_state = {
                "model_pickle": pickle.dumps(self.model),
                "feature_names": feature_names,
                "trained": True
            }
            self.is_trained = True
            self.logger.info(f"Model training completed and state saved")
        except Exception as e:
            self.logger.error(f"Error saving model state: {str(e)}")
    
    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in the provided data using the One-Class SVM model.
        
        Args:
            data: List of data items with features
            
        Returns:
            List of anomaly objects
        """
        if not SKLEARN_AVAILABLE:
            self.logger.error("scikit-learn not installed. Cannot detect anomalies.")
            return []
        
        # Load model if necessary
        if self.model is None and "model_pickle" in self.model_state:
            try:
                self.model = pickle.loads(self.model_state["model_pickle"])
                # Load training feature names as well
                if "feature_names" in self.model_state:
                    self.training_feature_names = self.model_state["feature_names"]
                self.logger.info("Loaded model from saved state")
            except Exception as e:
                self.logger.error(f"Error loading model from state: {str(e)}")
                return []
        
        if self.model is None:
            self.logger.error("No trained model available. Cannot detect anomalies.")
            return []
        
        # Extract feature vectors - now with feature alignment
        feature_matrix, _ = self._extract_features_aligned(data, self.training_feature_names)
        
        if feature_matrix.shape[0] == 0:
            self.logger.error("No features found in detection data.")
            return []
        
        self.logger.info(f"Detecting anomalies in {feature_matrix.shape[0]} samples")
        
        # Get predictions (-1 for anomalies, 1 for normal samples)
        predictions = self.model.predict(feature_matrix)
        
        # Get decision function scores (negative values for anomalies)
        scores = -self.model.decision_function(feature_matrix)
        
        # Log diagnostic info
        n_anomaly_predictions = int(np.sum(predictions == -1))
        self.logger.info(f"SVM predictions: {n_anomaly_predictions}/{len(predictions)} classified as anomaly (prediction=-1)")

        # Detect anomalies
        anomalies = []

        for i, (item, pred, score) in enumerate(zip(data, predictions, scores)):
            # For One-Class SVM, prediction of -1 indicates an anomaly
            # We also use the decision function value as a score

            # Normalize score to [0, 1] range - ensure Python float
            normalized_score = float(1.0 / (1.0 + np.exp(-score)))

            # Convert prediction to Python int
            prediction = int(pred)

            # If prediction is -1 AND score exceeds threshold, it's an anomaly
            if prediction == -1 and normalized_score >= self.threshold:
                details = {
                    "score": float(normalized_score),
                    "raw_score": float(score),
                    "prediction": int(pred),
                    "feature_count": int(feature_matrix.shape[1])
                }
                
                # Make sure to pass Python float for score
                anomaly = self.create_anomaly(item, float(normalized_score), details)
                anomalies.append(anomaly)
        
        self.logger.info(f"Detected {len(anomalies)} anomalies")
        return anomalies
    
    def _safe_scalar_conversion(self, feature_value: Any, feature_name: str = "") -> float:
        """
        Safely convert any feature value to a scalar float.
        
        This method handles various data types that might appear in features:
        - Scalars (int, float, bool) - converted directly
        - Lists/arrays - converted to length (count)
        - None values - converted to 0.0
        - Strings - converted to hash value
        - Dicts - converted to number of keys
        
        Args:
            feature_value: The value to convert
            feature_name: Name of the feature (for logging)
        
        Returns:
            float: Scalar value suitable for feature matrix
        """
        # Handle None
        if feature_value is None:
            return 0.0
        
        # Handle already-scalar numeric values
        if isinstance(feature_value, (int, float, bool, np.integer, np.floating, np.bool_)):
            return float(feature_value)
        
        # Handle sequences (lists, tuples, arrays) - THE FIX FOR THE BUG
        if isinstance(feature_value, (list, tuple, np.ndarray)):
            if len(feature_value) == 0:
                return 0.0
            elif len(feature_value) == 1:
                # Single-element array - extract and convert the element
                return self._safe_scalar_conversion(feature_value[0], feature_name)
            else:
                # Multi-element array - try to compute mean if numeric, otherwise use count
                try:
                    # Check if all elements are numeric
                    numeric_values = []
                    for item in feature_value:
                        if isinstance(item, (int, float, bool, np.number)):
                            numeric_values.append(float(item))
                    
                    if len(numeric_values) == len(feature_value) and len(numeric_values) > 0:
                        # All elements are numeric - use mean
                        return float(np.mean(numeric_values))
                except (ValueError, TypeError):
                    pass
                
                # Default to count for non-numeric or mixed arrays
                return float(len(feature_value))
        
        # Handle strings
        if isinstance(feature_value, str):
            # For categorical strings, use hash (modulo to keep reasonable range)
            return float(hash(feature_value) % 10000)
        
        # Handle dicts/objects
        if isinstance(feature_value, dict):
            # Use number of keys
            return float(len(feature_value))
        
        # Fallback for any other type
        try:
            return float(feature_value)
        except (ValueError, TypeError):
            # Last resort - use hash
            self.logger.debug(f"Converting non-standard type {type(feature_value).__name__} for feature '{feature_name}' using hash")
            return float(hash(str(feature_value)) % 10000)
    
    def _extract_features(self, data: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[str]]:
        """
        Extract feature vectors from data items.
        
        Args:
            data: List of data items with features
            
        Returns:
            Tuple of (feature_matrix, feature_names)
        """
        if not data:
            return np.array([]), []
        
        # Collect all feature names first
        all_features = set()
        
        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                for feature_name in item["features"]:
                    # Apply feature prefix filter if configured
                    if self.feature_prefix is None or feature_name.startswith(self.feature_prefix):
                        all_features.add(feature_name)
        
        feature_names = sorted(all_features)
        
        if not feature_names:
            self.logger.warning("No features found in data.")
            return np.array([]), []
        
        # Create feature matrix
        n_samples = len(data)
        n_features = len(feature_names)
        feature_matrix = np.zeros((n_samples, n_features), dtype=np.float64)
        
        # Track any conversion warnings (only log once per feature)
        conversion_warnings = {}
        
        # Fill feature matrix with safe conversion
        for i, item in enumerate(data):
            if "features" in item and isinstance(item["features"], dict):
                for j, feature_name in enumerate(feature_names):
                    # Get feature value with default of 0.0
                    feature_value = item["features"].get(feature_name, 0.0)
                    
                    # Debug: Log non-scalar values (only once per feature)
                    if isinstance(feature_value, (list, tuple, np.ndarray)) and feature_name not in conversion_warnings:
                        self.logger.debug(
                            f"Feature '{feature_name}' contains non-scalar value: "
                            f"type={type(feature_value).__name__}, "
                            f"converting to scalar (using count or mean)"
                        )
                        conversion_warnings[feature_name] = True
                    
                    # Safely convert to scalar - THIS IS THE KEY FIX
                    try:
                        scalar_value = self._safe_scalar_conversion(feature_value, feature_name)
                        feature_matrix[i, j] = scalar_value
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to convert feature '{feature_name}' value '{feature_value}': {e}. Using 0."
                        )
                        feature_matrix[i, j] = 0.0
        
        # Log summary of conversions
        if conversion_warnings:
            self.logger.info(
                f"Converted {len(conversion_warnings)} non-scalar features to scalar values: "
                f"{', '.join(list(conversion_warnings.keys())[:5])}{'...' if len(conversion_warnings) > 5 else ''}"
            )
        
        # Validate feature matrix
        if np.isnan(feature_matrix).any():
            nan_count = np.isnan(feature_matrix).sum()
            self.logger.warning(f"Feature matrix contains {nan_count} NaN values. Replacing with 0.")
            feature_matrix = np.nan_to_num(feature_matrix, nan=0.0)
        
        if np.isinf(feature_matrix).any():
            inf_count = np.isinf(feature_matrix).sum()
            self.logger.warning(f"Feature matrix contains {inf_count} Inf values. Replacing with 0.")
            feature_matrix = np.nan_to_num(feature_matrix, posinf=0.0, neginf=0.0)
        
        self.logger.debug(
            f"Feature extraction complete. Matrix shape: {feature_matrix.shape}, "
            f"Value range: [{feature_matrix.min():.2f}, {feature_matrix.max():.2f}]"
        )
        
        return feature_matrix, feature_names
    
    def _extract_features_aligned(self, data: List[Dict[str, Any]], target_feature_names: List[str] = None) -> Tuple[np.ndarray, List[str]]:
        """
        Extract features aligned with the specified target features.
        
        This ensures that feature vectors are compatible with a trained model, regardless of
        feature differences in the input data.
        
        Args:
            data: List of data items with features
            target_feature_names: List of feature names to align with (if None, extracts all)
            
        Returns:
            Tuple of (feature_matrix, feature_names)
        """
        if not data:
            return np.array([]), []
        
        # If no target feature names provided, just do normal extraction
        if target_feature_names is None:
            return self._extract_features(data)
            
        # Use the provided target feature names
        feature_names = target_feature_names
        
        # Log a warning if we detect feature mismatch
        all_available_features = set()
        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                all_available_features.update(item["features"].keys())
        
        missing_features = set(feature_names) - all_available_features
        extra_features = all_available_features - set(feature_names)
        
        if missing_features or extra_features:
            self.logger.warning(f"Feature mismatch detected: missing {len(missing_features)} features, {len(extra_features)} extra features")
            self.logger.debug(f"Missing features: {missing_features if len(missing_features) < 10 else f'{len(missing_features)} features'}")
        
        # Create feature matrix with dimensions matching the target features
        n_samples = len(data)
        n_features = len(feature_names)
        feature_matrix = np.zeros((n_samples, n_features), dtype=np.float64)
        
        # Track conversion warnings
        conversion_warnings = {}
        
        # Fill feature matrix with safe conversion - ensuring all values are scalars
        for i, item in enumerate(data):
            if "features" in item and isinstance(item["features"], dict):
                for j, feature_name in enumerate(feature_names):
                    # Get feature value with default of 0.0 for missing features
                    feature_value = item["features"].get(feature_name, 0.0)
                    
                    # Debug: Log non-scalar values (only once per feature)
                    if isinstance(feature_value, (list, tuple, np.ndarray)) and feature_name not in conversion_warnings:
                        self.logger.debug(
                            f"Feature '{feature_name}' contains non-scalar value during detection: "
                            f"type={type(feature_value).__name__}"
                        )
                        conversion_warnings[feature_name] = True
                    
                    # Safely convert to scalar - SAME FIX APPLIED HERE
                    try:
                        scalar_value = self._safe_scalar_conversion(feature_value, feature_name)
                        feature_matrix[i, j] = scalar_value
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to convert feature '{feature_name}' value '{feature_value}': {e}. Using 0."
                        )
                        feature_matrix[i, j] = 0.0
        
        # Log summary
        if conversion_warnings:
            self.logger.debug(
                f"Converted {len(conversion_warnings)} non-scalar features during detection"
            )
        
        # Validate feature matrix
        if np.isnan(feature_matrix).any():
            nan_count = np.isnan(feature_matrix).sum()
            self.logger.warning(f"Feature matrix contains {nan_count} NaN values. Replacing with 0.")
            feature_matrix = np.nan_to_num(feature_matrix, nan=0.0)
        
        if np.isinf(feature_matrix).any():
            inf_count = np.isinf(feature_matrix).sum()
            self.logger.warning(f"Feature matrix contains {inf_count} Inf values. Replacing with 0.")
            feature_matrix = np.nan_to_num(feature_matrix, posinf=0.0, neginf=0.0)
        
        return feature_matrix, feature_names
    
    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Set the model state from serialized state.
        
        Args:
            state: Dictionary with model state
        """
        super().set_state(state)
        
        if "model_pickle" in self.model_state and SKLEARN_AVAILABLE:
            try:
                self.model = pickle.loads(self.model_state["model_pickle"])
                # Also load feature names
                if "feature_names" in self.model_state:
                    self.training_feature_names = self.model_state["feature_names"]
                self.logger.info("Loaded model from saved state")
            except Exception as e:
                self.logger.error(f"Error loading model from state: {str(e)}")