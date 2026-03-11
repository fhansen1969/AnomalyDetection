# Anomaly Detection Algorithms Reference

This document provides a comprehensive reference for every algorithm used in the Anomaly Detection system, including ML models, feature engineering techniques, score normalization methods, and the ensemble combination strategy.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Statistical Model](#1-statistical-model)
3. [Isolation Forest](#2-isolation-forest)
4. [One-Class SVM](#3-one-class-svm)
5. [Autoencoder](#4-autoencoder)
6. [GAN-Based Detector](#5-gan-based-detector)
7. [LSTM Autoencoder](#6-lstm-autoencoder)
8. [Clustering Model](#7-clustering-model)
9. [Ensemble Model](#8-ensemble-model)
10. [Score Normalization](#score-normalization)
11. [Feature Engineering](#feature-engineering)
12. [Algorithm Selection Guide](#algorithm-selection-guide)

---

## Architecture Overview

All models inherit from the abstract base class `AnomalyDetectionModel`, which defines the interface contract:

```
AnomalyDetectionModel (abstract)
├── train(data) -> None
├── detect(data) -> List[anomaly]
├── get_state() -> Dict
└── set_state(state) -> None

ImprovedAnomalyDetectionModel (extends above)
├── _get_anomaly_scores(data) -> np.ndarray
└── evaluate(data, labels) -> Dict[metrics]
```

**Data format**: All models consume `List[Dict]` where each item contains a `"features"` key mapping to a dictionary of feature name-value pairs. Features are extracted into a numeric matrix (`np.ndarray`) before model processing.

**Source files**: `anomaly_detection/models/`

---

## 1. Statistical Model

**Source**: `anomaly_detection/models/statistical.py`
**Class**: `StatisticalModel`
**Dependencies**: NumPy only (no external ML library)

### Algorithm

The Statistical Model uses **Z-score analysis** to detect anomalies. It learns the distribution of each feature during training and flags data points that deviate significantly during detection.

### Training Phase

For each feature `f` in the training data, the model computes and stores:

| Statistic | Formula |
|-----------|---------|
| Mean | `mean_f = (1/N) * sum(x_f)` |
| Standard Deviation | `std_f = sqrt((1/N) * sum((x_f - mean_f)^2))` |
| Min | `min_f = min(x_f)` |
| Max | `max_f = max(x_f)` |

If `std_f < 1e-10` (constant feature), it is set to `1.0` to prevent division by zero.

### Detection Phase

For each sample `x`:

1. Compute the Z-score for every feature: `z_f = |x_f - mean_f| / std_f`
2. Take the **maximum absolute Z-score** across all features: `score(x) = max(|z_f|) for all f`
3. Normalize all scores to `[0, 1]` via min-max normalization across the batch
4. Flag as anomaly if `normalized_score >= threshold`

### Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `threshold` | `0.7` | Minimum normalized score to classify as anomaly |
| `threshold_multiplier` | `3.0` | Z-score multiplier (stored but not used in current detection logic) |
| `window_size` | `10` | Window size parameter (reserved for future use) |
| `feature_prefix` | `None` | Optional prefix filter to select subset of features |

### Characteristics

- **Strengths**: Extremely fast, fully interpretable, zero external dependencies, works well as a baseline
- **Weaknesses**: Assumes features are independent; uses max Z-score so a single noisy feature can dominate; assumes approximately Gaussian distributions
- **Computational complexity**: O(N * F) for both training and detection, where N = samples, F = features
- **Serialization**: Pure Python dict (feature statistics)

---

## 2. Isolation Forest

**Source**: `anomaly_detection/models/isolation_forest.py`
**Class**: `IsolationForestModel`
**Dependencies**: scikit-learn (`sklearn.ensemble.IsolationForest`)

### Algorithm

Isolation Forest isolates anomalies by randomly selecting a feature and then randomly selecting a split value between the minimum and maximum values of that feature. Anomalies require fewer splits (shorter path lengths) to be isolated because they are rare and different.

The intuition: anomalies are few and different, so they are easier to separate from the rest of the data with random partitions.

### Training Phase

1. Extract all features into a numeric matrix
2. Build an ensemble of `n_estimators` random isolation trees
3. Each tree randomly selects features and split points to partition the data
4. The model learns which samples require fewer partitions to isolate

### Detection Phase

1. Align input features with training feature names (missing features default to `0.0`)
2. Compute the `decision_function()` score for each sample (negative values indicate anomalies)
3. Invert scores: `inverted = -decision_function` so higher values = more anomalous
4. Normalize to `[0, 1]` via min-max normalization
5. Flag as anomaly if `normalized_score >= threshold`

### Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_estimators` | `100` | Number of isolation trees in the forest |
| `max_samples` | `"auto"` | Number of samples to draw per tree (`auto` = min(256, N)) |
| `contamination` | `0.01` | Expected proportion of anomalies (1%) |
| `random_state` | `42` | Random seed for reproducibility |
| `threshold` | `0.7` | Minimum normalized score for anomaly classification |
| `feature_prefix` | `None` | Optional prefix filter for feature selection |

### Characteristics

- **Strengths**: No distribution assumptions; scales well to high-dimensional data; effective with large datasets; parallelized (`n_jobs=-1`)
- **Weaknesses**: Contamination parameter must be estimated; may struggle with locally dense anomalies; sensitive to irrelevant features
- **Computational complexity**: O(N * T * log(N)) for training, O(N * T * log(N)) for detection, where T = number of trees
- **Serialization**: Pickle (full sklearn model object)

---

## 3. One-Class SVM

**Source**: `anomaly_detection/models/one_class_svm.py`
**Class**: `OneClassSVMModel`
**Dependencies**: scikit-learn (`sklearn.svm.OneClassSVM`)

### Algorithm

One-Class SVM learns a decision boundary in a high-dimensional feature space that encloses the majority of normal data. It maps input features into a kernel-induced space using the Radial Basis Function (RBF) kernel and finds the hyperplane that separates the data from the origin with maximum margin.

### Training Phase

1. Extract features with safe scalar conversion (handles lists, arrays, strings, dicts)
2. Validate feature matrix for NaN/Inf values
3. Fit `OneClassSVM` with the RBF kernel to learn the decision boundary

### Detection Phase

1. Align features with training feature names
2. Get predictions: `-1` = anomaly, `+1` = normal
3. Compute decision function scores and invert: `raw_score = -decision_function`
4. Apply **sigmoid normalization**: `normalized_score = 1 / (1 + exp(-raw_score))`
5. Flag as anomaly if `prediction == -1` OR `normalized_score >= threshold`

### Type Handling

The One-Class SVM includes a comprehensive `_safe_scalar_conversion()` method that handles:

| Input Type | Conversion |
|------------|------------|
| Numeric scalar | Direct `float()` conversion |
| Single-element array | Extract and convert the element |
| Multi-element numeric array | Mean of all elements |
| Non-numeric array | Count (length) |
| String | `hash(string) % 10000` |
| Dict | Number of keys |
| None | `0.0` |

### Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `kernel` | `"rbf"` | Kernel function (Radial Basis Function) |
| `nu` | `0.01` | Upper bound on the fraction of training errors / support vectors (1%) |
| `gamma` | `"scale"` | Kernel coefficient; `"scale"` = `1 / (n_features * X.var())` |
| `threshold` | `0.7` | Minimum sigmoid-normalized score for anomaly classification |
| `feature_prefix` | `None` | Optional prefix filter for feature selection |

### Characteristics

- **Strengths**: Effective for high-dimensional data; flexible kernel functions; well-founded mathematical theory
- **Weaknesses**: O(N^2) to O(N^3) training complexity; sensitive to feature scaling; `nu` parameter requires tuning
- **Computational complexity**: O(N^2 * F) to O(N^3) training; O(N_sv * F) detection, where N_sv = support vectors
- **Serialization**: Pickle (full sklearn model object)

---

## 4. Autoencoder

**Source**: `anomaly_detection/models/autoencoder.py`
**Class**: `AutoencoderModel`
**Network**: `AutoencoderNetwork` (PyTorch `nn.Module`)
**Dependencies**: PyTorch (`torch`, `torch.nn`)

### Algorithm

The Autoencoder is a neural network trained to reconstruct its input. It compresses data through a bottleneck (encoder) and then reconstructs it (decoder). Normal data is reconstructed accurately while anomalies produce high reconstruction error.

### Network Architecture

```
Input (F dims)
  -> Linear(F, 64) -> ReLU
  -> Linear(64, 32) -> ReLU
  -> Linear(32, 16) -> ReLU          [Bottleneck / Latent Space]
  -> Linear(16, 32) -> ReLU
  -> Linear(32, 64) -> ReLU
  -> Linear(64, F)                   [Reconstruction]
```

The architecture is symmetric: the decoder mirrors the encoder with reversed layer dimensions.

### Training Phase

1. Extract features into a matrix and convert to `torch.FloatTensor`
2. Move data to GPU if available (`cuda`), otherwise CPU
3. Train end-to-end using:
   - **Loss function**: Mean Squared Error (MSE) between input and reconstruction
   - **Optimizer**: Adam with configurable learning rate
   - **Training loop**: Iterate for `epochs` epochs over batches of `batch_size`
4. Log loss every 10 epochs for monitoring

### Detection Phase

1. Align features with training feature names
2. Forward pass through the trained autoencoder
3. Compute per-sample reconstruction error: `MSE(x, reconstruct(x))`
4. Normalize errors to `[0, 1]` via min-max normalization
5. Flag as anomaly if `normalized_error >= threshold`

### Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hidden_dims` | `[64, 32, 16]` | Layer dimensions for encoder (decoder mirrors) |
| `learning_rate` | `0.001` | Adam optimizer learning rate |
| `epochs` | `50` | Number of training epochs |
| `batch_size` | `32` | Training batch size |
| `threshold` | `0.7` | Minimum normalized reconstruction error for anomaly |
| `feature_prefix` | `None` | Optional prefix filter for feature selection |

### Characteristics

- **Strengths**: Learns non-linear patterns; GPU-accelerable; captures complex feature interactions; effective bottleneck forces learning of essential data structure
- **Weaknesses**: Requires sufficient training data; prone to overfitting on small datasets; PyTorch dependency; architecture must be tuned per dataset
- **Computational complexity**: O(epochs * N * F * H) training; O(N * F * H) detection, where H = total hidden units
- **Serialization**: PyTorch `state_dict()` (model weights only; architecture recreated from config)

---

## 5. GAN-Based Detector

**Source**: `anomaly_detection/models/ganbased.py`
**Class**: `GANAnomalyDetector`
**Networks**: `Generator`, `Discriminator` (PyTorch `nn.Module`)
**Dependencies**: PyTorch (`torch`, `torch.nn`)

### Algorithm

The GAN-based detector trains a Generator and Discriminator adversarially on normal data. The Discriminator learns to identify real vs. fake data. During detection, anomalies score low on the Discriminator (the Discriminator identifies them as "fake" since they don't match normal patterns).

### Network Architecture

**Generator** (latent noise -> synthetic data):
```
Latent (32 dims)
  -> Linear(32, 128) -> BatchNorm1d -> LeakyReLU(0.2)
  -> Linear(128, 256) -> BatchNorm1d -> LeakyReLU(0.2)
  -> Linear(256, F) -> Tanh
```

**Discriminator** (data -> real/fake probability):
```
Input (F dims)
  -> Linear(F, 256) -> LeakyReLU(0.2) -> Dropout(0.3)
  -> Linear(256, 128) -> LeakyReLU(0.2) -> Dropout(0.3)
  -> Linear(128, 1) -> Sigmoid
```

### Training Phase

1. Normalize features to `[-1, 1]` range (for compatibility with `Tanh` activation)
2. Alternating training:
   - **Discriminator step**: Train to distinguish real data from Generator output
   - **Generator step**: Train to fool the Discriminator
3. Loss: Binary Cross-Entropy (BCE)
4. Track metrics: D_loss, G_loss, D_real_accuracy, D_fake_accuracy

### Detection Phase

1. Normalize input features using saved training statistics (`data_mean`, `data_std`)
2. Pass through the Discriminator: output in `[0, 1]` where `1.0` = real (normal)
3. Anomaly score: `score = 1.0 - discriminator_output` (higher = more anomalous)
4. Flag as anomaly if `score >= threshold`

### Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `latent_dim` | `32` | Dimension of the Generator's latent noise space |
| `generator_hidden_dims` | `[128, 256]` | Hidden layer sizes for Generator |
| `discriminator_hidden_dims` | `[256, 128]` | Hidden layer sizes for Discriminator |
| `learning_rate` | `0.0002` | Adam optimizer learning rate |
| `beta1` | `0.5` | Adam optimizer beta1 parameter |
| `epochs` | `100` | Number of adversarial training epochs |
| `batch_size` | `64` | Training batch size |
| `threshold` | `0.7` | Minimum anomaly score for classification |

### Characteristics

- **Strengths**: Can capture complex, multi-modal data distributions; no explicit density estimation needed; powerful discriminator boundary
- **Weaknesses**: Training instability (mode collapse); high computational cost; hyperparameter sensitivity; requires careful tuning
- **Computational complexity**: O(epochs * N * (G_params + D_params)) training; O(N * D_params) detection
- **Serialization**: PyTorch `state_dict()` for both Generator and Discriminator, plus training normalization statistics

---

## 6. LSTM Autoencoder

**Source**: `anomaly_detection/models/lstm_model.py`
**Class**: `LSTMModel`
**Base**: `ImprovedAnomalyDetectionModel`
**Dependencies**: TensorFlow/Keras, scikit-learn (`StandardScaler`)

### Algorithm

The LSTM Autoencoder is designed for **time-series anomaly detection**. It uses Long Short-Term Memory layers to learn temporal patterns in sequences of data. The model compresses sequences through an encoder LSTM, maps to a latent space, and reconstructs via a decoder LSTM. High reconstruction error indicates temporal anomalies.

### Network Architecture

```
Input Sequence (sequence_length x n_features)
  -> LSTM(n_features, 64, return_sequences=True)
  -> LSTM(64, 32, return_sequences=False)
  -> Dense(32, 16)                               [Latent Space]
  -> Dense(16, 32)
  -> RepeatVector(sequence_length)
  -> LSTM(32, 32, return_sequences=True)
  -> LSTM(32, 64, return_sequences=True)
  -> TimeDistributed(Dense(64, n_features))      [Sequence Reconstruction]
```

### Training Phase

1. Extract features and scale using `StandardScaler`
2. Create sliding window sequences of length `sequence_length`
3. Train the autoencoder with:
   - **Loss**: MSE between input and reconstructed sequences
   - **Optimizer**: Adam
   - **Callbacks**: Early stopping (patience=10), Learning rate reduction on plateau
4. Calculate reconstruction threshold from training data: `threshold_percentile` (default: 95th percentile of training MSE)

### Detection Phase

1. Extract features and create sequences using the same windowing
2. Reconstruct sequences via the trained autoencoder
3. Compute per-sequence MSE: `MSE = mean((input - reconstructed)^2)` across time steps and features
4. Normalize scores and flag anomalies above threshold

### Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sequence_length` | `50` | Number of time steps per input sequence |
| `hidden_dims` | `[64, 32]` | LSTM layer dimensions for encoder |
| `latent_dim` | `16` | Dimension of the latent representation |
| `dropout_rate` | `0.2` | Dropout rate between LSTM layers |
| `epochs` | `50` | Maximum training epochs |
| `batch_size` | `32` | Training batch size |
| `learning_rate` | `0.001` | Adam optimizer learning rate |
| `validation_split` | `0.2` | Fraction of data for validation during training |
| `patience` | `10` | Early stopping patience (epochs without improvement) |
| `min_delta` | `1e-4` | Minimum improvement to qualify as progress |
| `threshold_percentile` | `95` | Percentile of training errors to set as threshold |

### Characteristics

- **Strengths**: Captures temporal dependencies and sequential patterns; early stopping prevents overfitting; effective for periodic/seasonal data
- **Weaknesses**: Requires minimum `sequence_length` data points; TensorFlow dependency; model weights stored externally as `.h5` file; computationally expensive
- **Computational complexity**: O(epochs * N * sequence_length * hidden_dim^2) training
- **Serialization**: Keras `.h5` weights file + metadata JSON

---

## 7. Clustering Model

**Source**: `anomaly_detection/models/clustering_model.py`
**Class**: `ClusteringModel`
**Base**: `ImprovedAnomalyDetectionModel`
**Dependencies**: scikit-learn (`KMeans`, `DBSCAN`, `StandardScaler`, `silhouette_score`)

### Algorithm

The Clustering Model offers two algorithms that detect anomalies based on how well data points fit established cluster structure:

### 7a. K-Means Approach

**Training**: Fit K-Means to find `n_clusters` centroids. Calculate a distance threshold based on the `contamination` percentile of training distances.

**Detection**: For each data point, compute the Euclidean distance to the nearest cluster center. Normalize by the training distance threshold. Points far from all centers are anomalous.

**Scoring**:
```
distance = min(||x - c_k||) for all cluster centers c_k
score = distance / distance_threshold
```

### 7b. DBSCAN Approach

**Training**: Fit DBSCAN to identify core, border, and noise points based on density.

**Detection**: Classify new points by their relationship to existing clusters:

| Point Type | Score |
|------------|-------|
| **Noise** (no cluster) | `1.0` (maximum anomaly) |
| **Border** (near cluster edge) | `distance_to_nearest_core / eps` |
| **Core** (inside cluster) | `0.0` (normal) |

### Hyperparameters

**K-Means parameters**:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_clusters` | `8` | Number of clusters to form |
| `init_method` | `"k-means++"` | Initialization method |
| `max_iter` | `300` | Maximum iterations for convergence |
| `tol` | `1e-4` | Convergence tolerance |

**DBSCAN parameters**:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `eps` | `0.5` | Maximum distance between two samples for neighborhood |
| `min_samples` | `5` | Minimum samples in a neighborhood for core point |
| `metric` | `"euclidean"` | Distance metric |

**Common parameters**:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `algorithm` | `"kmeans"` | Clustering algorithm (`"kmeans"` or `"dbscan"`) |
| `contamination` | `0.1` | Expected anomaly fraction (used to set distance threshold) |
| `random_state` | `42` | Random seed |

### Characteristics

- **Strengths**: Interpretable (cluster membership); K-Means scales well; DBSCAN finds arbitrary-shaped clusters; silhouette score provides quality assessment
- **Weaknesses**: K-Means requires specifying cluster count; DBSCAN sensitive to `eps`/`min_samples`; both use `StandardScaler` which assumes stationary distributions
- **Computational complexity**: K-Means O(N * K * F * I); DBSCAN O(N * log(N)) with spatial indexing
- **Serialization**: Pickle (cluster model + scaler + distance threshold)

---

## 8. Ensemble Model

**Source**: `anomaly_detection/models/ensemble.py`
**Class**: `EnsembleModel`
**Dependencies**: None (orchestrates other models)

### Algorithm

The Ensemble Model combines results from multiple individual models using **weighted score averaging** with anomaly deduplication via grouping.

### Detection Flow

```
For each model in models_to_use:
    1. Run model.detect(data) independently
    2. Tag each anomaly with source_model name
    3. Collect all anomalies across models

Group anomalies by (source, timestamp, id):
    For each group:
        1. Compute weighted average:
           combined_score = sum(score_i * weight_i) / sum(weight_i)
        2. Include if combined_score >= threshold
        3. Record individual model scores in details
```

### Grouping Logic

Anomalies are grouped by a composite key of:
- `_source` or `source` from the original data
- `timestamp` from the data or anomaly
- `id` from the original data

This deduplicates the same data point detected by multiple models, producing a single combined anomaly with a weighted score.

### Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `models_to_use` | `[]` | List of model names to include in ensemble |
| `weights` | `[]` | Per-model weights (matched by index to `models_to_use`) |
| `default_weight` | `0.5` | Weight for models not in the weights list |
| `threshold` | `0.7` | Minimum combined score to include in results |

### Example Configuration

```yaml
ensemble:
  models_to_use:
    - isolation_forest_model
    - statistical_model
    - autoencoder_model
    - one_class_svm_model
  weights: [0.7, 0.5, 0.8, 0.6]
  threshold: 0.7
```

### Characteristics

- **Strengths**: Robust to individual model failures (catches exceptions per model); reduces false positives through consensus; flexible weighting
- **Weaknesses**: No voting mechanism (purely score-based); grouping by timestamp can fail if timestamps differ slightly; not a trained model itself
- **Note**: The Ensemble does not require training. It delegates `train()` as a no-op and relies on its constituent models being trained independently.

---

## Score Normalization

All models normalize raw anomaly scores to the `[0, 1]` range before applying the threshold. The system uses four normalization strategies:

### Min-Max Normalization (Statistical, Isolation Forest, Autoencoder)

```
normalized = (score - min) / (max - min)
```

Applied per-batch. Handles edge cases:
- If `max - min < 1e-10`: returns `1.0` if max > 0, else `0.0`
- NaN/Inf values replaced with `0.0` / `1.0` / `0.0` respectively
- Output clipped to `[0, 1]`

### Sigmoid Normalization (One-Class SVM)

```
normalized = 1 / (1 + exp(-raw_score))
```

Maps the full real line to `(0, 1)`. Natural fit for models that produce signed distance values.

### Discriminator Output (GAN)

```
score = 1.0 - discriminator_output
```

Discriminator already outputs `[0, 1]` via Sigmoid; inversion maps high "realness" to low anomaly score.

### Reconstruction Error (LSTM)

```
score = normalize(MSE(input, reconstruction))
```

Uses min-max normalization on per-sequence MSE values. Training establishes a threshold at the configured percentile.

---

## Feature Engineering

The system extracts features at multiple levels before feeding data to models. All feature engineering is in `anomaly_detection/processors/`.

### General Features (`feature_extractor.py`)

| Feature Type | Prefix | Method |
|-------------|--------|--------|
| Numerical | `num_` | Direct value, NaN for missing |
| Boolean | `bool_` | Cast to `0.0` / `1.0` |
| Categorical | `cat_` | Label encoding (sorted mapping) or hash encoding (`hash % 10000`) |
| Text | `text_` | SentenceTransformer embeddings (384-dim, `all-MiniLM-L6-v2`) or statistical fallback |
| Temporal | `time_` | Hour, day of week, day of month, month, weekend indicator, business hours |

**Imputation strategies**: Mean, Median (default), Mode, KNN (k=5), Constant (0.0)

### Network Features (`network_feature_extractor.py`)

| Feature Type | Details |
|-------------|---------|
| IP Address | IPv4/IPv6 classification, private/loopback/multicast detection, octet values |
| Port | Well-known/registered/dynamic classification, common service detection (10 ports) |
| Protocol | TCP/UDP/ICMP/HTTP/DNS mapping, transport vs application layer |
| Traffic | Log-transformed byte/packet counts, average packet size, duration |
| Geographic | GeoIP2 country/city lookup (optional) |

### Time-Series Features (`time_series_feature_extractor.py`)

| Category | Features |
|----------|----------|
| Statistical | Mean, median, std, range, percentiles (25/50/75/90/95/99), skewness, kurtosis |
| Trend | Linear slope, intercept, R-squared, acceleration (2nd-order polynomial), trend change |
| Volatility | Mean/std/max of absolute differences, coefficient of variation, rate of change |
| Seasonality | FFT top-5 frequency components with period and strength (requires min 24 points) |
| Change Point | Simple (half-split mean comparison) or PELT algorithm via `ruptures` library |
| Rolling Windows | Mean, std, slope for configurable window sizes (default: 10, 30, 60, 120) |

---

## Algorithm Selection Guide

| Scenario | Recommended Model(s) | Rationale |
|----------|----------------------|-----------|
| Quick baseline / interpretable results | Statistical | Fast, no dependencies, easy to explain |
| General-purpose anomaly detection | Isolation Forest | Robust, scalable, no distribution assumptions |
| High-dimensional feature spaces | One-Class SVM, Isolation Forest | Both handle high dimensions well |
| Complex non-linear patterns | Autoencoder | Learns non-linear feature interactions |
| Multi-modal data distributions | GAN | Captures complex distributional shapes |
| Time-series / sequential data | LSTM | Captures temporal dependencies |
| Cluster-based anomalies | Clustering (K-Means/DBSCAN) | Natural for data with group structure |
| Production / maximum robustness | Ensemble | Combines multiple models, reduces false positives |

### Model Comparison

| Model | Training Speed | Detection Speed | Interpretability | External Deps |
|-------|---------------|----------------|-------------------|---------------|
| Statistical | Very Fast | Very Fast | High | None |
| Isolation Forest | Fast | Fast | Medium | scikit-learn |
| One-Class SVM | Slow (large N) | Fast | Low | scikit-learn |
| Autoencoder | Moderate | Fast | Low | PyTorch |
| GAN | Slow | Fast | Low | PyTorch |
| LSTM | Slow | Moderate | Low | TensorFlow |
| Clustering | Moderate | Fast | High | scikit-learn |
| Ensemble | N/A (delegates) | Sum of models | Medium | None |
