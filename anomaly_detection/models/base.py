"""
Base classes for anomaly detection models - COMPLETE UPDATED VERSION

This module defines abstract base classes for machine learning models used
in the anomaly detection system.

UPDATES:
- Support for improved models with evaluation metrics
- Better error handling and logging
- Helper methods for model management
- Backwards compatible with existing models
"""

import abc
import logging
import uuid
import datetime
import numpy as np
from typing import Dict, List, Any, Optional, Union


class AnomalyDetectionModel(abc.ABC):
    """
    Abstract base class for anomaly detection models.
    
    A model is responsible for analyzing data features to detect anomalies.
    All models (standard and improved) inherit from this class.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """
        Initialize model with a name and configuration.
        
        Args:
            name: Model name/identifier
            config: Model configuration dictionary
            storage_manager: Optional storage manager for persistence
        """
        self.name = name
        self.config = config
        self.storage_manager = storage_manager
        self.logger = logging.getLogger(f"model.{name}")
        self.model = None
        self.model_state = {}
        self.threshold = float(config.get("threshold", 0.7))
        self.is_trained = False
        self.performance: Dict[str, Any] = {}
        
        self.logger.info(f"Initialized {self.__class__.__name__} '{name}'")
    
    @abc.abstractmethod
    def train(self, data: List[Dict[str, Any]]) -> None:
        """
        Train the model on the provided data.
        
        Args:
            data: List of data items with 'features' key
        """
        pass
    
    @abc.abstractmethod
    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in the provided data.
        
        Args:
            data: List of data items with 'features' key
            
        Returns:
            List of anomaly dictionaries with metadata
        """
        pass
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get the current state of the model for serialization.
        
        Returns:
            Dictionary with model state including:
            - name: Model name
            - type: Model class name
            - timestamp: When state was captured
            - state: Model-specific state data
            - is_trained: Whether model is trained
        """
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "state": self.model_state,
            "is_trained": self.is_trained,
            "threshold": self.threshold
        }
    
    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Set the model state from serialized state.
        
        Args:
            state: Dictionary with model state
        """
        if "state" in state:
            self.model_state = state["state"]
        if "is_trained" in state:
            self.is_trained = state["is_trained"]
        if "threshold" in state:
            self.threshold = float(state["threshold"])
        
        self.logger.info(f"Loaded state for model '{self.name}', trained={self.is_trained}")
    
    def save(self, path: Optional[str] = None) -> None:
        """
        Save model to storage.
        
        Args:
            path: Optional custom save path (if storage_manager supports it)
        """
        if self.storage_manager:
            state = self.get_state()
            self.storage_manager.save_model(self.name, state)
            self.logger.info(f"Model '{self.name}' saved to storage")
        else:
            self.logger.warning(f"No storage manager configured, cannot save model '{self.name}'")
    
    def load(self, path: Optional[str] = None) -> bool:
        """
        Load model from storage.
        
        Args:
            path: Optional custom load path (if storage_manager supports it)
            
        Returns:
            True if loaded successfully, False otherwise
        """
        if self.storage_manager:
            state = self.storage_manager.load_model(self.name)
            if state:
                self.set_state(state)
                self.logger.info(f"Model '{self.name}' loaded from storage")
                return True
            else:
                self.logger.warning(f"No saved state found for model '{self.name}'")
                return False
        else:
            self.logger.warning(f"No storage manager configured, cannot load model '{self.name}'")
            return False
    
    def create_anomaly(self, item: Dict[str, Any], score: float, 
                      details: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create an anomaly object from a data item.
        
        Args:
            item: Original data item
            score: Anomaly score (0-1, higher is more anomalous)
            details: Additional details about the anomaly
            
        Returns:
            Anomaly dictionary with standardized structure
        """
        # Validate inputs
        if not isinstance(item, dict):
            self.logger.warning(f"Item is not a dictionary, creating empty item")
            item = {}
        
        # Extract or generate anomaly ID
        anomaly_id = item.get("id")
        if not anomaly_id:
            anomaly_id = str(uuid.uuid4())
        
        # Extract or generate timestamp
        timestamp = item.get("timestamp")
        if not timestamp:
            timestamp = datetime.datetime.utcnow().isoformat()
        
        # Validate details
        if details is None:
            details = {}
        elif not isinstance(details, dict):
            self.logger.warning(f"Details is not a dictionary, converting")
            details = {"raw_details": str(details)}
        
        # Validate score
        try:
            score = float(score)
            # Ensure score is in [0, 1] range
            score = max(0.0, min(1.0, score))
        except (ValueError, TypeError):
            self.logger.warning(f"Invalid score value {score}, using default 0.5")
            score = 0.5
        
        # Validate threshold
        try:
            threshold = float(self.threshold)
        except (ValueError, TypeError):
            self.logger.warning(f"Invalid threshold value {self.threshold}, using default 0.7")
            threshold = 0.7
        
        # Determine model name
        model_name = self.name if self.name else self.__class__.__name__
        
        # Create anomaly object
        anomaly = {
            "id": anomaly_id,
            "timestamp": timestamp,
            "detection_time": datetime.datetime.utcnow().isoformat(),
            "model": model_name,
            "model_type": self.__class__.__name__,
            "score": score,
            "threshold": threshold,
            "original_data": item,
            "details": details
        }
        
        # Include features if present
        if "features" in item and isinstance(item["features"], dict):
            anomaly["features"] = item["features"]

        # Determine severity based on score
        if score >= 0.9:
            anomaly["severity"] = "Critical"
        elif score >= 0.8:
            anomaly["severity"] = "High"
        elif score >= 0.6:
            anomaly["severity"] = "Medium"
        else:
            anomaly["severity"] = "Low"

        # --- Enrichment: score analysis ---
        score_percentile = (
            "top 1%"    if score >= 0.99 else
            "top 5%"    if score >= 0.95 else
            "top 10%"   if score >= 0.90 else
            "top 20%"   if score >= 0.80 else
            "top 30%"   if score >= 0.70 else
            "top 50%"   if score >= 0.50 else
            "bottom 50%"
        )
        anomaly_magnitude = (
            "Extreme"  if score >= 0.90 else
            "High"     if score >= 0.70 else
            "Moderate" if score >= 0.50 else
            "Low"
        )
        details["score_percentile"] = score_percentile
        details["score_band"] = min(10, max(1, round(score * 10)))
        details["anomaly_magnitude"] = anomaly_magnitude

        # --- Enrichment: feature summary ---
        feat_dict = item.get("features", {}) if isinstance(item, dict) else {}
        if not isinstance(feat_dict, dict):
            feat_dict = {}
        feat_names = sorted(feat_dict.keys())
        details["feature_count"] = len(feat_names)
        if feat_names:
            details["contributing_features"] = feat_names[:20]
        # Top 5 numeric features by absolute value
        numeric_feats = {}
        for k, v in feat_dict.items():
            try:
                numeric_feats[k] = float(v)
            except (ValueError, TypeError):
                pass
        if numeric_feats:
            top5 = sorted(numeric_feats.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
            details["top_features_by_value"] = {k: round(v, 4) for k, v in top5}

        # --- Enrichment: network field extraction ---
        # Pull src/dst IP from item top-level or features, so downstream consumers
        # don't have to re-parse original_data themselves.
        if isinstance(item, dict):
            for src_field in ("src_ip", "source_ip", "sourceIp", "ip", "ip_address"):
                val = item.get(src_field)
                if val is None and isinstance(feat_dict, dict):
                    val = feat_dict.get(src_field)
                if val:
                    anomaly["src_ip"] = str(val)
                    break
            for dst_field in ("dst_ip", "dest_ip", "destination_ip", "destIp", "remote_ip"):
                val = item.get(dst_field)
                if val is None and isinstance(feat_dict, dict):
                    val = feat_dict.get(dst_field)
                if val:
                    anomaly["dst_ip"] = str(val)
                    break

        return anomaly
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', trained={self.is_trained})"


class ImprovedAnomalyDetectionModel(AnomalyDetectionModel):
    """
    Improved base class for anomaly detection models with standardized scoring.
    
    This class extends AnomalyDetectionModel with:
    - Standardized score normalization (0-1 range)
    - Proper handling of negative scores
    - Template method pattern for scoring
    - Support for evaluation metrics
    
    Subclasses should implement:
    - _get_anomaly_scores(data): Return raw anomaly scores (can be any range)
    """
    
    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """Initialize improved model."""
        super().__init__(name, config, storage_manager)
    
    @abc.abstractmethod
    def _get_anomaly_scores(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """
        Get raw anomaly scores from the model.
        
        Subclasses must implement this to return raw scores for each data point.
        Scores can be in any range - they will be normalized by detect().
        
        Args:
            data: List of data items with 'features' key
            
        Returns:
            Numpy array of raw anomaly scores (higher = more anomalous)
        """
        pass
    
    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies using standardized scoring.
        
        This method:
        1. Calls _get_anomaly_scores() to get raw scores
        2. Normalizes scores to 0-1 range
        3. Filters by threshold
        4. Creates anomaly objects
        
        Args:
            data: List of data items with 'features' key
            
        Returns:
            List of anomaly dictionaries
        """
        if not data:
            return []
        
        try:
            # Get raw scores from subclass
            raw_scores = self._get_anomaly_scores(data)
            
            if raw_scores is None or len(raw_scores) == 0:
                self.logger.warning("No scores returned from _get_anomaly_scores")
                return []
            
            # Normalize scores to 0-1 range
            normalized_scores = self._normalize_scores(raw_scores)
            
            # Create anomalies for scores above threshold
            anomalies = []
            for i, score in enumerate(normalized_scores):
                if score >= self.threshold:
                    try:
                        anomaly = self.create_anomaly(
                            item=data[i],
                            score=float(score),
                            details={
                                "raw_score": float(raw_scores[i]),
                                "normalized_score": float(score)
                            }
                        )
                        anomalies.append(anomaly)
                    except Exception as e:
                        self.logger.error(f"Error creating anomaly for item {i}: {e}")
            
            self.logger.info(f"Detected {len(anomalies)} anomalies from {len(data)} samples")
            return anomalies
            
        except Exception as e:
            self.logger.error(f"Error in detect: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []
    
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
    
    def evaluate(self, data: List[Dict[str, Any]], 
                labels: List[int]) -> Dict[str, float]:
        """
        Evaluate model performance on labeled data.
        
        Args:
            data: List of data items with 'features' key
            labels: True labels (1 for anomaly, 0 for normal)
            
        Returns:
            Dictionary with evaluation metrics:
            - accuracy: Overall accuracy
            - precision: Anomaly detection precision
            - recall: Anomaly detection recall
            - f1: F1 score
            - auc: Area under ROC curve (if available)
        """
        if not data or not labels:
            return {}
        
        try:
            # Get predictions
            raw_scores = self._get_anomaly_scores(data)
            normalized_scores = self._normalize_scores(raw_scores)
            predictions = (normalized_scores >= self.threshold).astype(int)
            
            labels = np.array(labels)
            
            # Calculate metrics
            tp = np.sum((predictions == 1) & (labels == 1))
            tn = np.sum((predictions == 0) & (labels == 0))
            fp = np.sum((predictions == 1) & (labels == 0))
            fn = np.sum((predictions == 0) & (labels == 1))
            
            accuracy = (tp + tn) / len(labels) if len(labels) > 0 else 0.0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            metrics = {
                "accuracy": float(accuracy),
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
                "tp": int(tp),
                "tn": int(tn),
                "fp": int(fp),
                "fn": int(fn)
            }
            
            # Calculate AUC if possible
            try:
                from sklearn.metrics import roc_auc_score
                auc = roc_auc_score(labels, normalized_scores)
                metrics["auc"] = float(auc)
            except Exception:
                pass
            
            self.performance = metrics
            return metrics

        except Exception as e:
            self.logger.error(f"Error in evaluate: {e}")
            return {}


class ModelFactory:
    """
    Factory class for creating anomaly detection models based on configuration.
    
    UPDATED VERSION:
    - Supports both standard and improved models
    - Better error handling
    - Ensures ensemble models are created last
    - Provides helper methods for model management
    """
    
    def __init__(self, model_config: Dict[str, Any], storage_manager=None):
        """
        Initialize model factory with configuration.
        
        Args:
            model_config: Model configuration dictionary with:
                - enabled: List of model names to enable
                - <model_name>: Configuration for each model
            storage_manager: Optional storage manager for persistence
        """
        self.config = model_config
        self.storage_manager = storage_manager
        self.logger = logging.getLogger("model_factory")
        
        self.logger.info("Initialized ModelFactory")
    
    def create_models(self, load_saved: bool = False) -> List[AnomalyDetectionModel]:
        """
        Create models based on configuration.
        
        IMPROVED VERSION:
        - Creates ensemble models LAST (fixes "not iterable" error)
        - Tries improved models first, falls back to standard
        - Better error handling and logging
        
        Args:
            load_saved: Whether to load saved model states
            
        Returns:
            List of configured model instances
        """
        enabled_models = self.config.get("enabled", [])
        
        # Handle "all" keyword
        if "all" in enabled_models:
            enabled_models = [m for m in self.config.keys() if m != "enabled"]
        
        self.logger.info(f"Creating models: {enabled_models}")
        
        models = []
        
        # CRITICAL: Create base models first, ensemble last
        base_model_names = [m for m in enabled_models if m != "ensemble"]
        ensemble_needed = "ensemble" in enabled_models
        
        # Create base models
        for model_name in base_model_names:
            model = self._create_single_model(model_name)
            if model:
                models.append(model)
        
        # Create ensemble model LAST (after all base models exist)
        if ensemble_needed:
            model = self._create_single_model("ensemble")
            if model:
                models.append(model)
        
        # Load saved states if requested
        if load_saved and self.storage_manager:
            self.logger.info("Loading saved model states...")
            for model in models:
                try:
                    model.load()
                except Exception as e:
                    self.logger.error(f"Error loading state for model {model.name}: {e}")
        
        self.logger.info(f"Successfully created {len(models)} models")
        return models
    
    def _create_single_model(self, model_name: str) -> Optional[AnomalyDetectionModel]:
        """
        Create a single model by name.
        
        Tries improved version first, falls back to standard.
        
        Args:
            model_name: Name of model to create
            
        Returns:
            Model instance or None if creation failed
        """
        if model_name not in self.config:
            self.logger.warning(f"Configuration not found for model '{model_name}'")
            return None
        
        model_config = self.config[model_name]
        model = None
        
        try:
            if model_name == "statistical":
                model = self._create_statistical_model(model_config)
                
            elif model_name == "isolation_forest":
                model = self._create_isolation_forest_model(model_config)
                
            elif model_name == "one_class_svm":
                model = self._create_one_class_svm_model(model_config)
                
            elif model_name == "autoencoder":
                model = self._create_autoencoder_model(model_config)
                
            elif model_name == "gan":
                model = self._create_gan_model(model_config)
                
            elif model_name == "ensemble":
                model = self._create_ensemble_model(model_config)

            elif model_name == "ecod":
                model = self._create_ecod_model(model_config)

            elif model_name == "extended_iforest":
                model = self._create_extended_iforest_model(model_config)

            elif model_name == "deep_iforest":
                model = self._create_deep_iforest_model(model_config)

            elif model_name == "deep_sad":
                model = self._create_deep_sad_model(model_config)

            else:
                self.logger.warning(f"Unknown model type: {model_name}")
                return None
            
            if model:
                self.logger.info(f"Created {model_name} model: {model.__class__.__name__}")
                return model
            
        except Exception as e:
            self.logger.error(f"Error creating model '{model_name}': {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    def _create_statistical_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create statistical model (improved or standard)."""
        # Try improved version first
        try:
            from improved_statistical_model import ImprovedStatisticalModel
            self.logger.info("Using ImprovedStatisticalModel")
            return ImprovedStatisticalModel("statistical", config, self.storage_manager)
        except ImportError:
            pass
        
        # Fallback to standard version
        try:
            from anomaly_detection.models.statistical import StatisticalModel
            self.logger.info("Using standard StatisticalModel")
            return StatisticalModel("statistical", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import StatisticalModel: {e}")
            return None
    
    def _create_isolation_forest_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create isolation forest model (improved or standard)."""
        # Try improved version first
        try:
            from improved_isolation_forest_model import ImprovedIsolationForestModel
            self.logger.info("Using ImprovedIsolationForestModel")
            return ImprovedIsolationForestModel("isolation_forest", config, self.storage_manager)
        except ImportError:
            pass
        
        # Fallback to standard version
        try:
            from anomaly_detection.models.isolation_forest import IsolationForestModel
            self.logger.info("Using standard IsolationForestModel")
            return IsolationForestModel("isolation_forest", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import IsolationForestModel: {e}")
            return None
    
    def _create_one_class_svm_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create one-class SVM model."""
        try:
            from anomaly_detection.models.one_class_svm import OneClassSVMModel
            self.logger.info("Using OneClassSVMModel")
            return OneClassSVMModel("one_class_svm", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import OneClassSVMModel: {e}")
            return None
    
    def _create_autoencoder_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create autoencoder model."""
        try:
            from anomaly_detection.models.autoencoder import AutoencoderModel
            self.logger.info("Using AutoencoderModel")
            return AutoencoderModel("autoencoder", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import AutoencoderModel: {e}")
            return None
    
    def _create_gan_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create GAN-based model."""
        try:
            from anomaly_detection.models.ganbased import GANAnomalyDetector
            self.logger.info("Using GANAnomalyDetector")
            return GANAnomalyDetector("gan", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import GANAnomalyDetector: {e}")
            return None
    
    def _create_ensemble_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create ensemble model (must be created LAST)."""
        try:
            from anomaly_detection.models.ensemble import EnsembleModel
            self.logger.info("Using EnsembleModel")
            return EnsembleModel("ensemble", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import EnsembleModel: {e}")
            return None

    def _create_ecod_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create ECOD model."""
        try:
            from anomaly_detection.models.ecod import ECODModel
            self.logger.info("Using ECODModel")
            return ECODModel("ecod", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import ECODModel: {e}")
            return None

    def _create_extended_iforest_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create Extended Isolation Forest model."""
        try:
            from anomaly_detection.models.extended_iforest import ExtendedIsolationForestModel
            self.logger.info("Using ExtendedIsolationForestModel")
            return ExtendedIsolationForestModel("extended_iforest", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import ExtendedIsolationForestModel: {e}")
            return None

    def _create_deep_iforest_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create Deep Isolation Forest model (requires deepod>=0.4)."""
        try:
            from anomaly_detection.models.deep_iforest import DeepIsolationForestModel
            self.logger.info("Using DeepIsolationForestModel")
            return DeepIsolationForestModel("deep_iforest", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import DeepIsolationForestModel: {e}")
            return None

    def _create_deep_sad_model(self, config: Dict[str, Any]) -> Optional[AnomalyDetectionModel]:
        """Create Deep SAD model (vendored, requires torch)."""
        try:
            from anomaly_detection.models.deep_sad_model import DeepSADModel
            self.logger.info("Using DeepSADModel")
            return DeepSADModel("deep_sad", config, self.storage_manager)
        except ImportError as e:
            self.logger.error(f"Could not import DeepSADModel: {e}")
            return None
    
    # Helper methods for model management
    
    def get_model_by_name(self, models: List[AnomalyDetectionModel], 
                         name: str) -> Optional[AnomalyDetectionModel]:
        """
        Get a specific model by name from a list of models.
        
        Args:
            models: List of model instances
            name: Name of model to find
            
        Returns:
            Model instance or None if not found
        """
        for model in models:
            if hasattr(model, 'name') and model.name == name:
                return model
        return None
    
    def get_model_names(self, models: List[AnomalyDetectionModel]) -> List[str]:
        """
        Get list of model names from model instances.
        
        Args:
            models: List of model instances
            
        Returns:
            List of model names
        """
        names = []
        for model in models:
            if hasattr(model, 'name'):
                names.append(model.name)
        return names
    
    def models_to_dict(self, models: List[AnomalyDetectionModel]) -> Dict[str, AnomalyDetectionModel]:
        """
        Convert list of models to dictionary for easier access.
        
        Args:
            models: List of model instances
            
        Returns:
            Dictionary mapping model name to model instance
        """
        model_dict = {}
        for model in models:
            if hasattr(model, 'name'):
                model_dict[model.name] = model
        return model_dict
    
    def save_all_models(self, models: List[AnomalyDetectionModel]) -> None:
        """
        Save all models to storage.
        
        Args:
            models: List of model instances to save
        """
        if not self.storage_manager:
            self.logger.warning("No storage manager configured, cannot save models")
            return
        
        saved_count = 0
        for model in models:
            try:
                model.save()
                saved_count += 1
            except Exception as e:
                self.logger.error(f"Error saving model {model.name}: {e}")
        
        self.logger.info(f"Saved {saved_count}/{len(models)} models")
    
    def load_all_models(self, models: List[AnomalyDetectionModel]) -> None:
        """
        Load all models from storage.
        
        Args:
            models: List of model instances to load
        """
        if not self.storage_manager:
            self.logger.warning("No storage manager configured, cannot load models")
            return
        
        loaded_count = 0
        for model in models:
            try:
                if model.load():
                    loaded_count += 1
            except Exception as e:
                self.logger.error(f"Error loading model {model.name}: {e}")
        
        self.logger.info(f"Loaded {loaded_count}/{len(models)} models")