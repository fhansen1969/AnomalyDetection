"""
Utility functions for the anomaly detection system.

This module provides common utility functions used throughout the system.
"""

import logging
import json
import os
import sys
import datetime
from typing import Dict, Any, Optional


def setup_logging(config: Dict[str, Any]) -> None:
    """
    Set up logging for the system.
    
    Args:
        config: System configuration
    """
    log_level_str = config.get("log_level", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('anomaly_detection.log')
        ]
    )
    
    # Set up specific loggers
    loggers = [
        "collector", "processor", "model", "storage_manager", 
        "agent_manager", "alert_manager"
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)
    
    logging.info(f"Logging initialized at level {log_level_str}")


def save_json(data: Any, file_path: str, indent: int = 2) -> None:
    """
    Save data to a JSON file.
    
    Args:
        data: Data to save
        file_path: Path to save file
        indent: JSON indentation level
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Custom JSON encoder for handling dates and special types
    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            return super().default(obj)
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=indent, cls=CustomJSONEncoder)


def load_json(file_path: str) -> Optional[Any]:
    """
    Load data from a JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Loaded data or None if file doesn't exist or is invalid
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON file: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Error loading JSON file {file_path}: {str(e)}")
        return None


def format_timestamp(timestamp: Optional[str] = None, 
                    format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a timestamp string.
    
    Args:
        timestamp: ISO format timestamp string or None for current time
        format_str: Output format string
        
    Returns:
        Formatted timestamp string
    """
    if timestamp is None:
        dt = datetime.datetime.utcnow()
    else:
        try:
            dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            dt = datetime.datetime.utcnow()
    
    return dt.strftime(format_str)


def parse_timestamp(timestamp_str: str, 
                   formats: Optional[list] = None) -> Optional[datetime.datetime]:
    """
    Parse a timestamp string using multiple possible formats.
    
    Args:
        timestamp_str: Timestamp string
        formats: List of format strings to try
        
    Returns:
        Datetime object or None if parsing fails
    """
    if not formats:
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y%m%d%H%M%S",
            "%Y-%m-%d"
        ]
    
    for fmt in formats:
        try:
            return datetime.datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue
    
    return None


def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def generate_id(prefix: str = "id") -> str:
    """
    Generate a unique ID with timestamp.
    
    Args:
        prefix: ID prefix
        
    Returns:
        Unique ID string
    """
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{timestamp}"
