"""
Autoencoder model for anomaly detection.

This module provides an implementation of an autoencoder-based approach
for unsupervised anomaly detection using neural networks.

UPDATES:
- Enhanced NumPy type handling for PyTorch compatibility
- Improved model serialization and state management
- Better error handling and logging
- Comprehensive feature alignment
"""

import logging
import pickle
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch not installed. AutoencoderModel will not work.")

from anomaly_detection.models.base import AnomalyDetectionModel


class AutoencoderNetwork(nn.Module):
    """
    Neural network architecture for the Autoencoder.
    
    This network learns to compress and reconstruct input data,
    with the reconstruction error serving as an anomaly score.
    """
    
    def __init__(self, input_dim: int, hidden_dims: List[int] = [64, 32, 16]):
        """
        Initialize autoencoder network.
        
        Args:
            input_dim: Dimension of input features
            hidden_dims: List of hidden layer dimensions
        """
        super(AutoencoderNetwork, self).__init__()
        
        # Build encoder
        encoder_layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            encoder_layers.append(nn.Linear(prev_dim, hidden_dim))
            encoder_layers.append(nn.ReLU())
            prev_dim = hidden_dim
        
        self.encoder = nn.Sequential(*encoder_layers)
        
        # Build decoder (reverse of encoder)
        decoder_layers = []
        for hidden_dim in reversed(hidden_dims[:-1]):
            decoder_layers.append(nn.Linear(prev_dim, hidden_dim))
            decoder_layers.append(nn.ReLU())
            prev_dim = hidden_dim
        
        # Final layer to reconstruct input
        decoder_layers.append(nn.Linear(prev_dim, input_dim))
        
        self.decoder = nn.Sequential(*decoder_layers)
    
    def forward(self, x):
        """Forward pass through the autoencoder."""
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


class AutoencoderModel(AnomalyDetectionModel):
    """
    Anomaly detection model using an autoencoder approach.
    
    The autoencoder learns to compress and reconstruct normal data.
    Anomalies are detected when reconstruction error is high.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize Autoencoder model with configuration.
        
        Args:
            name: Model name
            config: Model configuration
        """
        super().__init__(name, config)
        
        if not TORCH_AVAILABLE:
            self.logger.error("PyTorch not installed. AutoencoderModel will not work.")
            return
        
        # Model hyperparameters - ensure Python types
        self.hidden_dims = config.get("hidden_dims", [64, 32, 16])
        self.learning_rate = float(config.get("learning_rate", 0.001))
        self.epochs = int(config.get("epochs", 50))
        self.batch_size = int(config.get("batch_size", 32))
        
        # Feature selection
        self.feature_prefix = config.get("feature_prefix", None)
        
        # Convert threshold to Python float (from parent class)
        self.threshold = float(self.threshold)
        
        # Device configuration
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Model will be initialized during training
        self.model = None
        self.input_dim = None
        
        # Store training features
        self.training_feature_names = None
        
        # Track training statistics
        self.training_loss_history = []
        
        self.logger.info(f"Initialized Autoencoder model '{self.name}' with hidden dims: {self.hidden_dims}")
        self.logger.info(f"Using device: {self.device}")
    
    
    def _safe_scalar_conversion(self, feature_value, feature_name=""):
        """Convert any value to scalar float, handling arrays/lists/etc."""
        if feature_value is None:
            return 0.0
        if isinstance(feature_value, (int, float, bool, np.integer, np.floating, np.bool_)):
            return float(feature_value)
        if isinstance(feature_value, (list, tuple, np.ndarray)):
            if len(feature_value) == 0:
                return 0.0
            elif len(feature_value) == 1:
                return self._safe_scalar_conversion(feature_value[0], feature_name)
            try:
                nums = [float(x) for x in feature_value if isinstance(x, (int, float, bool, np.number))]
                return float(np.mean(nums)) if len(nums) == len(feature_value) and nums else float(len(feature_value))
            except:
                return float(len(feature_value))
        if isinstance(feature_value, str):
            return float(abs(hash(feature_value)) % 10000)
        if isinstance(feature_value, dict):
            return float(len(feature_value))
        try:
            return float(feature_value)
        except:
            return 0.0
    def train(self, data: List[Dict[str, Any]]) -> None:
        """
        Train the Autoencoder model on the provided data.
        
        Args:
            data: List of data items with features
        """
        if not TORCH_AVAILABLE:
            self.logger.error("PyTorch not installed. Cannot train model.")
            return
        
        # Extract feature vectors
        feature_matrix, feature_names = self._extract_features(data)
        
        if feature_matrix.shape[0] == 0:
            self.logger.error("No features found in training data.")
            return
        
        # Store feature names for later use in detection
        self.training_feature_names = feature_names
        self.input_dim = feature_matrix.shape[1]
        
        self.logger.info(f"Training Autoencoder model '{self.name}' on {feature_matrix.shape[0]} "
                       f"samples with {feature_matrix.shape[1]} features")
        
        # Initialize the model
        self.model = AutoencoderNetwork(self.input_dim, self.hidden_dims).to(self.device)
        
        # Convert to torch tensor - ensure proper dtype
        X_train = torch.FloatTensor(feature_matrix).to(self.device)
        
        # Create data loader
        dataset = TensorDataset(X_train)
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        # Define loss function and optimizer
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)
        
        # Training loop
        self.model.train()
        self.training_loss_history = []
        
        for epoch in range(self.epochs):
            epoch_loss = 0.0
            batch_count = 0
            
            for batch in dataloader:
                batch_data = batch[0]
                
                # Forward pass
                reconstructed = self.model(batch_data)
                loss = criterion(reconstructed, batch_data)
                
                # Backward pass
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                # Track loss - convert to Python float
                epoch_loss += float(loss.item())
                batch_count += 1
            
            avg_loss = epoch_loss / batch_count if batch_count > 0 else 0.0
            self.training_loss_history.append(float(avg_loss))
            
            if (epoch + 1) % 10 == 0:
                self.logger.info(f"Epoch [{epoch + 1}/{self.epochs}], Loss: {avg_loss:.6f}")
        
        # Save model state
        try:
            self.model_state = {
                "model_state_dict": self.model.state_dict(),
                "feature_names": feature_names,
                "input_dim": int(self.input_dim),
                "hidden_dims": self.hidden_dims,
                "training_loss_history": self.training_loss_history,
                "trained": True
            }
            self.logger.info(f"Model '{self.name}' training completed. Final loss: {self.training_loss_history[-1]:.6f}")
        except Exception as e:
            self.logger.error(f"Error saving model state: {str(e)}")
    
    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in the provided data using the Autoencoder model.
        
        Args:
            data: List of data items with features
            
        Returns:
            List of anomaly objects
        """
        if not TORCH_AVAILABLE:
            self.logger.error("PyTorch not installed. Cannot detect anomalies.")
            return []
        
        # Load model if necessary
        if self.model is None and "model_state_dict" in self.model_state:
            try:
                # Restore model architecture
                if "feature_names" in self.model_state:
                    self.training_feature_names = self.model_state["feature_names"]
                if "input_dim" in self.model_state:
                    self.input_dim = int(self.model_state["input_dim"])
                if "hidden_dims" in self.model_state:
                    self.hidden_dims = self.model_state["hidden_dims"]
                
                # Recreate model
                self.model = AutoencoderNetwork(self.input_dim, self.hidden_dims).to(self.device)
                
                # Load state dict
                self.model.load_state_dict(self.model_state["model_state_dict"])
                self.logger.info(f"Loaded model '{self.name}' from saved state")
            except Exception as e:
                self.logger.error(f"Error loading model from state: {str(e)}")
                return []
        
        if self.model is None:
            self.logger.error(f"No trained model available for '{self.name}'. Cannot detect anomalies.")
            return []
        
        # Extract feature vectors - now with feature alignment
        feature_matrix, _ = self._extract_features_aligned(data, self.training_feature_names)
        
        if feature_matrix.shape[0] == 0:
            self.logger.error("No features found in detection data.")
            return []
        
        self.logger.info(f"Detecting anomalies in {feature_matrix.shape[0]} samples")
        
        # Convert to torch tensor
        X_test = torch.FloatTensor(feature_matrix).to(self.device)
        
        # Get reconstruction errors
        self.model.eval()
        with torch.no_grad():
            reconstructed = self.model(X_test)
            # Calculate reconstruction error (MSE per sample)
            reconstruction_errors = torch.mean((X_test - reconstructed) ** 2, dim=1)
            # Convert to numpy and then to Python floats
            errors = reconstruction_errors.cpu().numpy()
        
        # Normalize errors to [0, 1] range for scoring
        if len(errors) > 1:
            max_error = float(np.max(errors))
            min_error = float(np.min(errors))
            if max_error > min_error:
                normalized_scores = (errors - min_error) / (max_error - min_error)
            else:
                normalized_scores = np.zeros_like(errors)
        else:
            normalized_scores = np.array([float(errors[0])])
        
        # Detect anomalies
        anomalies = []
        
        for i, (item, error, score) in enumerate(zip(data, errors, normalized_scores)):
            # Ensure Python float types
            error_val = float(error)
            score_val = float(score)
            
            # If score exceeds threshold, it's an anomaly
            if score_val >= self.threshold:
                details = {
                    "score": float(score_val),
                    "reconstruction_error": float(error_val),
                    "feature_count": int(feature_matrix.shape[1]),
                    "model_type": "autoencoder"
                }
                
                # Pass Python float for score
                anomaly = self.create_anomaly(item, float(score_val), details)
                anomalies.append(anomaly)
        
        self.logger.info(f"Model '{self.name}' detected {len(anomalies)} anomalies")
        return anomalies
    
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
        feature_matrix = np.zeros((n_samples, n_features), dtype=np.float32)
        
        # Fill feature matrix - ensure float32 for PyTorch
        for i, item in enumerate(data):
            if "features" in item and isinstance(item["features"], dict):
                for j, feature_name in enumerate(feature_names):
                    # Convert to Python float
                    feature_value = item["features"].get(feature_name, 0.0)
                    feature_matrix[i, j] = self._safe_scalar_conversion(feature_value, feature_name)
        
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
        feature_matrix = np.zeros((n_samples, n_features), dtype=np.float32)
        
        # Fill feature matrix - ensuring all values are Python floats
        for i, item in enumerate(data):
            if "features" in item and isinstance(item["features"], dict):
                for j, feature_name in enumerate(feature_names):
                    # Get feature value with default of 0.0 for missing features
                    feature_value = item["features"].get(feature_name, 0.0)
                    # Ensure it's a Python float
                    feature_matrix[i, j] = self._safe_scalar_conversion(feature_value, feature_name)
        
        return feature_matrix, feature_names
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get the current state of the model for serialization.
        
        Returns:
            Dictionary with model state
        """
        state = super().get_state()
        
        # Add autoencoder-specific state
        state["hidden_dims"] = self.hidden_dims
        state["learning_rate"] = float(self.learning_rate)
        state["epochs"] = int(self.epochs)
        state["batch_size"] = int(self.batch_size)
        state["input_dim"] = int(self.input_dim) if self.input_dim else None
        state["training_loss_history"] = [float(x) for x in self.training_loss_history]
        
        return state
    
    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Set the model state from serialized state.
        
        Args:
            state: Dictionary with model state
        """
        super().set_state(state)
        
        if "model_state_dict" in self.model_state and TORCH_AVAILABLE:
            try:
                # Restore model parameters
                if "feature_names" in self.model_state:
                    self.training_feature_names = self.model_state["feature_names"]
                if "input_dim" in self.model_state:
                    self.input_dim = int(self.model_state["input_dim"])
                if "hidden_dims" in self.model_state:
                    self.hidden_dims = self.model_state["hidden_dims"]
                if "training_loss_history" in self.model_state:
                    self.training_loss_history = self.model_state["training_loss_history"]
                
                # Recreate model
                self.model = AutoencoderNetwork(self.input_dim, self.hidden_dims).to(self.device)
                
                # Load state dict
                self.model.load_state_dict(self.model_state["model_state_dict"])
                self.model.eval()
                
                self.logger.info(f"Loaded autoencoder model '{self.name}' from saved state")
            except Exception as e:
                self.logger.error(f"Error loading model from state: {str(e)}")