"""
Functions for generating sample data for the Anomaly Detection Dashboard.
These functions create realistic mock data for development and demonstrations.
"""

import random
import datetime
import numpy as np
import pandas as pd

def generate_sample_data(count=50):
    """Generate sample anomaly data."""
    anomalies = []
    models = ["isolation_forest_model", "one_class_svm_model", "ensemble_model", "autoencoder_model", "statistical_model"]
    
    for i in range(count):
        score = random.uniform(0.5, 0.95)
        model = random.choice(models)
        
        # Determine severity based on score
        if score > 0.8:
            severity = "High"
        elif score > 0.6:
            severity = "Medium"
        else:
            severity = "Low"
        
        # Create timestamp within last 7 days
        days_ago = random.randint(0, 7)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        timestamp = (datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)).isoformat()
        detection_time = timestamp  # Match detection_time with timestamp
        
        # Generate location data
        location = random.choice(["us-east", "us-west", "eu-central", "ap-south", "sa-east"])
        
        # Generate source and destination IPs
        src_ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
        dst_ip = f"10.0.{random.randint(1, 254)}.{random.randint(1, 254)}"
        
        # Generate features that contributed to anomaly
        features_list = []
        for _ in range(random.randint(1, 3)):
            feature = random.choice([
                "unusual_login_time", "high_data_transfer", "rare_destination",
                "suspicious_process", "unusual_network_activity", "unauthorized_access_attempt",
                "configuration_change", "privilege_escalation", "data_exfiltration",
                "unusual_protocol", "malformed_packet", "unusual_login_location"
            ])
            if feature not in features_list:
                features_list.append(feature)
        
        # Format features as JSONB array (JSON string representation)
        
        # Generate some sample data
        data = {
            "source_type": random.choice(["log", "metric", "event", "network"]),
            "timestamp": timestamp,
            "user_id": random.choice([None, f"user_{random.randint(1000, 9999)}"]),
            "event_type": random.choice(["login", "data_access", "configuration", "network", "system"]),
            "bytes_transferred": random.randint(1000, 100000),
            "duration_seconds": random.randint(1, 300),
            "protocol": random.choice(["HTTP", "HTTPS", "TCP", "UDP", "SSH"]),
            "status_code": random.choice([200, 401, 403, 404, 500])
        }
        
        # Generate details
        details = {
            "bytes_transferred": data["bytes_transferred"],
            "duration_seconds": data["duration_seconds"],
            "protocol": data["protocol"],
            "additional_info": f"Generated sample data for anomaly {i+1000}"
        }
        
        anomalies.append({
            "id": f"ANM-{i+1000}",
            "model": model,
            "score": score,
            "threshold": 0.5,
            "timestamp": timestamp,
            "detection_time": detection_time,
            "location": location,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "data": data,
            "details": details,
            "features": features_list,
            "status": random.choice(["new", "investigating", "resolved"]),
            "severity": severity,
            "analysis": {
                "severity": severity,
                "confidence": random.uniform(0.7, 0.95),
                "risk_factors": random.sample(["unusual_traffic", "high_volume", "suspicious_pattern", "policy_violation", "data_exfiltration_risk"], k=random.randint(1, 3))
            }
        })
    
    return anomalies

def generate_sample_models():
    """Generate sample model data."""
    return [
        {
            "name": "isolation_forest_model",
            "type": "IsolationForest",
            "status": "trained",
            "performance": {
                "accuracy": 0.92,
                "precision": 0.89,
                "recall": 0.94,
                "f1_score": 0.91
            },
            "config": {
                "contamination": 0.05,
                "n_estimators": 100,
                "random_state": 42
            }
        },
        {
            "name": "one_class_svm_model",
            "type": "OneClassSVM",
            "status": "trained",
            "performance": {
                "accuracy": 0.87,
                "precision": 0.85,
                "recall": 0.88,
                "f1_score": 0.86
            },
            "config": {
                "kernel": "rbf",
                "nu": 0.01,
                "gamma": "scale"
            }
        },
        {
            "name": "ensemble_model",
            "type": "Ensemble",
            "status": "trained",
            "performance": {
                "accuracy": 0.95,
                "precision": 0.93,
                "recall": 0.96,
                "f1_score": 0.94
            },
            "config": {
                "weights": {
                    "isolation_forest_model": 0.7,
                    "one_class_svm_model": 0.3
                }
            }
        },
        {
            "name": "autoencoder_model",
            "type": "Autoencoder",
            "status": "trained",
            "performance": {
                "accuracy": 0.90,
                "precision": 0.88,
                "recall": 0.91,
                "f1_score": 0.89
            },
            "config": {
                "hidden_dims": [64, 32, 16, 32, 64],
                "activation": "relu",
                "epochs": 100
            }
        },
        {
            "name": "statistical_model",
            "type": "Statistical",
            "status": "not_trained",
            "performance": {
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0
            },
            "config": {
                "window_size": 10,
                "threshold_multiplier": 3.0
            }
        }
    ]

def generate_system_status():
    """Generate sample system status data."""
    return {
        "initialized": True,
        "models": {
            "count": 5,
            "names": ["isolation_forest_model", "one_class_svm_model", "ensemble_model", "autoencoder_model", "statistical_model"],
            "trained": 4,
            "accuracy": 0.91
        },
        "processors": {
            "count": 3,
            "names": ["normalizer", "feature_extractor", "anomaly_detector"],
            "active": 2
        },
        "collectors": {
            "count": 4,
            "names": ["file_collector", "api_collector", "stream_collector", "batch_collector"],
            "active": 3
        },
        "storage": {
            "initialized": True,
            "type": "postgresql",
            "usage": 68,
            "total_space": "500GB",
            "used_space": "340GB"
        },
        "jobs": {
            "total": 25,
            "running": 4,
            "completed": 20,
            "failed": 1
        },
        "system_load": {
            "cpu": 45,
            "memory": 62,
            "network": 38
        },
        "uptime": "5d 12h 43m"
    }

def get_sample_time_series_data():
    """Generate sample time series data."""
    # Create a date range for the past 30 days
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=30)
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Create anomaly counts with a realistic pattern
    base_anomalies = np.random.normal(loc=15, scale=5, size=len(dates))
    
    # Add a weekly pattern (higher on weekdays)
    weekday_effect = np.array([3 if d.weekday() < 5 else -2 for d in dates])
    
    # Add a trend
    trend = np.linspace(0, 5, len(dates))
    
    # Combine effects
    anomaly_counts = base_anomalies + weekday_effect + trend
    anomaly_counts = np.maximum(anomaly_counts, 1)  # Ensure at least 1 anomaly per day
    
    # Create dataframe
    df = pd.DataFrame({
        'date': dates,
        'anomaly_count': anomaly_counts.astype(int)
    })
    
    return df