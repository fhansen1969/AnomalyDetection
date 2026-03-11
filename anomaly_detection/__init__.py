"""
Anomaly detection system package.

This package provides a comprehensive anomaly detection framework for
identifying, analyzing, and responding to security anomalies.
"""

__version__ = "1.0.0"
__author__ = "Security Team"
__description__ = "Comprehensive anomaly detection system"

# Import main components for easier access
try:
    from anomaly_detection.utils.config import Config
    from anomaly_detection.collectors import CollectorFactory
    from anomaly_detection.processors import ProcessorFactory
    from anomaly_detection.models import ModelFactory
    from anomaly_detection.storage import StorageManager
    from anomaly_detection.agents import AgentManager
    from anomaly_detection.alerts import AlertManager

    __all__ = [
        'Config',
        'CollectorFactory',
        'ProcessorFactory',
        'ModelFactory',
        'StorageManager',
        'AgentManager',
        'AlertManager'
    ]
except ImportError as e:
    # Handle import errors gracefully during initial setup
    import sys
    print(f"Note: Some modules could not be imported yet: {e}", file=sys.stderr)
    print("This is normal during initial setup.", file=sys.stderr)
    __all__ = []
