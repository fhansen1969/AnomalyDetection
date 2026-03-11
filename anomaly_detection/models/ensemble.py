"""
Ensemble model for anomaly detection - FIXED VERSION

CRITICAL FIXES:
1. Fixed initialization to properly receive and store model references
2. Added set_models() method to inject model instances after creation
3. Improved error handling when models are not available
4. Better validation and logging
"""

import logging
import pickle
import numpy as np
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from anomaly_detection.models.base import AnomalyDetectionModel


class EnsembleModel(AnomalyDetectionModel):
    """
    FIXED: Anomaly detection model using an ensemble approach.
    
    This model combines the results of multiple anomaly detection models
    to provide more robust anomaly detection.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize Ensemble model with configuration.
        
        Args:
            name: Model name
            config: Model configuration
        """
        super().__init__(name, config)
        
        # Weights for each model
        weights_list = config.get("weights", [])
        self.models_to_use = config.get("models_to_use", [])
        
        # Convert weights list to dictionary if needed
        if isinstance(weights_list, list) and isinstance(self.models_to_use, list):
            self.weights = {}
            for i, model in enumerate(self.models_to_use):
                if i < len(weights_list):
                    self.weights[model] = float(weights_list[i])
                else:
                    self.weights[model] = 0.5  # Default weight
        else:
            self.weights = config.get("weights", {})
        
        # Ensure all weights are Python floats
        self.weights = {k: float(v) for k, v in self.weights.items()}
        
        # Default weight if not specified
        self.default_weight = float(config.get("default_weight", 0.5))
        
        # Threshold for combined score
        self.threshold = float(config.get("threshold", 0.7))
        
        # FIXED: Store model instances dictionary
        self._model_instances = {}
        
        # Track model availability
        self.available_models = set()
        
        self.logger.info(f"Initialized Ensemble model '{self.name}' with weights: {self.weights}")
        self.logger.info(f"Target models: {self.models_to_use}")
    
    def set_models(self, models: Dict[str, AnomalyDetectionModel]) -> None:
        """
        FIXED: Set the model instances that this ensemble will use.
        
        This should be called after creating the ensemble model to inject
        the actual model instances.
        
        Args:
            models: Dictionary mapping model name to model instance
        """
        self._model_instances = models
        self.available_models = set(models.keys())
        
        # Validate that target models exist
        missing_models = set(self.models_to_use) - self.available_models
        if missing_models:
            self.logger.warning(f"Missing configured models: {missing_models}")
            self.logger.info(f"Available models: {self.available_models}")
        else:
            self.logger.info(f"All {len(self.models_to_use)} target models available")
    
    def train(self, data: List[Dict[str, Any]]) -> None:
        """
        Train the Ensemble model on the provided data.
        
        The Ensemble model doesn't require training itself, as it relies
        on the results of other models.
        
        Args:
            data: List of data items with features
        """
        self.logger.info(f"Ensemble model '{self.name}' doesn't require training")
        
        # Mark as trained
        self.model_state["trained"] = True
        self.model_state["timestamp"] = datetime.utcnow().isoformat()
        self.is_trained = True

        return

    def detect(self, data: List[Dict[str, Any]], models: Dict[str, AnomalyDetectionModel] = None) -> List[Dict[str, Any]]:
        """
        FIXED: Detect anomalies in the provided data using the Ensemble model.
        
        This implementation runs detection across all configured models
        and combines their results automatically.
        
        Args:
            data: List of data items with features
            models: Dictionary of model name to model instance (optional, uses stored models if not provided)
                
        Returns:
            List of anomaly objects with weighted and combined scores
        """
        # FIXED: Use provided models or fall back to stored model instances
        if models is not None:
            self._model_instances = models
            self.available_models = set(models.keys())
        elif not self._model_instances:
            self.logger.error("No models available for ensemble detection. Call set_models() first or pass models parameter.")
            return []
        
        active_models = self._model_instances
        
        self.logger.info(f"Ensemble model '{self.name}' starting detection across {len(self.models_to_use)} configured models")
        self.logger.debug(f"Available models: {self.available_models}")
        
        # Validate that required models are available
        missing_models = set(self.models_to_use) - self.available_models
        if missing_models:
            self.logger.warning(f"Missing configured models: {missing_models}")
        
        # If no models to use, return empty
        if not self.models_to_use:
            self.logger.error("No models configured in models_to_use list")
            return []
        
        # Track all anomalies from all models
        all_anomalies = []
        model_results = {}
        successful_models = []
        failed_models = []
        
        # Run detection for each model
        for model_name in self.models_to_use:
            try:
                # Check if model exists in available models
                if model_name not in active_models:
                    self.logger.warning(f"Model '{model_name}' not found in available models, skipping")
                    failed_models.append(model_name)
                    continue
                    
                # Get model instance
                model = active_models[model_name]
                
                # Validate model has a proper name
                if not hasattr(model, 'name') or not model.name:
                    self.logger.error(f"Model at key '{model_name}' has invalid name attribute")
                    failed_models.append(model_name)
                    continue
                    
                # Run detection
                self.logger.debug(f"Running detection with model: {model.name}")
                results = model.detect(data)
                
                # Validate results
                if not isinstance(results, list):
                    self.logger.error(f"Model '{model_name}' returned invalid results (not a list)")
                    failed_models.append(model_name)
                    continue
                
                model_results[model_name] = results
                successful_models.append(model_name)
                
                # Add source model tracking to each anomaly
                for anomaly in results:
                    # Ensure anomaly is a dictionary
                    if not isinstance(anomaly, dict):
                        self.logger.warning(f"Model '{model_name}' returned non-dict anomaly, skipping")
                        continue
                    
                    # Track source model
                    anomaly["source_model"] = model_name
                    
                    # Ensure model field is set correctly
                    if "model" not in anomaly or not anomaly["model"]:
                        anomaly["model"] = model_name
                    
                    # Validate score is present and valid
                    if "score" not in anomaly:
                        self.logger.warning(f"Anomaly from '{model_name}' missing score, setting to 0.0")
                        anomaly["score"] = 0.0
                    else:
                        try:
                            anomaly["score"] = float(anomaly["score"])
                        except (ValueError, TypeError):
                            self.logger.warning(f"Invalid score in anomaly from '{model_name}', setting to 0.0")
                            anomaly["score"] = 0.0
                
                # Add to combined results
                all_anomalies.extend(results)
                
            except Exception as e:
                self.logger.error(f"Error running model '{model_name}': {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                failed_models.append(model_name)
        
        # Log detection statistics
        self.logger.info(f"Ensemble detection completed:")
        self.logger.info(f"  - Successful models: {len(successful_models)}/{len(self.models_to_use)}")
        self.logger.info(f"  - Failed models: {len(failed_models)}")
        
        for model_name, results in model_results.items():
            self.logger.info(f"  - Model '{model_name}': {len(results)} anomalies detected")
        
        # Apply ensemble combination logic
        if not all_anomalies:
            self.logger.info("No anomalies detected by any model")
            return []
        
        # Log pre-combination statistics
        self.logger.info(f"Total anomalies before combination: {len(all_anomalies)}")
        
        # Combine results
        combined_anomalies = self._combine_results(all_anomalies)
        
        self.logger.info(f"Final ensemble result: {len(combined_anomalies)} combined anomalies")
        
        return combined_anomalies
    
    def _combine_results(self, anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Combine anomaly results from multiple models using weighted averaging.
        
        This method groups anomalies by their original data item and computes
        weighted average scores across all models that detected each anomaly.
        
        Args:
            anomalies: List of anomaly objects from various models
            
        Returns:
            List of combined anomaly objects
        """
        self.logger.info(f"Combining results from {len(anomalies)} anomalies")
        
        # Group anomalies by their original data item
        grouped_anomalies = {}
        
        for anomaly in anomalies:
            # Validate anomaly structure
            if not isinstance(anomaly, dict):
                self.logger.warning("Skipping non-dict anomaly in combine_results")
                continue
            
            # Create a key from the original data item
            original_data = anomaly.get("original_data") or anomaly.get("data", {})
            
            # Generate grouping key
            key = self._generate_grouping_key(original_data, anomaly)
            
            if key not in grouped_anomalies:
                grouped_anomalies[key] = []
            
            grouped_anomalies[key].append(anomaly)
        
        self.logger.debug(f"Grouped {len(anomalies)} anomalies into {len(grouped_anomalies)} groups")
        
        # Process each group to create a combined anomaly
        combined_anomalies = []
        
        for key, group in grouped_anomalies.items():
            try:
                combined_anomaly = self._combine_group(group)
                if combined_anomaly:
                    combined_anomalies.append(combined_anomaly)
            except Exception as e:
                self.logger.error(f"Error combining group with key {key}: {str(e)}")
        
        self.logger.info(f"Generated {len(combined_anomalies)} combined anomalies")
        return combined_anomalies
    
    def _generate_grouping_key(self, original_data: Dict[str, Any], anomaly: Dict[str, Any]) -> tuple:
        """Generate a grouping key for anomaly deduplication."""
        # Try to use source information
        source_info = None
        if isinstance(original_data, dict):
            if "_source" in original_data:
                source_info = str(original_data["_source"])
            elif "source" in original_data:
                source_info = str(original_data["source"])
        
        # Try to use timestamp
        timestamp = None
        if isinstance(original_data, dict) and "timestamp" in original_data:
            timestamp = original_data["timestamp"]
        elif "timestamp" in anomaly:
            timestamp = anomaly["timestamp"]
        
        # Try to use ID
        item_id = None
        if isinstance(original_data, dict) and "id" in original_data:
            item_id = original_data["id"]
        
        # Create key with available information
        key = (source_info, timestamp, item_id)
        
        return key
    
    def _combine_group(self, group: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Combine a group of anomalies into a single anomaly."""
        if not group:
            return None
        
        # Calculate weighted average score
        total_weight = 0.0
        weighted_score = 0.0
        individual_scores = []
        
        for anomaly in group:
            # Get model name - with fallback
            model_name = anomaly.get("source_model") or anomaly.get("model", "unknown")
            
            # Ensure score is a valid float
            try:
                score = float(anomaly.get("score", 0.0))
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid score in anomaly, using 0.0")
                score = 0.0
            
            # Get weight for this model
            weight = float(self.weights.get(model_name, self.default_weight))
            
            # Accumulate weighted score
            weighted_score += score * weight
            total_weight += weight
            
            # Track individual scores for details
            individual_scores.append({
                "model": model_name,
                "score": float(score),
                "weight": float(weight)
            })
        
        # Calculate combined score
        if total_weight > 0:
            combined_score = float(weighted_score / total_weight)
        else:
            self.logger.warning("Total weight is zero, using average score")
            combined_score = float(np.mean([float(a.get("score", 0.0)) for a in group]))
        
        # Only include if combined score is above threshold
        if combined_score < self.threshold:
            self.logger.debug(f"Combined score {combined_score} below threshold {self.threshold}, excluding")
            return None
        
        # Use the first anomaly as a template
        template = group[0]
        
        # Get original data
        original_data = template.get("original_data") or template.get("data", {})
        
        # Create combined anomaly details
        details = {
            "combined_score": float(combined_score),
            "individual_scores": individual_scores,
            "model_count": int(len(group)),
            "models_used": [a.get("source_model") or a.get("model", "unknown") for a in group],
            "ensemble_name": self.name
        }
        
        # Create the combined anomaly using the base class method
        combined_anomaly = self.create_anomaly(
            original_data,
            float(combined_score),
            details
        )
        
        # Add ensemble-specific fields
        combined_anomaly["is_ensemble"] = True
        combined_anomaly["ensemble_model"] = self.name
        
        return combined_anomaly
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get the current state of the ensemble model.
        
        CRITICAL FIX: Ensure all configuration is saved.
        """
        state = super().get_state()
        
        # Add ensemble-specific state - ensure all fields are saved
        state["weights"] = self.weights
        state["models_to_use"] = self.models_to_use
        state["default_weight"] = float(self.default_weight)
        state["available_models"] = list(self.available_models)
        
        # Also save in the 'state' subdict for compatibility
        state["state"]["weights"] = self.weights
        state["state"]["models_to_use"] = self.models_to_use
        state["state"]["default_weight"] = float(self.default_weight)
        state["state"]["available_models"] = list(self.available_models)
        
        self.logger.debug(f"Saving ensemble state with {len(self.weights)} weights and {len(self.models_to_use)} target models")
        
        return state
    
    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Set the ensemble model state from serialized state.
        
        CRITICAL FIX: Properly restore configuration even if state structure varies.
        """
        super().set_state(state)
        
        # CRITICAL FIX: Check both model_state AND the state parameter directly
        # Some saved states have fields at root level, others in 'state' subdict
        state_data = self.model_state if self.model_state else state
        
        # Restore ensemble-specific state with fallback to config
        if "weights" in state_data:
            self.weights = {k: float(v) for k, v in state_data["weights"].items()}
            self.logger.info(f"Restored weights from state: {self.weights}")
        elif not self.weights:
            # Fallback to config if no saved weights
            self.logger.warning(f"No weights in saved state, using config defaults")
            self.weights = self.config.get("weights", {})
        
        if "models_to_use" in state_data:
            self.models_to_use = state_data["models_to_use"]
            self.logger.info(f"Restored models_to_use from state: {self.models_to_use}")
        elif not self.models_to_use:
            # Fallback to config if no saved models
            self.logger.warning(f"No models_to_use in saved state, using config defaults")
            self.models_to_use = self.config.get("models_to_use", [])
        
        if "default_weight" in state_data:
            self.default_weight = float(state_data["default_weight"])
        elif not hasattr(self, 'default_weight') or not self.default_weight:
            self.default_weight = float(self.config.get("default_weight", 0.5))
        
        if "available_models" in state_data:
            self.available_models = set(state_data["available_models"])
        
        # Validate restored state
        if not self.weights or not self.models_to_use:
            self.logger.error(f"CRITICAL: Ensemble model loaded with empty configuration!")
            self.logger.error(f"  weights: {self.weights}")
            self.logger.error(f"  models_to_use: {self.models_to_use}")
            self.logger.info(f"  Attempting recovery from config...")
            
            # Emergency recovery from config
            if not self.weights:
                self.weights = self.config.get("weights", {})
            if not self.models_to_use:
                self.models_to_use = self.config.get("models_to_use", [])
            
            self.logger.info(f"  Recovered weights: {self.weights}")
            self.logger.info(f"  Recovered models_to_use: {self.models_to_use}")
        
        self.logger.info(f"Restored ensemble model state for '{self.name}' "
                        f"with {len(self.weights)} weights and {len(self.models_to_use)} target models")