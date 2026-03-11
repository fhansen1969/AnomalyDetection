"""
Base classes for data processors.

This module defines abstract base classes for data processors used by 
the anomaly detection system.
"""

import abc
import logging
from typing import Dict, List, Any, Optional


class Processor(abc.ABC):
    """
    Abstract base class for data processors.
    
    A processor is responsible for transforming raw data into a format
    suitable for analysis, including normalization, feature extraction, etc.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize processor with a name and configuration.
        
        Args:
            name: Processor name
            config: Processor configuration
        """
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"processor.{name}")
    
    @abc.abstractmethod
    def process(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process input data.
        
        Args:
            data: List of input data items
            
        Returns:
            List of processed data items
        """
        pass


class ProcessorFactory:
    """
    Factory class for creating processors based on configuration.
    """
    
    def __init__(self, processor_config: Dict[str, Any], storage_manager=None):
        """
        Initialize processor factory with configuration.
        
        Args:
            processor_config: Processor configuration dictionary
            storage_manager: Optional storage manager for persistence
        """
        self.config = processor_config
        self.storage_manager = storage_manager
    
    def create_processors(self) -> List[Processor]:
        """
        Create processors based on configuration.
        
        Returns:
            List of configured processors
        """
        processors = []
        
        # Import processor implementations here to avoid circular imports
        from anomaly_detection.processors.normalizer import Normalizer
        from anomaly_detection.processors.feature_extractor import FeatureExtractor
        
        # Create normalizers
        for normalizer_config in self.config.get("normalizers", []):
            name = normalizer_config.get("name", "normalizer")
            processors.append(Normalizer(name, normalizer_config, self.storage_manager))
        
        # Create feature extractors
        for extractor_config in self.config.get("feature_extractors", []):
            name = extractor_config.get("name", "feature_extractor")
            processors.append(FeatureExtractor(name, extractor_config, self.storage_manager))
        
        return processors
