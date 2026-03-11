"""
Startup helper script for Anomaly Detection System
Ensures all components are properly configured and running
"""

import os
import sys
import time
import subprocess
import yaml
from pathlib import Path

def create_minimal_config():
    """Create a minimal working config.yaml if it doesn't exist"""
    config = {
        "database": {
            "type": "file",
            "file_path": "storage/anomaly_db.json"
        },
        "collectors": {
            "enabled": ["file"],
            "file": {
                "paths": ["data/input/"],
                "watch_interval_seconds": 60,
                "batch_size": 100
            }
        },
        "models": {
            "enabled": ["isolation_forest", "statistical"],
            "isolation_forest": {
                "contamination": 0.05,
                "n_estimators": 100,
                "random_state": 42
            },
            "statistical": {
                "window_size": 10,
                "threshold_multiplier": 3.0
            }
        },
        "processors": {
            "normalizers": [{
                "name": "generic_normalizer",
                "type": "json",
                "timestamp_field": "timestamp"
            }],
            "feature_extractors": [{
                "name": "basic_features",
                "fields": ["*"],
                "categorical_encoding": "one_hot"
            }]
        },
        "agents": {
            "enabled": False  # Disable agents initially for simpler setup
        },
        "alerts": {
            "enabled": False
        }
    }
    
    with open("config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print("✅ Created minimal config.yaml")

def create_directory_structure():
    """Create required directories"""
    directories = [
        "data/input",
        "storage",
        "storage/anomalies",
        "storage/processed", 
        "storage/state",
        "anomaly_detection"
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print("✅ Created directory structure")

def create_sample_data():
    """Create a sample data file for testing"""
    import json
    from datetime import datetime
    
    sample_data = {
        "timestamp": datetime.now().isoformat(),
        "cpu_usage": 45.5,
        "memory_usage": 62.3,
        "network_in": 15000,
        "network_out": 8000,
        "disk_usage": 75.2,
        "process_count": 125
    }
    
    sample_file = "data/input/sample_data.json"
    with open(sample_file, "w") as f:
        json.dump(sample_data, f, indent=2)
    
    print(f"✅ Created sample data file: {sample_file}")

def check_api_server():
    """Check if API server is running"""
    import requests
    
    try:
        response = requests.get("http://localhost:8000/")
        if response.status_code == 200:
            print("✅ API server is running")
            return True
        else:
            print("❌ API server returned error")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ API server is not running")
        return False

def start_api_server():
    """Start the API server"""
    print("\n🚀 Starting API server...")
    
    # Check if api_services.py exists
    if not os.path.exists("api_services.py"):
        print("❌ api_services.py not found!")
        return None
    
    # Start server in subprocess
    cmd = [sys.executable, "api_services.py", "--config", "config.yaml", "--auto-init"]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    # Wait for server to start
    print("   Waiting for server to start...")
    for i in range(30):  # Wait up to 30 seconds
        time.sleep(1)
        if check_api_server():
            return process
        print(".", end="", flush=True)
    
    print("\n❌ Server failed to start")
    return None

def main():
    """Main setup and startup routine"""
    print("🛡️  Anomaly Detection System - Startup Helper\n")
    
    # 1. Check/create config
    if not os.path.exists("config.yaml"):
        print("⚠️  config.yaml not found")
        create_minimal_config()
    else:
        print("✅ config.yaml exists")
    
    # 2. Create directories
    print("\n📁 Setting up directories...")
    create_directory_structure()
    
    # 3. Create sample data
    print("\n📊 Creating sample data...")
    create_sample_data()
    
    # 4. Check API server
    print("\n🔍 Checking API server...")
    if not check_api_server():
        response = input("\nWould you like to start the API server? (y/n): ")
        if response.lower() == 'y':
            api_process = start_api_server()
            if not api_process:
                print("\n❌ Failed to start API server")
                print("Please start it manually:")
                print("  python api_services.py --config config.yaml --auto-init")
                sys.exit(1)
        else:
            print("\n⚠️  Please start the API server manually:")
            print("  python api_services.py --config config.yaml --auto-init")
    
    # 5. Ready to start dashboard
    print("\n✨ System is ready!")
    print("\nTo start the dashboard, run:")
    print("  streamlit run light_theme_dashboard.py")
    
    response = input("\nWould you like to start the dashboard now? (y/n): ")
    if response.lower() == 'y':
        print("\n🚀 Starting dashboard...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "light_theme_dashboard.py"])

if __name__ == "__main__":
    main()
