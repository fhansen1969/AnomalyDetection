"""
Configuration helper functions for the Anomaly Detection Dashboard.
Handles loading and accessing configuration from YAML file.
"""

import os
import yaml
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_project_root():
    """Get the absolute path to the project root directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    return project_root

def load_config():
    """Load configuration from YAML file.
    
    Returns:
        dict: Configuration dictionary or None if error
    """
    config_path = os.path.join(get_project_root(), '../config', 'config.yaml')
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            logger.info(f"Configuration loaded successfully from {config_path}")
            return config
    except FileNotFoundError:
        logger.error(f"Config file not found at {config_path}")
        return None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading config: {e}")
        return None

def get_config_value(key_path, default=None):
    """Get a configuration value using a dot-notation path.
    
    Args:
        key_path (str): Dot-notation path to the config value (e.g., 'database.connection.host')
        default: Default value to return if path not found
        
    Returns:
        The configuration value or default if not found
    """
    config = load_config()
    
    if not config:
        return default
    
    # Start with full config under 'config' key
    current = config.get('config', {})
    
    # Split the path and traverse the config
    keys = key_path.split('.')
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current

def get_database_config():
    """Get database configuration.
    
    Returns:
        dict: Database configuration or default if not found
    """
    default_config = {
        "host": "localhost",
        "port": 5432,
        "database": "anomaly_detection",
        "user": "anomaly_user",
        "password": "St@rW@rs!"
    }
    
    db_config = get_config_value('database.connection')
    
    if not db_config:
        logger.warning("Using default database configuration")
        return default_config
    
    return db_config

def get_models_config():
    """Get models configuration.
    
    Returns:
        dict: Models configuration or empty dict if not found
    """
    return get_config_value('models', {})

def get_agents_config():
    """Get agents configuration.
    
    Returns:
        dict: Agents configuration or empty dict if not found
    """
    return get_config_value('agents', {})

def get_system_config():
    """Get system configuration.
    
    Returns:
        dict: System configuration or default if not found
    """
    default_config = {
        "log_level": "INFO",
        "name": "Anomaly Detection System",
        "output_dir": "results"
    }
    
    system_config = get_config_value('system')
    
    if not system_config:
        logger.warning("Using default system configuration")
        return default_config
    
    return system_config
