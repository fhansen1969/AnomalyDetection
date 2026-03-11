"""
Processor package initialization.

This module imports and exports processor components.
"""

from anomaly_detection.processors.base import Processor, ProcessorFactory
from anomaly_detection.processors.normalizer import Normalizer
from anomaly_detection.processors.feature_extractor import FeatureExtractor

__all__ = [
    'Processor',
    'ProcessorFactory',
    'Normalizer',
    'FeatureExtractor'
]
