"""
IMPROVED Feature Extractor for Anomaly Detection System

Key improvements:
1. Proper imputation strategies (mean, median, mode, KNN)
2. Real NLP embeddings using SentenceTransformers
3. Better handling of missing values
4. Feature alignment for train/test consistency
5. Comprehensive feature engineering
"""

import logging
import hashlib
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Union, Tuple
from collections import defaultdict
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.preprocessing import StandardScaler
import json

# Try to import SentenceTransformers for real embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers not installed. Real embeddings not available.")

try:
    from anomaly_detection.processors.base import Processor
except ImportError:
    class Processor:
        def __init__(self, name: str, config: Dict[str, Any]):
            self.name = name
            self.config = config
            self.logger = logging.getLogger(name)


class FeatureImputer:
    """
    Handles missing value imputation with multiple strategies.
    """
    
    def __init__(self, strategy: str = "median", n_neighbors: int = 5):
        """
        Initialize feature imputer.
        
        Args:
            strategy: Imputation strategy - 'mean', 'median', 'mode', 'knn', 'constant'
            n_neighbors: Number of neighbors for KNN imputation
        """
        self.strategy = strategy
        self.n_neighbors = n_neighbors
        self.imputers = {}
        self.feature_medians = {}
        self.feature_means = {}
        self.feature_modes = {}
        
    def fit(self, feature_matrix: np.ndarray, feature_names: List[str]):
        """
        Fit imputer on training data.
        
        Args:
            feature_matrix: Training feature matrix
            feature_names: List of feature names
        """
        if self.strategy == "knn":
            self.imputers["knn"] = KNNImputer(n_neighbors=self.n_neighbors)
            self.imputers["knn"].fit(feature_matrix)
        else:
            # Compute statistics for each feature
            for i, name in enumerate(feature_names):
                values = feature_matrix[:, i]
                valid_values = values[~np.isnan(values)]
                
                if len(valid_values) > 0:
                    self.feature_means[name] = np.mean(valid_values)
                    self.feature_medians[name] = np.median(valid_values)
                    # Mode for discrete values
                    unique, counts = np.unique(valid_values, return_counts=True)
                    self.feature_modes[name] = unique[np.argmax(counts)]
                else:
                    self.feature_means[name] = 0.0
                    self.feature_medians[name] = 0.0
                    self.feature_modes[name] = 0.0
    
    def transform(self, feature_matrix: np.ndarray, feature_names: List[str]) -> np.ndarray:
        """
        Impute missing values in feature matrix.
        
        Args:
            feature_matrix: Feature matrix with missing values
            feature_names: List of feature names
            
        Returns:
            Imputed feature matrix
        """
        if self.strategy == "knn" and "knn" in self.imputers:
            return self.imputers["knn"].transform(feature_matrix)
        
        # Column-wise imputation
        imputed = feature_matrix.copy()
        
        for i, name in enumerate(feature_names):
            mask = np.isnan(imputed[:, i])
            if np.any(mask):
                if self.strategy == "mean":
                    fill_value = self.feature_means.get(name, 0.0)
                elif self.strategy == "median":
                    fill_value = self.feature_medians.get(name, 0.0)
                elif self.strategy == "mode":
                    fill_value = self.feature_modes.get(name, 0.0)
                else:  # constant
                    fill_value = 0.0
                
                imputed[mask, i] = fill_value
        
        return imputed


class TextEmbedder:
    """
    Handles text embeddings using SentenceTransformers or fallback methods.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", use_real_embeddings: bool = True):
        """
        Initialize text embedder.
        
        Args:
            model_name: SentenceTransformer model name
            use_real_embeddings: Whether to use real embeddings (requires sentence-transformers)
        """
        self.model_name = model_name
        self.use_real_embeddings = use_real_embeddings and SENTENCE_TRANSFORMERS_AVAILABLE
        self.model = None
        self.embedding_dim = None
        
        if self.use_real_embeddings:
            try:
                self.model = SentenceTransformer(model_name)
                # Get embedding dimension
                test_embedding = self.model.encode(["test"])
                self.embedding_dim = test_embedding.shape[1]
                logging.info(f"Loaded SentenceTransformer model: {model_name} (dim={self.embedding_dim})")
            except Exception as e:
                logging.error(f"Failed to load SentenceTransformer: {e}")
                self.use_real_embeddings = False
                self.embedding_dim = 384  # Default fallback dimension
        else:
            self.embedding_dim = 384  # Default dimension for fallback
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                logging.warning("SentenceTransformers not available. Using statistical text features instead.")
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """
        Encode texts to embeddings.
        
        Args:
            texts: List of text strings
            
        Returns:
            Array of embeddings (shape: [len(texts), embedding_dim])
        """
        if self.use_real_embeddings and self.model is not None:
            try:
                return self.model.encode(texts, show_progress_bar=False)
            except Exception as e:
                logging.error(f"Embedding encoding failed: {e}")
                return self._fallback_encode(texts)
        else:
            return self._fallback_encode(texts)
    
    def _fallback_encode(self, texts: List[str]) -> np.ndarray:
        """
        Fallback text encoding using statistical features (NO FAKE HASHING).
        
        This creates a reduced feature vector based on actual text statistics.
        """
        embeddings = []
        
        for text in texts:
            features = []
            
            # Basic statistics (first 10 dimensions)
            features.append(len(text))  # Length
            features.append(len(text.split()))  # Word count
            features.append(sum(c.isdigit() for c in text))  # Digit count
            features.append(sum(c.isalpha() for c in text))  # Alpha count
            features.append(sum(c.isupper() for c in text))  # Uppercase count
            features.append(sum(c.islower() for c in text))  # Lowercase count
            features.append(sum(c.isspace() for c in text))  # Space count
            features.append(text.count('.'))  # Period count
            features.append(text.count(','))  # Comma count
            features.append(len(set(text)))  # Unique char count
            
            # Character n-gram frequencies (next 10 dimensions)
            # Count common 2-character patterns
            bigrams = [text[i:i+2] for i in range(len(text)-1)]
            common_bigrams = ['th', 'he', 'in', 'er', 'an', 'ed', 'nd', 'to', 'en', 'at']
            for bg in common_bigrams:
                features.append(bigrams.count(bg))
            
            # Normalize to reasonable scale
            features = [f / (len(text) + 1) for f in features]
            
            # Pad to target dimension with zeros
            while len(features) < self.embedding_dim:
                features.append(0.0)
            
            embeddings.append(features[:self.embedding_dim])
        
        return np.array(embeddings, dtype=np.float32)


class FeatureExtractor(Processor):
    """
    Processor for feature extraction with proper imputation and embeddings.
    
    Key features:
    - Real NLP embeddings via SentenceTransformers
    - Proper missing value imputation (mean, median, mode, KNN)
    - Feature alignment for consistent train/test features
    - Better handling of categorical variables
    - Comprehensive feature engineering
    """
    
    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """Initialize improved feature extractor."""
        super().__init__(name, config)
        self.storage_manager = storage_manager
        
        # Fields to ignore
        self.FIELDS_TO_IGNORE = {
            "_source", "features", "normalized", "extracted_features",
            "_collection_metadata", "raw_data", "id", "_id",
            "collected_at", "collection_timestamp"
        }
        
        # Load field configurations
        self.numerical_fields = set(config.get("numerical_fields", []))
        self.categorical_fields = set(config.get("categorical_fields", []))
        self.boolean_fields = set(config.get("boolean_fields", []))
        self.text_fields = set(config.get("text_fields", []))
        self.timestamp_field = config.get("timestamp_field", "timestamp")
        
        # Imputation configuration
        self.imputation_strategy = config.get("imputation_strategy", "median")
        self.knn_neighbors = config.get("knn_neighbors", 5)
        self.imputer = FeatureImputer(self.imputation_strategy, self.knn_neighbors)
        
        # Text embedding configuration
        self.use_real_embeddings = config.get("use_real_embeddings", True)
        self.embedding_model = config.get("embedding_model", "all-MiniLM-L6-v2")
        self.text_embedder = TextEmbedder(self.embedding_model, self.use_real_embeddings)
        
        # Categorical encoding
        self.categorical_encoding = config.get("categorical_encoding", "label")
        self.categorical_mappings = {}
        self.categorical_values = defaultdict(set)
        
        # Feature alignment
        self.fitted_feature_names = None
        self.is_fitted = False
        
        # Array handling
        self.extract_from_arrays = config.get("extract_from_arrays", ["raw_data"])
        
        # Temporal features
        self.extract_temporal_features = config.get("extract_temporal_features", True)
        
        self.logger.info(f"Initialized ImprovedFeatureExtractor")
        self.logger.info(f"  - Imputation: {self.imputation_strategy}")
        self.logger.info(f"  - Real embeddings: {self.use_real_embeddings}")
        self.logger.info(f"  - Embedding model: {self.embedding_model}")
    
    def fit(self, data: List[Dict[str, Any]]) -> 'ImprovedFeatureExtractor':
        """
        Fit the feature extractor on training data.
        
        This learns:
        - Feature names and order
        - Categorical mappings
        - Imputation statistics
        
        Args:
            data: Training data
            
        Returns:
            Self for chaining
        """
        self.logger.info(f"Fitting feature extractor on {len(data)} samples")
        
        # Extract features without imputation to learn structure
        temp_features = []
        for item in data:
            records = self._get_records_from_item(item)
            for record in records:
                features = self._extract_raw_features(record, fit_mode=True)
                temp_features.append(features)
        
        if not temp_features:
            raise ValueError("No features extracted during fitting")
        
        # Get consistent feature names
        all_feature_names = set()
        for feat_dict in temp_features:
            all_feature_names.update(feat_dict.keys())
        
        self.fitted_feature_names = sorted(all_feature_names)
        self.logger.info(f"Fitted {len(self.fitted_feature_names)} feature names")
        
        # Convert to matrix for imputer fitting
        feature_matrix = self._features_to_matrix(temp_features, self.fitted_feature_names)
        
        # Fit imputer
        self.imputer.fit(feature_matrix, self.fitted_feature_names)
        
        self.is_fitted = True
        self.logger.info("Feature extractor fitting complete")
        
        return self
    
    def process(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract and impute features from data.
        
        Args:
            data: List of data items
            
        Returns:
            List of data items with extracted features
        """
        if not self.is_fitted:
            self.logger.warning("Feature extractor not fitted. Fitting on current data.")
            self.fit(data)
        
        processed_data = []
        
        for item in data:
            processed_item = item.copy()
            
            try:
                # Get records from item (handles batch structures)
                records = self._get_records_from_item(item)
                
                # Extract features from all records
                all_features = []
                for record in records:
                    features = self._extract_raw_features(record, fit_mode=False)
                    all_features.append(features)
                
                # Aggregate features (for batch processing)
                if len(all_features) > 1:
                    aggregated_features = self._aggregate_features(all_features)
                else:
                    aggregated_features = all_features[0] if all_features else {}
                
                # Align features with fitted feature names
                aligned_features = self._align_features(aggregated_features)
                
                # Convert to matrix, impute, convert back
                feature_matrix = self._features_to_matrix([aligned_features], self.fitted_feature_names)
                imputed_matrix = self.imputer.transform(feature_matrix, self.fitted_feature_names)
                
                # Convert back to dictionary
                final_features = {}
                for i, name in enumerate(self.fitted_feature_names):
                    final_features[name] = float(imputed_matrix[0, i])
                
                processed_item["features"] = final_features
                processed_item["extracted_features"] = final_features
                
                self.logger.debug(f"Extracted {len(final_features)} features")
                
            except Exception as e:
                self.logger.error(f"Error extracting features: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                processed_item["features"] = {}
                processed_item["extracted_features"] = {}
            
            processed_data.append(processed_item)
        
        self.logger.info(f"Processed {len(processed_data)} items")
        return processed_data
    
    def fit_transform(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fit and then transform (process) the data.
        
        Args:
            data: Training data
            
        Returns:
            List of data items with extracted features
        """
        self.fit(data)
        return self.process(data)
    
    def _get_records_from_item(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract actual records from item (handles batch structures)."""
        # Check for array fields containing records
        for array_field in self.extract_from_arrays:
            if array_field in item and isinstance(item[array_field], list):
                return item[array_field]
        
        # Single record
        return [item]
    
    def _extract_raw_features(self, record: Dict[str, Any], fit_mode: bool = False) -> Dict[str, float]:
        """
        Extract raw features from a single record.
        
        Args:
            record: Data record
            fit_mode: Whether in fitting mode (learns categorical mappings)
            
        Returns:
            Dictionary of features
        """
        features = {}
        
        # 1. Numerical features
        for field in self.numerical_fields:
            if field in record:
                value = record[field]
                try:
                    num_value = float(value)
                    if not np.isinf(num_value):  # Keep NaN for imputation
                        features[f"num_{field}"] = num_value
                    else:
                        features[f"num_{field}"] = np.nan
                except (ValueError, TypeError):
                    features[f"num_{field}"] = np.nan
            else:
                features[f"num_{field}"] = np.nan
        
        # 2. Boolean features
        for field in self.boolean_fields:
            if field in record:
                value = record[field]
                if isinstance(value, bool):
                    features[f"bool_{field}"] = float(value)
                elif isinstance(value, str):
                    features[f"bool_{field}"] = float(value.lower() in ['true', '1', 'yes'])
                else:
                    features[f"bool_{field}"] = float(bool(value))
            else:
                features[f"bool_{field}"] = np.nan
        
        # 3. Categorical features
        for field in self.categorical_fields:
            if field in record:
                value = str(record[field])
                
                if fit_mode:
                    # Learn categorical values
                    self.categorical_values[field].add(value)
                
                # Encode based on strategy
                if self.categorical_encoding == "label":
                    if field not in self.categorical_mappings and fit_mode:
                        # Create mapping
                        sorted_values = sorted(self.categorical_values[field])
                        self.categorical_mappings[field] = {v: i for i, v in enumerate(sorted_values)}
                    
                    if field in self.categorical_mappings:
                        features[f"cat_{field}"] = float(self.categorical_mappings[field].get(value, -1))
                    else:
                        features[f"cat_{field}"] = -1.0
                        
                elif self.categorical_encoding == "hash":
                    # Simple hash encoding
                    hash_val = hash(value) % 10000
                    features[f"cat_{field}_hash"] = float(hash_val)
            else:
                features[f"cat_{field}"] = np.nan
        
        # 4. Text features with REAL embeddings
        for field in self.text_fields:
            if field in record and record[field]:
                text = str(record[field])
                
                # Get embedding
                embedding = self.text_embedder.encode([text])[0]
                
                # Add embedding dimensions as features
                for i, val in enumerate(embedding):
                    features[f"text_{field}_emb_{i}"] = float(val)
            else:
                # Missing text - will be imputed
                for i in range(self.text_embedder.embedding_dim):
                    features[f"text_{field}_emb_{i}"] = np.nan
        
        # 5. Temporal features from timestamp
        if self.extract_temporal_features and self.timestamp_field in record:
            temporal_features = self._extract_temporal_features(record[self.timestamp_field])
            features.update(temporal_features)
        
        return features
    
    def _extract_temporal_features(self, timestamp_value: Any) -> Dict[str, float]:
        """Extract temporal features from timestamp."""
        features = {}
        
        try:
            from datetime import datetime
            
            if isinstance(timestamp_value, str):
                dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            elif isinstance(timestamp_value, (int, float)):
                dt = datetime.fromtimestamp(timestamp_value)
            elif isinstance(timestamp_value, datetime):
                dt = timestamp_value
            else:
                return features
            
            # Extract temporal features
            features["temporal_hour"] = float(dt.hour)
            features["temporal_day_of_week"] = float(dt.weekday())
            features["temporal_day_of_month"] = float(dt.day)
            features["temporal_month"] = float(dt.month)
            features["temporal_is_weekend"] = float(dt.weekday() >= 5)
            features["temporal_is_business_hours"] = float(9 <= dt.hour <= 17)
            
        except Exception as e:
            self.logger.debug(f"Failed to extract temporal features: {e}")
        
        return features
    
    def _aggregate_features(self, feature_list: List[Dict[str, float]]) -> Dict[str, float]:
        """
        Aggregate features from multiple records (for batch processing).
        
        Uses mean aggregation by default.
        """
        if not feature_list:
            return {}
        
        if len(feature_list) == 1:
            return feature_list[0]
        
        # Collect all feature names
        all_keys = set()
        for feat_dict in feature_list:
            all_keys.update(feat_dict.keys())
        
        # Aggregate using mean
        aggregated = {}
        for key in all_keys:
            values = [f.get(key, np.nan) for f in feature_list]
            valid_values = [v for v in values if not np.isnan(v)]
            
            if valid_values:
                aggregated[key] = float(np.mean(valid_values))
            else:
                aggregated[key] = np.nan
        
        return aggregated
    
    def _align_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Align features with fitted feature names.
        
        Ensures consistent feature order and handles missing features.
        """
        if not self.is_fitted or not self.fitted_feature_names:
            return features
        
        aligned = {}
        for name in self.fitted_feature_names:
            aligned[name] = features.get(name, np.nan)
        
        return aligned
    
    def _features_to_matrix(self, feature_list: List[Dict[str, float]], 
                           feature_names: List[str]) -> np.ndarray:
        """Convert list of feature dictionaries to numpy matrix."""
        matrix = np.zeros((len(feature_list), len(feature_names)))
        
        for i, feat_dict in enumerate(feature_list):
            for j, name in enumerate(feature_names):
                matrix[i, j] = feat_dict.get(name, np.nan)
        
        return matrix
    
    def get_feature_names(self) -> List[str]:
        """Get the list of fitted feature names."""
        return self.fitted_feature_names if self.fitted_feature_names else []
    
    def save_state(self, filepath: str):
        """Save feature extractor state."""
        state = {
            "fitted_feature_names": self.fitted_feature_names,
            "categorical_mappings": self.categorical_mappings,
            "categorical_values": {k: list(v) for k, v in self.categorical_values.items()},
            "is_fitted": self.is_fitted,
            "config": self.config
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        self.logger.info(f"Saved feature extractor state to {filepath}")
    
    def load_state(self, filepath: str):
        """Load feature extractor state."""
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        self.fitted_feature_names = state.get("fitted_feature_names")
        self.categorical_mappings = state.get("categorical_mappings", {})
        self.categorical_values = defaultdict(set, {
            k: set(v) for k, v in state.get("categorical_values", {}).items()
        })
        self.is_fitted = state.get("is_fitted", False)
        
        self.logger.info(f"Loaded feature extractor state from {filepath}")