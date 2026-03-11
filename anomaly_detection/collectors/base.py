"""
Base classes for data collectors.

This module defines abstract base classes for data collectors used by
the anomaly detection system.
"""

import abc
import logging
from typing import Dict, List, Any, Optional


class Collector(abc.ABC):
    """
    Abstract base class for data collectors.
    
    A collector is responsible for gathering data from a specific source
    for processing and analysis.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize collector with a name and configuration.
        
        Args:
            name: Collector name
            config: Collector configuration
        """
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"collector.{name}")
    
    @abc.abstractmethod
    def collect(self) -> List[Dict[str, Any]]:
        """
        Collect data from the configured source.
        
        Returns:
            List of collected data items as dictionaries
        """
        pass


class CollectorFactory:
    """
    Factory class for creating collectors based on configuration.
    """
    
    def __init__(self, collector_config: Dict[str, Any], storage_manager=None):
        """
        Initialize collector factory with configuration.
        
        Args:
            collector_config: Collector configuration dictionary
            storage_manager: Optional storage manager for persistence
        """
        self.config = collector_config
        self.storage_manager = storage_manager
        self.logger = logging.getLogger("CollectorFactory")
    
    def create_collectors(self) -> List[Collector]:
        """
        Create collectors based on configuration.
        
        Returns:
            List of configured collectors
        """
        enabled_collectors = self.config.get("enabled", [])
        collectors = []
        
        if "all" in enabled_collectors:
            enabled_collectors = [c for c in self.config.keys() if c != "enabled"]
        
        self.logger.info(f"Creating collectors for: {enabled_collectors}")
        
        # Import collector implementations here to avoid circular imports
        collector_classes = {}
        
        try:
            from anomaly_detection.collectors.kafka_collector import KafkaCollector
            collector_classes["kafka"] = KafkaCollector
        except ImportError as e:
            self.logger.warning(f"Could not import KafkaCollector: {e}")
        
        try:
            from anomaly_detection.collectors.file_collector import FileCollector
            collector_classes["file"] = FileCollector
        except ImportError as e:
            self.logger.warning(f"Could not import FileCollector: {e}")
        
        try:
            from anomaly_detection.collectors.sql_collector import SQLCollector
            collector_classes["sql"] = SQLCollector
        except ImportError as e:
            self.logger.warning(f"Could not import SQLCollector: {e}")
        
        try:
            from anomaly_detection.collectors.rest_api_collector import RestApiCollector
            collector_classes["rest_api"] = RestApiCollector
        except ImportError as e:
            self.logger.warning(f"Could not import RestApiCollector: {e}")
        
        # Create enabled collectors
        for collector_type in enabled_collectors:
            if collector_type in self.config and collector_type in collector_classes:
                collector_config = self.config[collector_type]
                collector_class = collector_classes[collector_type]
                
                try:
                    collector = collector_class(
                        name=f"{collector_type}_collector",
                        config=collector_config,
                        storage_manager=self.storage_manager
                    )
                    collectors.append(collector)
                    self.logger.info(f"Created {collector_type} collector")
                except Exception as e:
                    self.logger.error(f"Error creating {collector_type} collector: {e}")
            elif collector_type not in collector_classes:
                self.logger.warning(f"Collector type '{collector_type}' not available")
            elif collector_type not in self.config:
                self.logger.warning(f"No configuration found for collector type '{collector_type}'")
        
        self.logger.info(f"Created {len(collectors)} collectors")
        return collectors