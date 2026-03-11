"""
Clustering-based Anomaly Detection Model

Uses clustering algorithms to detect anomalies based on distance from cluster centers.
"""

import logging
import numpy as np
from typing import Dict, List, Any, Tuple
import pickle

try:
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not installed. ClusteringModel will not work.")

from anomaly_detection.models.base import ImprovedAnomalyDetectionModel


class ClusteringModel(ImprovedAnomalyDetectionModel):
    """
    Clustering-based anomaly detection model.

    Uses K-means or DBSCAN clustering to identify anomalies based on
    distance from cluster centers or density-based outliers.
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """Initialize Clustering model."""
        super().__init__(name, config, storage_manager)

        if not SKLEARN_AVAILABLE:
            self.logger.error("scikit-learn not installed")
            return

        # Algorithm selection
        self.algorithm = config.get("algorithm", "kmeans").lower()

        # K-means parameters
        if self.algorithm == "kmeans":
            self.n_clusters = int(config.get("n_clusters", 8))
            self.init_method = config.get("init_method", "k-means++")
            self.max_iter = int(config.get("max_iter", 300))
            self.tol = float(config.get("tol", 1e-4))

        # DBSCAN parameters
        elif self.algorithm == "dbscan":
            self.eps = float(config.get("eps", 0.5))
            self.min_samples = int(config.get("min_samples", 5))
            self.metric = config.get("metric", "euclidean")

        # Common parameters
        self.random_state = int(config.get("random_state", 42))

        # Anomaly detection parameters
        self.contamination = float(config.get("contamination", 0.1))
        self.distance_threshold = None  # Will be calculated during training

        # Feature scaling
        self.scaler = StandardScaler()

        # Model components
        self.cluster_model = None
        self.cluster_centers_ = None
        self.labels_ = None

        self.logger.info(f"Initialized {self.algorithm.upper()} Clustering model")

    def _get_anomaly_scores(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """
        Get anomaly scores based on clustering results.

        Args:
            data: List of data items with features

        Returns:
            Array of anomaly scores (higher = more anomalous)
        """
        if self.cluster_model is None:
            self.logger.error("Model not trained")
            return np.array([])

        # Extract and scale features
        features = self._extract_features_for_prediction(data)
        if features.shape[0] == 0:
            return np.array([])

        features_scaled = self.scaler.transform(features)

        if self.algorithm == "kmeans":
            return self._kmeans_anomaly_scores(features_scaled)
        elif self.algorithm == "dbscan":
            return self._dbscan_anomaly_scores(features_scaled)
        else:
            self.logger.error(f"Unknown algorithm: {self.algorithm}")
            return np.array([])

    def _kmeans_anomaly_scores(self, features_scaled: np.ndarray) -> np.ndarray:
        """Calculate anomaly scores for K-means clustering."""
        # Calculate distance to nearest cluster center
        distances = np.zeros(features_scaled.shape[0])

        for i, point in enumerate(features_scaled):
            # Calculate distance to each cluster center
            cluster_distances = np.linalg.norm(point - self.cluster_centers_, axis=1)
            # Use distance to nearest cluster
            distances[i] = np.min(cluster_distances)

        # Normalize distances to [0, 1] range
        if self.distance_threshold is not None:
            # Use training threshold for normalization
            scores = distances / self.distance_threshold
        else:
            # Fallback: use max distance in current batch
            max_dist = np.max(distances)
            if max_dist > 0:
                scores = distances / max_dist
            else:
                scores = distances

        return scores

    def _dbscan_anomaly_scores(self, features_scaled: np.ndarray) -> np.ndarray:
        """Calculate anomaly scores for DBSCAN clustering."""
        # Predict cluster labels for new data
        labels = self.cluster_model.fit_predict(features_scaled)

        # Anomalies are points labeled as -1 (noise)
        # For scored anomalies, use distance to nearest core point
        scores = np.zeros(len(labels))

        # Points labeled as noise get high scores
        noise_mask = labels == -1
        scores[noise_mask] = 1.0

        # For clustered points, calculate distance-based scores
        if np.any(~noise_mask):
            # Find core samples
            core_samples_mask = np.zeros(len(labels), dtype=bool)
            core_samples_mask[self.cluster_model.core_sample_indices_] = True

            for i, (label, is_core) in enumerate(zip(labels, core_samples_mask)):
                if label != -1:  # Not noise
                    if is_core:
                        scores[i] = 0.0  # Core points are normal
                    else:
                        # Border points: calculate distance to cluster center
                        cluster_points = features_scaled[labels == label]
                        if len(cluster_points) > 0:
                            center = np.mean(cluster_points, axis=0)
                            distance = np.linalg.norm(features_scaled[i] - center)
                            # Normalize by expected distance threshold
                            scores[i] = min(distance / self.eps, 1.0)

        return scores

    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train the clustering model."""
        if not SKLEARN_AVAILABLE:
            self.logger.error("scikit-learn not installed")
            return

        # Extract features
        features, feature_names = self._extract_features(data)

        if features.shape[0] == 0:
            self.logger.error("No features in training data")
            return

        self.logger.info(f"Training on {features.shape[0]} samples with {features.shape[1]} features")

        # Scale features
        features_scaled = self.scaler.fit_transform(features)

        # Train clustering model
        if self.algorithm == "kmeans":
            self.cluster_model = KMeans(
                n_clusters=self.n_clusters,
                init=self.init_method,
                max_iter=self.max_iter,
                tol=self.tol,
                random_state=self.random_state
            )

            # Fit and get cluster assignments
            self.labels_ = self.cluster_model.fit_predict(features_scaled)
            self.cluster_centers_ = self.cluster_model.cluster_centers_

            # Calculate distance threshold based on training data
            distances = np.zeros(features_scaled.shape[0])
            for i, point in enumerate(features_scaled):
                cluster_distances = np.linalg.norm(point - self.cluster_centers_, axis=1)
                distances[i] = np.min(cluster_distances)

            # Set threshold based on contamination parameter
            self.distance_threshold = np.percentile(distances, (1 - self.contamination) * 100)

            # Calculate silhouette score for model quality
            if len(np.unique(self.labels_)) > 1:
                silhouette_avg = silhouette_score(features_scaled, self.labels_)
                self.logger.info(f"Silhouette score: {silhouette_avg:.3f}")
            else:
                self.logger.warning("Only one cluster found - model may not be suitable")

        elif self.algorithm == "dbscan":
            self.cluster_model = DBSCAN(
                eps=self.eps,
                min_samples=self.min_samples,
                metric=self.metric
            )

            # Fit and get cluster assignments
            self.labels_ = self.cluster_model.fit_predict(features_scaled)

            # Count noise points
            n_noise = np.sum(self.labels_ == -1)
            n_clusters = len(set(self.labels_)) - (1 if -1 in self.labels_ else 0)

            self.logger.info(f"Found {n_noise} noise points and {n_clusters} clusters")

            if n_clusters == 0:
                self.logger.warning("No clusters found - DBSCAN parameters may need adjustment")

        else:
            self.logger.error(f"Unknown algorithm: {self.algorithm}")
            return

        # Save model state
        self.model_state = {
            "algorithm": self.algorithm,
            "scaler_mean": self.scaler.mean_.tolist(),
            "scaler_scale": self.scaler.scale_.tolist(),
            "feature_names": feature_names,
            "cluster_centers": self.cluster_centers_.tolist() if self.cluster_centers_ is not None else None,
            "distance_threshold": self.distance_threshold,
            "labels_sample": self.labels_[:100].tolist() if len(self.labels_) > 100 else self.labels_.tolist(),  # Sample for validation
            "training_samples": features.shape[0],
            "contamination": self.contamination
        }

        # Add algorithm-specific state
        if self.algorithm == "kmeans":
            self.model_state.update({
                "n_clusters": self.n_clusters,
                "inertia": float(self.cluster_model.inertia_),
                "n_iter": int(self.cluster_model.n_iter_)
            })
        elif self.algorithm == "dbscan":
            self.model_state.update({
                "eps": self.eps,
                "min_samples": self.min_samples,
                "n_noise_points": int(np.sum(self.labels_ == -1)),
                "n_clusters": len(set(self.labels_)) - (1 if -1 in self.labels_ else 0),
                "core_sample_indices": self.cluster_model.core_sample_indices_.tolist()
            })

        self.is_trained = True
        self.logger.info(f"Training completed with {self.algorithm.upper()} algorithm")

    def _extract_features(self, data: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[str]]:
        """Extract features from data for training/prediction."""
        features_list = []
        feature_names = None

        for item in data:
            if "features" in item and isinstance(item["features"], dict):
                if feature_names is None:
                    feature_names = sorted(item["features"].keys())

                # Extract feature values in consistent order
                feature_values = []
                for name in feature_names:
                    value = item["features"].get(name, 0.0)
                    try:
                        feature_values.append(float(value))
                    except (ValueError, TypeError):
                        feature_values.append(0.0)

                features_list.append(feature_values)

        if not features_list:
            return np.array([]), []

        return np.array(features_list), feature_names

    def _extract_features_for_prediction(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """Extract features for prediction."""
        features, _ = self._extract_features(data)
        return features

    def save(self, path: Optional[str] = None) -> None:
        """Save model to storage."""
        if self.storage_manager and self.model_state:
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

        # Restore scaler
        if "scaler_mean" in model_state and "scaler_scale" in model_state:
            self.scaler.mean_ = np.array(model_state["scaler_mean"])
            self.scaler.scale_ = np.array(model_state["scaler_scale"])

        # Restore cluster centers
        if model_state.get("cluster_centers"):
            self.cluster_centers_ = np.array(model_state["cluster_centers"])

        # Restore parameters
        self.algorithm = model_state.get("algorithm", "kmeans")
        self.distance_threshold = model_state.get("distance_threshold")
        self.is_trained = state.get("is_trained", False)

        # Recreate model with loaded parameters
        if self.algorithm == "kmeans":
            self.cluster_model = KMeans(
                n_clusters=model_state.get("n_clusters", 8),
                random_state=self.random_state
            )
        elif self.algorithm == "dbscan":
            self.cluster_model = DBSCAN(
                eps=model_state.get("eps", 0.5),
                min_samples=model_state.get("min_samples", 5)
            )

        self.logger.info(f"Model '{self.name}' loaded from storage")
        return True
