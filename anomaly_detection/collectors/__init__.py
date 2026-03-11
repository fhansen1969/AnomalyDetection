"""
Collector package initialization.

This module imports and exports collector components.
"""

from anomaly_detection.collectors.base import Collector, CollectorFactory
from anomaly_detection.collectors.kafka_collector import KafkaCollector
from anomaly_detection.collectors.file_collector import FileCollector

__all__ = [
    'Collector',
    'CollectorFactory',
    'KafkaCollector',
    'FileCollector'
]
