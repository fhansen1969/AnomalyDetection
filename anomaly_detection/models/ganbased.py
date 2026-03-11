"""
GAN-based model for anomaly detection.

This module provides an implementation of a GAN-based approach for
unsupervised anomaly detection using generative adversarial networks.

UPDATES:
- Enhanced model architecture and training stability
- Improved NumPy type handling and PyTorch compatibility
- Better model state serialization
- Comprehensive error handling and logging
- Feature alignment for inference
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
    logging.warning("PyTorch not installed. GANAnomalyDetector will not work.")

from anomaly_detection.models.base import AnomalyDetectionModel


class Generator(nn.Module):
    """Generator network for GAN-based anomaly detection."""
    
    def __init__(self, latent_dim: int, output_dim: int, hidden_dims: List[int] = [128, 256]):
        """
        Initialize generator network.
        
        Args:
            latent_dim: Dimension of latent space
            output_dim: Dimension of output (should match input data)
            hidden_dims: List of hidden layer dimensions
        """
        super(Generator, self).__init__()
        
        layers = []
        prev_dim = latent_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.LeakyReLU(0.2))
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, output_dim))
        layers.append(nn.Tanh())
        
        self.model = nn.Sequential(*layers)
    
    def forward(self, z):
        """Forward pass through generator."""
        return self.model(z)


class Discriminator(nn.Module):
    """Discriminator network for GAN-based anomaly detection."""
    
    def __init__(self, input_dim: int, hidden_dims: List[int] = [256, 128]):
        """
        Initialize discriminator network.
        
        Args:
            input_dim: Dimension of input data
            hidden_dims: List of hidden layer dimensions
        """
        super(Discriminator, self).__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.LeakyReLU(0.2))
            layers.append(nn.Dropout(0.3))
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, 1))
        layers.append(nn.Sigmoid())
        
        self.model = nn.Sequential(*layers)
    
    def forward(self, x):
        """Forward pass through discriminator."""
        return self.model(x)


class GANAnomalyDetector(AnomalyDetectionModel):
    """
    Anomaly detection model using a GAN-based approach.
    
    This model trains a GAN on normal data. The discriminator learns to
    distinguish real data from generated data. Anomalies are detected
    when the discriminator identifies samples as "fake" or when the
    generator cannot accurately reconstruct the sample.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize GAN-based anomaly detector with configuration.
        
        Args:
            name: Model name
            config: Model configuration
        """
        super().__init__(name, config)
        
        if not TORCH_AVAILABLE:
            self.logger.error("PyTorch not installed. GANAnomalyDetector will not work.")
            return
        
        # Model hyperparameters - ensure Python types
        self.latent_dim = int(config.get("latent_dim", 32))
        self.generator_hidden_dims = config.get("generator_hidden_dims", [128, 256])
        self.discriminator_hidden_dims = config.get("discriminator_hidden_dims", [256, 128])
        self.learning_rate = float(config.get("learning_rate", 0.0002))
        self.beta1 = float(config.get("beta1", 0.5))  # Adam optimizer parameter
        self.epochs = int(config.get("epochs", 100))
        self.batch_size = int(config.get("batch_size", 64))
        
        # Feature selection
        self.feature_prefix = config.get("feature_prefix", None)
        
        # Convert threshold to Python float (from parent class)
        self.threshold = float(self.threshold)
        
        # Device configuration
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Models will be initialized during training
        self.generator = None
        self.discriminator = None
        self.input_dim = None
        
        # Store training features
        self.training_feature_names = None
        
        # Track training statistics
        self.training_history = {
            "d_loss": [],
            "g_loss": [],
            "d_real_acc": [],
            "d_fake_acc": []
        }
        
        self.logger.info(f"Initialized GAN-based anomaly detector '{self.name}'")
        self.logger.info(f"  Latent dim: {self.latent_dim}")
        self.logger.info(f"  Generator hidden dims: {self.generator_hidden_dims}")
        self.logger.info(f"  Discriminator hidden dims: {self.discriminator_hidden_dims}")
        self.logger.info(f"  Using device: {self.device}")
    
    
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
        Train the GAN-based anomaly detector on the provided data.
        
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
        
        self.logger.info(f"Training GAN model '{self.name}' on {feature_matrix.shape[0]} "
                       f"samples with {feature_matrix.shape[1]} features")
        
        # Normalize data to [-1, 1] for tanh activation
        self.data_mean = np.mean(feature_matrix, axis=0)
        self.data_std = np.std(feature_matrix, axis=0) + 1e-8
        feature_matrix = (feature_matrix - self.data_mean) / self.data_std
        feature_matrix = np.clip(feature_matrix, -3, 3)  # Clip outliers
        
        # Initialize the models
        self.generator = Generator(
            self.latent_dim, 
            self.input_dim, 
            self.generator_hidden_dims
        ).to(self.device)
        
        self.discriminator = Discriminator(
            self.input_dim,
            self.discriminator_hidden_dims
        ).to(self.device)
        
        # Convert to torch tensor
        X_train = torch.FloatTensor(feature_matrix).to(self.device)
        
        # Create data loader
        dataset = TensorDataset(X_train)
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        # Define loss function and optimizers
        criterion = nn.BCELoss()
        optimizer_G = optim.Adam(self.generator.parameters(), lr=self.learning_rate, betas=(self.beta1, 0.999))
        optimizer_D = optim.Adam(self.discriminator.parameters(), lr=self.learning_rate, betas=(self.beta1, 0.999))
        
        # Training loop
        for epoch in range(self.epochs):
            d_losses = []
            g_losses = []
            d_real_accs = []
            d_fake_accs = []
            
            for batch in dataloader:
                batch_size = batch[0].size(0)
                real_data = batch[0]
                
                # ============ Train Discriminator ============
                optimizer_D.zero_grad()
                
                # Real data
                real_labels = torch.ones(batch_size, 1).to(self.device)
                real_output = self.discriminator(real_data)
                d_real_loss = criterion(real_output, real_labels)
                
                # Fake data
                z = torch.randn(batch_size, self.latent_dim).to(self.device)
                fake_data = self.generator(z).detach()
                fake_labels = torch.zeros(batch_size, 1).to(self.device)
                fake_output = self.discriminator(fake_data)
                d_fake_loss = criterion(fake_output, fake_labels)
                
                # Combined loss
                d_loss = d_real_loss + d_fake_loss
                d_loss.backward()
                optimizer_D.step()
                
                # ============ Train Generator ============
                optimizer_G.zero_grad()
                
                z = torch.randn(batch_size, self.latent_dim).to(self.device)
                fake_data = self.generator(z)
                fake_output = self.discriminator(fake_data)
                g_loss = criterion(fake_output, real_labels)  # Generator wants discriminator to think it's real
                
                g_loss.backward()
                optimizer_G.step()
                
                # Track metrics - convert to Python floats
                d_losses.append(float(d_loss.item()))
                g_losses.append(float(g_loss.item()))
                d_real_accs.append(float((real_output > 0.5).float().mean().item()))
                d_fake_accs.append(float((fake_output < 0.5).float().mean().item()))
            
            # Average metrics for epoch
            avg_d_loss = float(np.mean(d_losses))
            avg_g_loss = float(np.mean(g_losses))
            avg_d_real_acc = float(np.mean(d_real_accs))
            avg_d_fake_acc = float(np.mean(d_fake_accs))
            
            self.training_history["d_loss"].append(avg_d_loss)
            self.training_history["g_loss"].append(avg_g_loss)
            self.training_history["d_real_acc"].append(avg_d_real_acc)
            self.training_history["d_fake_acc"].append(avg_d_fake_acc)
            
            if (epoch + 1) % 10 == 0:
                self.logger.info(
                    f"Epoch [{epoch + 1}/{self.epochs}] "
                    f"D_loss: {avg_d_loss:.4f} G_loss: {avg_g_loss:.4f} "
                    f"D_real_acc: {avg_d_real_acc:.3f} D_fake_acc: {avg_d_fake_acc:.3f}"
                )
        
        # Save model state
        try:
            self.model_state = {
                "generator_state_dict": self.generator.state_dict(),
                "discriminator_state_dict": self.discriminator.state_dict(),
                "feature_names": feature_names,
                "input_dim": int(self.input_dim),
                "latent_dim": int(self.latent_dim),
                "data_mean": self.data_mean.tolist(),
                "data_std": self.data_std.tolist(),
                "training_history": self.training_history,
                "trained": True
            }
            self.is_trained = True
            self.logger.info(f"Model '{self.name}' training completed")
        except Exception as e:
            self.logger.error(f"Error saving model state: {str(e)}")
    
    def detect(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in the provided data using the GAN model.
        
        Args:
            data: List of data items with features
            
        Returns:
            List of anomaly objects
        """
        if not TORCH_AVAILABLE:
            self.logger.error("PyTorch not installed. Cannot detect anomalies.")
            return []
        
        # Load model if necessary
        if self.discriminator is None and "discriminator_state_dict" in self.model_state:
            try:
                # Restore model parameters
                if "feature_names" in self.model_state:
                    self.training_feature_names = self.model_state["feature_names"]
                if "input_dim" in self.model_state:
                    self.input_dim = int(self.model_state["input_dim"])
                if "latent_dim" in self.model_state:
                    self.latent_dim = int(self.model_state["latent_dim"])
                if "data_mean" in self.model_state:
                    self.data_mean = np.array(self.model_state["data_mean"])
                if "data_std" in self.model_state:
                    self.data_std = np.array(self.model_state["data_std"])
                
                # Recreate models
                self.generator = Generator(
                    self.latent_dim,
                    self.input_dim,
                    self.generator_hidden_dims
                ).to(self.device)
                
                self.discriminator = Discriminator(
                    self.input_dim,
                    self.discriminator_hidden_dims
                ).to(self.device)
                
                # Load state dicts
                self.generator.load_state_dict(self.model_state["generator_state_dict"])
                self.discriminator.load_state_dict(self.model_state["discriminator_state_dict"])
                
                self.generator.eval()
                self.discriminator.eval()
                
                self.logger.info(f"Loaded model '{self.name}' from saved state")
            except Exception as e:
                self.logger.error(f"Error loading model from state: {str(e)}")
                return []
        
        if self.discriminator is None:
            self.logger.error(f"No trained model available for '{self.name}'. Cannot detect anomalies.")
            return []
        
        # Extract feature vectors - now with feature alignment
        feature_matrix, _ = self._extract_features_aligned(data, self.training_feature_names)
        
        if feature_matrix.shape[0] == 0:
            self.logger.error("No features found in detection data.")
            return []
        
        self.logger.info(f"Detecting anomalies in {feature_matrix.shape[0]} samples")
        
        # Normalize data using training statistics
        feature_matrix = (feature_matrix - self.data_mean) / self.data_std
        feature_matrix = np.clip(feature_matrix, -3, 3)
        
        # Convert to torch tensor
        X_test = torch.FloatTensor(feature_matrix).to(self.device)
        
        # Get discriminator scores
        with torch.no_grad():
            discriminator_scores = self.discriminator(X_test)
            # Convert to numpy and then to Python floats
            scores = discriminator_scores.cpu().numpy().flatten()
        
        # Lower discriminator score means more likely to be anomalous
        # (discriminator thinks it's fake/anomalous)
        anomaly_scores = 1.0 - scores
        
        # Detect anomalies
        anomalies = []
        
        for i, (item, score) in enumerate(zip(data, anomaly_scores)):
            # Ensure Python float type
            score_val = float(score)
            
            # If score exceeds threshold, it's an anomaly
            if score_val >= self.threshold:
                details = {
                    "score": float(score_val),
                    "discriminator_score": float(scores[i]),
                    "feature_count": int(feature_matrix.shape[1]),
                    "model_type": "gan"
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
        
        # Add GAN-specific state
        state["latent_dim"] = int(self.latent_dim)
        state["generator_hidden_dims"] = self.generator_hidden_dims
        state["discriminator_hidden_dims"] = self.discriminator_hidden_dims
        state["learning_rate"] = float(self.learning_rate)
        state["beta1"] = float(self.beta1)
        state["epochs"] = int(self.epochs)
        state["batch_size"] = int(self.batch_size)
        state["input_dim"] = int(self.input_dim) if self.input_dim else None
        
        # Convert training history to Python types
        if self.training_history:
            state["training_history"] = {
                k: [float(x) for x in v] for k, v in self.training_history.items()
            }
        
        return state
    
    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Set the model state from serialized state.
        
        Args:
            state: Dictionary with model state
        """
        super().set_state(state)
        
        if "discriminator_state_dict" in self.model_state and TORCH_AVAILABLE:
            try:
                # Restore model parameters
                if "feature_names" in self.model_state:
                    self.training_feature_names = self.model_state["feature_names"]
                if "input_dim" in self.model_state:
                    self.input_dim = int(self.model_state["input_dim"])
                if "latent_dim" in self.model_state:
                    self.latent_dim = int(self.model_state["latent_dim"])
                if "data_mean" in self.model_state:
                    self.data_mean = np.array(self.model_state["data_mean"])
                if "data_std" in self.model_state:
                    self.data_std = np.array(self.model_state["data_std"])
                if "training_history" in self.model_state:
                    self.training_history = self.model_state["training_history"]
                
                # Recreate models
                self.generator = Generator(
                    self.latent_dim,
                    self.input_dim,
                    self.generator_hidden_dims
                ).to(self.device)
                
                self.discriminator = Discriminator(
                    self.input_dim,
                    self.discriminator_hidden_dims
                ).to(self.device)
                
                # Load state dicts
                self.generator.load_state_dict(self.model_state["generator_state_dict"])
                self.discriminator.load_state_dict(self.model_state["discriminator_state_dict"])
                
                self.generator.eval()
                self.discriminator.eval()
                
                self.logger.info(f"Loaded GAN model '{self.name}' from saved state")
            except Exception as e:
                self.logger.error(f"Error loading model from state: {str(e)}")