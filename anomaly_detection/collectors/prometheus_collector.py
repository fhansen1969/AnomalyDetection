"""
Prometheus Collector for Anomaly Detection System

Collects metrics from Prometheus endpoints for anomaly detection.
"""

import requests
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from anomaly_detection.collectors.base import Collector


class PrometheusCollector(Collector):
    """
    Collector for Prometheus metrics endpoints.

    Queries Prometheus for metrics data and formats it for anomaly detection.
    """

    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        super().__init__(name, config)
        self.storage_manager = storage_manager

        # Prometheus configuration
        self.endpoint = config.get("endpoint", "http://localhost:9090")
        self.metrics = config.get("metrics", [])
        self.query_range = config.get("query_range_hours", 1)
        self.step_seconds = config.get("step_seconds", 60)

        # Authentication (optional)
        self.username = config.get("username")
        self.password = config.get("password")
        self.bearer_token = config.get("bearer_token")

        self.logger.info(f"Initialized Prometheus collector for {self.endpoint}")

    def collect(self) -> List[Dict[str, Any]]:
        """
        Collect metrics from Prometheus.

        Returns:
            List of metric data points formatted for anomaly detection
        """
        results = []

        for metric_config in self.metrics:
            metric_name = metric_config.get("name")
            query = metric_config.get("query")

            if not metric_name or not query:
                self.logger.warning(f"Invalid metric config: {metric_config}")
                continue

            try:
                metric_data = self._query_metric(query, metric_name)
                results.extend(metric_data)
            except Exception as e:
                self.logger.error(f"Error collecting metric {metric_name}: {e}")

        self.logger.info(f"Collected {len(results)} metric data points")
        return results

    def _query_metric(self, query: str, metric_name: str) -> List[Dict[str, Any]]:
        """Query a single metric from Prometheus."""
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=self.query_range)

        params = {
            "query": query,
            "start": start_time.timestamp(),
            "end": end_time.timestamp(),
            "step": self.step_seconds
        }

        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        auth = (self.username, self.password) if self.username and self.password else None

        response = requests.get(
            f"{self.endpoint}/api/v1/query_range",
            params=params,
            headers=headers,
            auth=auth
        )

        if response.status_code != 200:
            raise Exception(f"Prometheus query failed: {response.text}")

        data = response.json()

        # Format results for anomaly detection
        results = []
        for result in data.get("data", {}).get("result", []):
            metric_labels = result.get("metric", {})
            values = result.get("values", [])

            for timestamp, value in values:
                try:
                    # Convert timestamp and value
                    dt = datetime.fromtimestamp(timestamp)
                    numeric_value = float(value)

                    data_point = {
                        "metric_name": metric_name,
                        "value": numeric_value,
                        "timestamp": dt.isoformat(),
                        "_source": {
                            "collector": self.name,
                            "type": "prometheus",
                            "endpoint": self.endpoint
                        }
                    }

                    # Add metric labels as additional fields
                    for label, label_value in metric_labels.items():
                        data_point[f"label_{label}"] = label_value

                    results.append(data_point)

                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid value in metric {metric_name}: {value}")

        return results
