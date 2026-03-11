"""
Configuration module for the anomaly detection system.

This module provides functionality to manage system configuration,
including loading, validating, and accessing configuration parameters.
"""

import os
import yaml
import logging
from typing import Dict, Any, List, Optional
import shutil
from pathlib import Path


class Config:
    """
    Configuration class that holds and validates system settings.
    
    Attributes:
        config (Dict): The complete configuration dictionary
        system (Dict): System-level configuration
        collectors (Dict): Data collector configuration
        processors (Dict): Data processor configuration
        models (Dict): Machine learning model configuration
        agents (Dict): LangGraph agent configuration
        database (Dict): Database and vector store configuration
        knowledge_base (Dict): Knowledge base configuration
        alerts (Dict): Alert system configuration
    """
    
    def __init__(self, config_dict: Dict[str, Any]):
      """
      Initialize configuration object from a dictionary.
      
      Args:
          config_dict: Configuration as a dictionary
      """
      # Ensure config_dict is not None
      self.config = config_dict if config_dict is not None else {}
      self.validate()
      
      # Extract specific sections for easier access
      self.system = self.config.get("system", {})
      self.collectors = self.config.get("collectors", {})
      self.processors = self.config.get("processors", {})
      self.models = self.config.get("models", {})
      self.agents = self.config.get("agents", {})
      self.database = self.config.get("database", {})
      self.knowledge_base = self.config.get("knowledge_base", {})
      self.alerts = self.config.get("alerts", {})
    
    def validate(self) -> None:
      """
      Validate configuration structure and required fields.
      
      Raises:
          ValueError: If configuration is invalid
      """
      # Ensure self.config is a dictionary
      if not isinstance(self.config, dict):
          self.config = {}
          
      # Check required top-level sections
      required_sections = [
          "system", "collectors", "processors", "models", 
          "agents", "database", "alerts"
      ]
      
      # Initialize missing sections
      for section in required_sections:
          if section not in self.config:
              self.config[section] = {}
      
      # Validate system configuration
      if "name" not in self.config["system"]:
          self.config["system"]["name"] = "Anomaly Detection System"
      
      if "log_level" not in self.config["system"]:
          self.config["system"]["log_level"] = "INFO"
      
      if "output_dir" not in self.config["system"]:
          self.config["system"]["output_dir"] = "results"
      
      # Validate collectors configuration
      if "enabled" not in self.config["collectors"]:
          self.config["collectors"]["enabled"] = ["file"]
      
      # Validate models configuration
      if "enabled" not in self.config["models"]:
          self.config["models"]["enabled"] = []
      
      # Additional validation could be added for specific sections
      logging.debug("Configuration validated successfully")
        
def get(self, section: str, option: str, default: Any = None) -> Any:
    """
    Get a configuration value with a dot-separated path.
    
    Args:
        section: Top-level configuration section
        option: Option name within the section
        default: Default value if option not found
        
    Returns:
        Configuration value or default value
    """
    if section not in self.config:
        return default
    
    if option not in self.config[section]:
        return default
    
    return self.config[section][option]


def create_default_config(config_path: str) -> None:
    """
    Create a default configuration file.
    
    Args:
        config_path: Path where to create the configuration file
    """
    default_config_content = """
# Anomaly Detection System Configuration

# System settings
system:
  name: "Security Anomaly Detection System"
  version: "1.0.0"
  log_level: "INFO"
  output_dir: "results"

# Data Collection Configuration
collectors:
  enabled:
    - "file"
  
  kafka:
    bootstrap_servers: "localhost:9092"
    topics:
      - name: "security_events"
        group_id: "anomaly_detection_group"
    consumer_timeout_ms: 5000
    batch_size: 100
  
  file:
    paths:
      - "./data/sample/*.json"
    watch_interval_seconds: 60
    batch_size: 1000

# Data Processing Configuration
processors:
  normalizers:
    - name: "json_normalizer"
      type: "json"
      timestamp_field: "timestamp"
  
  feature_extractors:
    - name: "basic_features"
      fields: ["*"]

# Machine Learning Models Configuration
models:
  enabled:
    - "isolation_forest"
  
  isolation_forest:
    n_estimators: 100
    contamination: 0.01
    random_state: 42

# LangGraph Agent Configuration
agents:
  llm:
    provider: "ollama"
    base_url: "http://localhost:11434/api"
    model: "mistral"

# Database Configuration
database:
  type: "postgresql"
  connection:
    host: "localhost"
    port: 5432
    database: "anomaly_detection"
    user: "postgres"
    password: "postgres"

# Alert Configuration
alerts:
  enabled: true
  threshold: 0.75
  types:
    - name: "console"
      enabled: true
"""
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    # Write default configuration file
    with open(config_path, "w") as f:
        f.write(default_config_content)
    
    logging.info(f"Created default configuration at {config_path}")