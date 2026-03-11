"""
Time Series Feature Extractor for Anomaly Detection System

Specialized feature extractor for time series data with trend analysis,
seasonality detection, and statistical features.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from anomaly_detection.processors.base import Processor


class TimeSeriesFeatureExtractor(Processor):
    """
    Specialized feature extractor for time series data.

    Extracts features for time series anomaly detection including:
    - Statistical features (mean, std, percentiles)
    - Trend analysis (slope, acceleration)
    - Seasonality features (FFT, autocorrelation)
    - Change point detection
    - Volatility measures
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        super().__init__(name, config)
        self.storage_manager = storage_manager

        # Time series configuration
        self.time_field = config.get("time_field", "timestamp")
        self.value_field = config.get("value_field", "value")
        self.group_by_field = config.get("group_by_field")  # Optional grouping field

        # Window configuration
        self.window_sizes = config.get("window_sizes", [10, 30, 60, 120])  # In time units
        self.window_unit = config.get("window_unit", "minutes")  # seconds, minutes, hours, days
        self.min_window_size = config.get("min_window_size", 5)

        # Feature extraction options
        self.extract_statistical = config.get("extract_statistical", True)
        self.extract_trend = config.get("extract_trend", True)
        self.extract_seasonal = config.get("extract_seasonal", False)  # Requires more data
        self.extract_volatility = config.get("extract_volatility", True)
        self.extract_change_points = config.get("extract_change_points", True)

        # Statistical features
        self.percentiles = config.get("percentiles", [25, 50, 75, 90, 95, 99])

        # Trend analysis
        self.trend_window = config.get("trend_window", 20)
        self.trend_poly_order = config.get("trend_poly_order", 2)

        # Seasonal analysis (FFT)
        self.fft_components = config.get("fft_components", 5)
        self.seasonal_min_periods = config.get("seasonal_min_periods", 24)  # Minimum data points

        # Change point detection
        self.change_point_method = config.get("change_point_method", "simple")  # simple, ruptures
        self.change_point_threshold = config.get("change_point_threshold", 2.0)

        # Rolling statistics cache for efficiency
        self.series_cache = {}
        self.cache_max_size = config.get("cache_max_size", 1000)

        self.logger.info(f"Initialized Time Series Feature Extractor with windows: {self.window_sizes}")

    def process(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract time series features from data.

        Args:
            data: List of time series data points

        Returns:
            List of data items with extracted time series features
        """
        # Group data by series if grouping field is specified
        if self.group_by_field:
            grouped_data = self._group_by_series(data)
        else:
            grouped_data = {"default": data}

        processed_data = []

        for series_key, series_data in grouped_data.items():
            try:
                # Sort by time
                sorted_data = self._sort_by_time(series_data)

                if len(sorted_data) < self.min_window_size:
                    self.logger.warning(f"Series {series_key} has insufficient data ({len(sorted_data)} points)")
                    continue

                # Extract features for each point in the series
                for i, item in enumerate(sorted_data):
                    # Get available historical data up to current point
                    historical_data = sorted_data[:i+1]

                    # Extract features
                    ts_features = self._extract_time_series_features(historical_data, series_key)

                    # Add features to item
                    if "features" in item:
                        item["features"].update(ts_features)
                    else:
                        item["features"] = ts_features

                    item["time_series_features"] = ts_features
                    processed_data.append(item)

            except Exception as e:
                self.logger.error(f"Error processing series {series_key}: {e}")

        self.logger.info(f"Extracted time series features for {len(processed_data)} data points")
        return processed_data

    def _group_by_series(self, data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group data by series identifier."""
        grouped = defaultdict(list)

        for item in data:
            group_key = item.get(self.group_by_field, "default")
            grouped[str(group_key)].append(item)

        return dict(grouped)

    def _sort_by_time(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort data by timestamp."""
        def get_timestamp(item):
            timestamp_str = item.get(self.time_field, item.get("timestamp", ""))
            try:
                if isinstance(timestamp_str, str):
                    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                elif isinstance(timestamp_str, (int, float)):
                    return datetime.fromtimestamp(timestamp_str)
                else:
                    return datetime.min
            except Exception:
                return datetime.min

        return sorted(data, key=get_timestamp)

    def _extract_time_series_features(self, historical_data: List[Dict[str, Any]],
                                    series_key: str) -> Dict[str, float]:
        """Extract time series features from historical data."""
        features = {}

        if len(historical_data) < self.min_window_size:
            return features

        # Extract values
        values = self._extract_values(historical_data)
        if len(values) < self.min_window_size:
            return features

        # Statistical features
        if self.extract_statistical:
            features.update(self._extract_statistical_features(values))

        # Trend features
        if self.extract_trend and len(values) >= self.trend_window:
            features.update(self._extract_trend_features(values))

        # Volatility features
        if self.extract_volatility:
            features.update(self._extract_volatility_features(values))

        # Seasonal features (requires more data)
        if self.extract_seasonal and len(values) >= self.seasonal_min_periods:
            features.update(self._extract_seasonal_features(values))

        # Change point features
        if self.extract_change_points and len(values) >= self.min_window_size:
            features.update(self._extract_change_point_features(values))

        # Rolling window features
        features.update(self._extract_rolling_features(values))

        return features

    def _extract_values(self, data: List[Dict[str, Any]]) -> np.ndarray:
        """Extract numeric values from data."""
        values = []
        for item in data:
            try:
                value = float(item.get(self.value_field, item.get("value", 0)))
                values.append(value)
            except (ValueError, TypeError, KeyError):
                continue
        return np.array(values)

    def _extract_statistical_features(self, values: np.ndarray) -> Dict[str, float]:
        """Extract basic statistical features."""
        features = {}

        if len(values) == 0:
            return features

        # Basic statistics
        features["ts_mean"] = float(np.mean(values))
        features["ts_std"] = float(np.std(values))
        features["ts_min"] = float(np.min(values))
        features["ts_max"] = float(np.max(values))
        features["ts_median"] = float(np.median(values))
        features["ts_range"] = float(np.max(values) - np.min(values))

        # Percentiles
        for p in self.percentiles:
            features[f"ts_p{p}"] = float(np.percentile(values, p))

        # Distribution features
        features["ts_skewness"] = float(self._calculate_skewness(values))
        features["ts_kurtosis"] = float(self._calculate_kurtosis(values))

        # Recent vs historical comparison
        if len(values) > 10:
            recent = values[-10:]
            historical = values[:-10]
            features["ts_recent_mean_ratio"] = float(np.mean(recent) / max(np.mean(historical), 1e-6))
            features["ts_recent_std_ratio"] = float(np.std(recent) / max(np.std(historical), 1e-6))

        return features

    def _extract_trend_features(self, values: np.ndarray) -> Dict[str, float]:
        """Extract trend and slope features."""
        features = {}

        if len(values) < 3:
            return features

        # Linear trend (slope)
        x = np.arange(len(values))
        try:
            slope, intercept = np.polyfit(x, values, 1)
            features["ts_trend_slope"] = float(slope)
            features["ts_trend_intercept"] = float(intercept)

            # Trend strength (R-squared)
            y_pred = slope * x + intercept
            ss_res = np.sum((values - y_pred) ** 2)
            ss_tot = np.sum((values - np.mean(values)) ** 2)
            r_squared = 1 - (ss_res / max(ss_tot, 1e-6))
            features["ts_trend_r_squared"] = float(r_squared)

        except np.linalg.LinAlgError:
            features["ts_trend_slope"] = 0.0
            features["ts_trend_r_squared"] = 0.0

        # Polynomial trend (acceleration)
        if len(values) >= 5:
            try:
                coeffs = np.polyfit(x, values, self.trend_poly_order)
                features["ts_acceleration"] = float(coeffs[-3]) if len(coeffs) >= 3 else 0.0
            except np.linalg.LinAlgError:
                features["ts_acceleration"] = 0.0

        # Recent trend vs overall trend
        if len(values) > 20:
            recent_trend = values[-10:]
            overall_trend = values[-20:]
            x_recent = np.arange(len(recent_trend))
            x_overall = np.arange(len(overall_trend))

            try:
                recent_slope = np.polyfit(x_recent, recent_trend, 1)[0]
                overall_slope = np.polyfit(x_overall, overall_trend, 1)[0]
                features["ts_trend_change"] = float(recent_slope - overall_slope)
            except np.linalg.LinAlgError:
                features["ts_trend_change"] = 0.0

        return features

    def _extract_volatility_features(self, values: np.ndarray) -> Dict[str, float]:
        """Extract volatility and variation features."""
        features = {}

        if len(values) < 3:
            return features

        # Absolute differences (volatility)
        diffs = np.abs(np.diff(values))
        features["ts_volatility_mean"] = float(np.mean(diffs))
        features["ts_volatility_std"] = float(np.std(diffs))
        features["ts_volatility_max"] = float(np.max(diffs))

        # Coefficient of variation
        mean_val = np.mean(values)
        if mean_val != 0:
            features["ts_coefficient_variation"] = float(np.std(values) / abs(mean_val))

        # Rate of change
        if len(values) > 1:
            roc = np.diff(values) / values[:-1]
            features["ts_roc_mean"] = float(np.mean(np.abs(roc)))
            features["ts_roc_std"] = float(np.std(roc))

        # Local volatility (rolling standard deviation)
        if len(values) >= 10:
            rolling_std = pd.Series(values).rolling(window=10).std()
            features["ts_local_volatility"] = float(rolling_std.iloc[-1])

        return features

    def _extract_seasonal_features(self, values: np.ndarray) -> Dict[str, float]:
        """Extract seasonal/periodic features using FFT."""
        features = {}

        if len(values) < self.seasonal_min_periods:
            return features

        try:
            # Fast Fourier Transform
            fft = np.fft.fft(values)
            freqs = np.fft.fftfreq(len(values))

            # Get magnitude spectrum
            magnitude = np.abs(fft)

            # Find dominant frequencies (excluding DC component)
            positive_freq_idx = freqs > 0
            sorted_indices = np.argsort(magnitude[positive_freq_idx])[::-1]

            # Extract top frequency components
            for i in range(min(self.fft_components, len(sorted_indices))):
                idx = sorted_indices[i]
                actual_idx = np.where(positive_freq_idx)[0][idx]

                freq = freqs[actual_idx]
                mag = magnitude[actual_idx]

                # Convert frequency to period
                if freq > 0:
                    period = 1.0 / freq
                    features[f"ts_seasonal_period_{i+1}"] = float(period)
                    features[f"ts_seasonal_strength_{i+1}"] = float(mag / len(values))

        except Exception as e:
            self.logger.debug(f"FFT seasonal analysis failed: {e}")

        return features

    def _extract_change_point_features(self, values: np.ndarray) -> Dict[str, float]:
        """Extract change point detection features."""
        features = {}

        if len(values) < self.min_window_size:
            return features

        if self.change_point_method == "simple":
            # Simple change point detection based on mean differences
            features.update(self._simple_change_point_detection(values))
        elif self.change_point_method == "ruptures":
            # Advanced change point detection using ruptures library
            features.update(self._ruptures_change_point_detection(values))

        return features

    def _simple_change_point_detection(self, values: np.ndarray) -> Dict[str, float]:
        """Simple change point detection based on statistical properties."""
        features = {}

        if len(values) < 10:
            return features

        # Split into two halves and compare statistics
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]

        first_mean, first_std = np.mean(first_half), np.std(first_half)
        second_mean, second_std = np.mean(second_half), np.std(second_half)

        # Change in mean
        mean_change = abs(second_mean - first_mean)
        features["ts_change_point_mean_diff"] = float(mean_change)

        # Normalized change
        if first_std > 0:
            features["ts_change_point_mean_zscore"] = float(mean_change / first_std)
        else:
            features["ts_change_point_mean_zscore"] = float(mean_change)

        # Check if change exceeds threshold
        features["ts_has_change_point"] = float(mean_change > self.change_point_threshold)

        return features

    def _ruptures_change_point_detection(self, values: np.ndarray) -> Dict[str, float]:
        """Advanced change point detection using ruptures library."""
        features = {}

        try:
            import ruptures as rpt

            # Use PELT (Pruned Exact Linear Time) algorithm
            algo = rpt.Pelt(model="rbf").fit(values)
            change_points = algo.predict(pen=10)

            features["ts_change_points_count"] = len(change_points) - 1  # Last element is end
            features["ts_change_points_density"] = len(change_points) / len(values)

            # Distance to nearest change point
            if change_points:
                current_pos = len(values)
                distances = [abs(cp - current_pos) for cp in change_points[:-1]]
                if distances:
                    features["ts_distance_to_change_point"] = min(distances)

        except ImportError:
            self.logger.debug("ruptures library not available for advanced change point detection")
        except Exception as e:
            self.logger.debug(f"Ruptures change point detection failed: {e}")

        return features

    def _extract_rolling_features(self, values: np.ndarray) -> Dict[str, float]:
        """Extract rolling window features."""
        features = {}

        # Rolling statistics for different window sizes
        for window in self.window_sizes:
            if len(values) >= window:
                rolling_values = values[-window:]

                features[f"ts_rolling_mean_{window}"] = float(np.mean(rolling_values))
                features[f"ts_rolling_std_{window}"] = float(np.std(rolling_values))

                # Rolling trend
                if window >= 5:
                    x = np.arange(window)
                    try:
                        slope = np.polyfit(x, rolling_values, 1)[0]
                        features[f"ts_rolling_slope_{window}"] = float(slope)
                    except np.linalg.LinAlgError:
                        features[f"ts_rolling_slope_{window}"] = 0.0

        return features

    def _calculate_skewness(self, values: np.ndarray) -> float:
        """Calculate skewness of the data."""
        if len(values) < 3:
            return 0.0

        mean_val = np.mean(values)
        std_val = np.std(values)

        if std_val == 0:
            return 0.0

        return float(np.mean(((values - mean_val) / std_val) ** 3))

    def _calculate_kurtosis(self, values: np.ndarray) -> float:
        """Calculate kurtosis of the data."""
        if len(values) < 4:
            return 0.0

        mean_val = np.mean(values)
        std_val = np.std(values)

        if std_val == 0:
            return 0.0

        return float(np.mean(((values - mean_val) / std_val) ** 4) - 3)
