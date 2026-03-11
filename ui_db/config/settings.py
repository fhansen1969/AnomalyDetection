"""
Configuration settings and constants for the Anomaly Detection Dashboard.
"""

import os
import sys
import yaml
import streamlit as st
import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path to fix module imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Load configuration from YAML file
def load_config():
    """Load configuration from YAML file."""
    config_path = os.path.join(project_root, '../config', 'config.yaml')
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except Exception as e:
        logger.error(f"Error loading config file: {e}")
        return None

# Get configuration
CONFIG = load_config()

# Default API URL
API_URL = "http://localhost:8000"

# Database Configuration
if CONFIG and 'config' in CONFIG and 'database' in CONFIG['config'] and 'connection' in CONFIG['config']['database']:
    DB_CONFIG = CONFIG['config']['database']['connection']
    logger.info("Loaded database configuration from config.yaml")
else:
    logger.warning("Using default database configuration")
    DB_CONFIG = {
        "host": "localhost",
        "port": 5432,
        "database": "anomaly_detection",
        "user": "anomaly_user",
        "password": "St@rW@rs!"
    }

# Models Configuration
if CONFIG and 'config' in CONFIG and 'models' in CONFIG['config']:
    MODELS_CONFIG = CONFIG['config']['models']
    logger.info("Loaded models configuration from config.yaml")
else:
    MODELS_CONFIG = {}

# Agents Configuration
if CONFIG and 'config' in CONFIG and 'agents' in CONFIG['config']:
    AGENTS_CONFIG = CONFIG['config']['agents']
    logger.info("Loaded agents configuration from config.yaml")
else:
    AGENTS_CONFIG = {}

# System Configuration
if CONFIG and 'config' in CONFIG and 'system' in CONFIG['config']:
    SYSTEM_CONFIG = CONFIG['config']['system']
    logger.info("Loaded system configuration from config.yaml")
else:
    SYSTEM_CONFIG = {
        "log_level": "INFO",
        "name": "Anomaly Detection System",
        "output_dir": "results"
    }

def initialize_session_state():
    """Initialize all session state variables if they don't exist."""
    if 'theme' not in st.session_state:
        st.session_state.theme = 'light'
    
    if 'agent_activities' not in st.session_state:
        st.session_state.agent_activities = []
    
    if 'agent_messages' not in st.session_state:
        st.session_state.agent_messages = []
    
    if 'anomaly_analysis' not in st.session_state:
        st.session_state.anomaly_analysis = []
    
    if 'active_agent' not in st.session_state:
        st.session_state.active_agent = None
    
    if 'agent_animation_speed' not in st.session_state:
        st.session_state.agent_animation_speed = 1.0
    
    if 'selected_page' not in st.session_state:
        st.session_state.selected_page = "Dashboard"
    
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []

def add_notification(message, type='info'):
    """Add a notification to the session state."""
    st.session_state.notifications.append({
        'message': message,
        'type': type,
        'time': datetime.datetime.now().isoformat()
    })
