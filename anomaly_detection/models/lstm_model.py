"""
LSTM Anomaly Detection Model

Uses Long Short-Term Memory networks for time series anomaly detection.
"""

import logging
import numpy as np
from typing import Dict, List, Any, Tuple
import pickle
import os

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, models, optimizers, losses, callbacks
    from sklearn.preprocessing import StandardScaler
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logging.warning("TensorFlow not installed. LSTMModel will not work.")

from anomaly_detection.models.base import ImprovedAnomalyDetectionModel


class LSTMModel(ImprovedAnomalyDetectionModel):
    """
    LSTM-based anomaly detection model for time series data.

    Uses reconstruction error from LSTM autoencoder to detect anomalies.
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """Initialize LSTM model."""
        super().__init__(name, config, storage_manager)

        if not TENSORFLOW_AVAILABLE:
            self.logger.error("TensorFlow not installed")
            return

        # Model architecture
        self.sequence_length = int(config.get("sequence_length", 50))
        self.hidden_dims = config.get("hidden_dims", [64, 32])
        self.latent_dim = int(config.get("latent_dim", 16))
        self.dropout_rate = float(config.get("dropout_rate", 0.2))

        # Training parameters
        self.epochs = int(config.get("epochs", 50))
        self.batch_size = int(config.get("batch_size", 32))
        self.learning_rate = float(config.get("learning_rate", 0.001))
        self.validation_split = float(config.get("validation_split", 0.2))

        # Early stopping
        self.patience = int(config.get("patience", 10))
        self.min_delta = float(config.get("min_delta", 1e-4))

        # Anomaly detection
        self.reconstruction_threshold = float(config.get("reconstruction_threshold", 0.1))
        self.threshold_percentile = float(config.get("threshold_percentile", 95))

        # Feature processing
        self.scaler = StandardScaler()
        self.feature_names = None

        # Model components
        self.encoder = None
        self.decoder = None
        self.autoencoder = None

        # Training history
        self.history = None

        self.logger.info(f"Initialized LSTM model with sequence_length={self.sequence_length}")

    def _get_anomaly_scores(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """
        Get anomaly scores using LSTM reconstruction error.

        Args:
            data: List of data items with features

        Returns:
            Array of anomaly scores (higher = more anomalous)
        """
        if self.autoencoder is None:
            self.logger.error("Model not trained")
            return np.array([])

        # Extract and prepare sequences
        sequences = self._prepare_sequences(data)
        if len(sequences) == 0:
            return np.array([])

        # Get reconstruction errors
        try:
            reconstructed = self.autoencoder.predict(sequences, verbose=0)
            mse = np.mean(np.square(sequences - reconstructed), axis=(1, 2))

            # Normalize scores
            scores = self._normalize_scores(mse)

            return scores

        except Exception as e:
            self.logger.error(f"Error during prediction: {e}")
            return np.array([])

    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train the LSTM autoencoder model."""
        if not TENSORFLOW_AVAILABLE:
            self.logger.error("TensorFlow not installed")
            return

        # Extract and prepare training sequences
        sequences = self._prepare_sequences(data)
        if len(sequences) == 0:
            self.logger.error("No valid sequences for training")
            return

        self.logger.info(f"Training on {len(sequences)} sequences with shape {sequences.shape}")

        # Build model
        self._build_model(sequences.shape[-1])

        # Training callbacks
        early_stopping = callbacks.EarlyStopping(
            monitor='val_loss',
            patience=self.patience,
            min_delta=self.min_delta,
            restore_best_weights=True,
            verbose=0
        )

        reduce_lr = callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=self.patience // 2,
            min_lr=1e-6,
            verbose=0
        )

        # Train model
        self.history = self.autoencoder.fit(
            sequences, sequences,
            epochs=self.epochs,
            batch_size=self.batch_size,
            validation_split=self.validation_split,
            callbacks=[early_stopping, reduce_lr],
            verbose=0
        )

        # Calculate reconstruction threshold
        reconstructed = self.autoencoder.predict(sequences, verbose=0)
        mse_train = np.mean(np.square(sequences - reconstructed), axis=(1, 2))

        self.reconstruction_threshold = np.percentile(mse_train, self.threshold_percentile)

        # Save model state
        self.model_state = {
            "sequence_length": self.sequence_length,
            "feature_names": self.feature_names,
            "scaler_mean": self.scaler.mean_.tolist(),
            "scaler_scale": self.scaler.scale_.tolist(),
            "reconstruction_threshold": self.reconstruction_threshold,
            "training_history": {
                "final_loss": float(self.history.history['loss'][-1]),
                "final_val_loss": float(self.history.history.get('val_loss', [0])[-1]),
                "epochs_trained": len(self.history.history['loss']),
                "stopped_epoch": early_stopping.stopped_epoch or self.epochs
            }
        }

        # Save model weights separately
        if self.storage_manager:
            weights_path = f"{self.name}_weights.h5"
            self.autoencoder.save_weights(weights_path)
            self.model_state["weights_path"] = weights_path

        self.is_trained = True
        self.logger.info(f"Training completed. Reconstruction threshold: {self.reconstruction_threshold:.6f}")

    def _build_model(self, input_dim: int):
        """Build the LSTM autoencoder architecture."""
        # Encoder
        encoder_inputs = layers.Input(shape=(self.sequence_length, input_dim), name='encoder_input')

        # LSTM layers for encoder
        encoder_lstm = encoder_inputs
        for i, hidden_dim in enumerate(self.hidden_dims):
            return_sequences = i < len(self.hidden_dims) - 1  # Return sequences for all but last
            encoder_lstm = layers.LSTM(
                hidden_dim,
                return_sequences=return_sequences,
                dropout=self.dropout_rate,
                recurrent_dropout=self.dropout_rate,
                name=f'encoder_lstm_{i+1}'
            )(encoder_lstm)

        # Latent space
        latent_space = layers.Dense(self.latent_dim, activation='relu', name='latent_space')(encoder_lstm)
        latent_space = layers.Dropout(self.dropout_rate, name='latent_dropout')(latent_space)

        # Decoder
        decoder_dense = layers.Dense(self.hidden_dims[-1], activation='relu', name='decoder_dense')(latent_space)
        decoder_dense = layers.RepeatVector(self.sequence_length, name='repeat_vector')(decoder_dense)

        # LSTM layers for decoder
        decoder_lstm = decoder_dense
        for i, hidden_dim in enumerate(reversed(self.hidden_dims)):
            return_sequences = i < len(self.hidden_dims) - 1
            decoder_lstm = layers.LSTM(
                hidden_dim,
                return_sequences=return_sequences,
                dropout=self.dropout_rate,
                recurrent_dropout=self.dropout_rate,
                name=f'decoder_lstm_{i+1}'
            )(decoder_lstm)

        # Output layer
        decoder_outputs = layers.TimeDistributed(
            layers.Dense(input_dim, activation='linear'),
            name='decoder_output'
        )(decoder_lstm)

        # Create models
        self.autoencoder = models.Model(encoder_inputs, decoder_outputs, name='lstm_autoencoder')
        self.encoder = models.Model(encoder_inputs, latent_space, name='encoder')

        # Compile
        optimizer = optimizers.Adam(learning_rate=self.learning_rate)
        self.autoencoder.compile(optimizer=optimizer, loss='mse', metrics=['mae'])

        self.logger.info(f"Built LSTM autoencoder: {self.hidden_dims} -> {self.latent_dim}")

    def _prepare_sequences(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """Prepare sequential data for LSTM training/prediction."""
        # Extract features
        features_list = []
        timestamps = []

        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                # Get feature values in consistent order
                if self.feature_names is None:
                    self.feature_names = sorted(item["features"].keys())

                feature_values = []
                for name in self.feature_names:
                    value = item["features"].get(name, 0.0)
                    try:
                        feature_values.append(float(value))
                    except (ValueError, TypeError):
                        feature_values.append(0.0)

                features_list.append(feature_values)

                # Get timestamp for sorting
                timestamp = item.get("timestamp", item.get("time", ""))
                timestamps.append(timestamp)

        if not features_list:
            return np.array([])

        # Convert to numpy array
        features_array = np.array(features_list)

        # Fit scaler during training, transform during prediction
        if not self.is_trained:
            features_scaled = self.scaler.fit_transform(features_array)
        else:
            features_scaled = self.scaler.transform(features_array)

        # Create sequences
        sequences = []
        for i in range(len(features_scaled) - self.sequence_length + 1):
            sequence = features_scaled[i:i + self.sequence_length]
            sequences.append(sequence)

        if not sequences:
            return np.array([])

        return np.array(sequences)

    def _normalize_scores(self, reconstruction_errors: np.ndarray) -> np.ndarray:
        """Normalize reconstruction errors to [0, 1] range."""
        if len(reconstruction_errors) == 0:
            return reconstruction_errors

        # Use training threshold for normalization
        if self.reconstruction_threshold > 0:
            scores = reconstruction_errors / self.reconstruction_threshold
        else:
            # Fallback: normalize by max error
            max_error = np.max(reconstruction_errors)
            if max_error > 0:
                scores = reconstruction_errors / max_error
            else:
                scores = reconstruction_errors

        # Clip to [0, 1] range
        scores = np.clip(scores, 0.0, 1.0)

        return scores

    def save(self, path: Optional[str] = None) -> None:
        """Save model to storage."""
        if self.storage_manager and self.model_state:
            # Save model weights separately
            weights_path = f"{self.name}_weights.h5"
            full_weights_path = os.path.join(self.storage_manager.get_storage_path(), weights_path)

            try:
                self.autoencoder.save_weights(full_weights_path)
                self.model_state["weights_path"] = weights_path
            except Exception as e:
                self.logger.error(f"Failed to save model weights: {e}")

            self.storage_manager.save_model(self.name, {
                "name": self.name,
                "type": self.__class__.__name__,
                "state": self.model_state,
                "is_trained": self.is_trained,
                "threshold": self.threshold
            })

            self.logger.info(f"Model '{self.name}' saved to storage")

    def load(self, path: Optional[str] = None) -> bool:
        """Load model from storage."""
        if not self.storage_manager:
            return False

        state = self.storage_manager.load_model(self.name)
        if not state or "state" not in state:
            return False

        model_state = state["state"]

        # Restore parameters
        self.sequence_length = model_state.get("sequence_length", 50)
        self.feature_names = model_state.get("feature_names")
        self.reconstruction_threshold = model_state.get("reconstruction_threshold", 0.1)
        self.is_trained = state.get("is_trained", False)

        # Restore scaler
        if "scaler_mean" in model_state and "scaler_scale" in model_state:
            self.scaler.mean_ = np.array(model_state["scaler_mean"])
            self.scaler.scale_ = np.array(model_state["scaler_scale"])

        # Rebuild model
        input_dim = len(self.feature_names) if self.feature_names else 10  # Fallback
        self._build_model(input_dim)

        # Load weights
        weights_path = model_state.get("weights_path")
        if weights_path and self.storage_manager:
            full_weights_path = os.path.join(self.storage_manager.get_storage_path(), weights_path)
            if os.path.exists(full_weights_path):
                try:
                    self.autoencoder.load_weights(full_weights_path)
                    self.logger.info(f"Model weights loaded from {weights_path}")
                except Exception as e:
                    self.logger.error(f"Failed to load model weights: {e}")
                    return False
            else:
                self.logger.warning(f"Model weights file not found: {full_weights_path}")
                return False

        self.logger.info(f"Model '{self.name}' loaded from storage")
        return True
