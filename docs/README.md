markdown# 🔍 Anomaly Detection System - Setup Guide

A comprehensive security-focused anomaly detection system that analyzes various data sources to identify potential threats using machine learning models and intelligent LLM-powered agents.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Detailed Setup Guide](#detailed-setup-guide)
 - [Step 1: System Dependencies](#step-1-system-dependencies)
 - [Step 2: Database Setup](#step-2-database-setup)
 - [Step 3: LLM Setup (Ollama)](#step-3-llm-setup-ollama)
 - [Step 4: Python Environment](#step-4-python-environment)
 - [Step 5: Configuration](#step-5-configuration)
 - [Step 6: API Service Setup](#step-6-api-service-setup)
 - [Step 7: Testing the System](#step-7-testing-the-system)
- [Pipeline Operations](#pipeline-operations)
- [System Management](#system-management)
- [Troubleshooting](#troubleshooting)

## 🌟 Key Features

- **Multi-Model ML Detection**: Isolation Forest, One-Class SVM, Autoencoder, GAN, Statistical, and Ensemble models
- **Intelligent Agent Analysis**: LLM-powered agents for security analysis, remediation, and threat intelligence
- **Real-time & Batch Processing**: Support for streaming and batch anomaly detection
- **Comprehensive API**: RESTful API with WebSocket support for real-time updates
- **Production-Ready Pipelines**: Test, validation, and detection pipelines for MLOps

## Prerequisites

### System Requirements
- **OS**: macOS or Ubuntu Linux
- **Python**: 3.9 or higher
- **Memory**: 8GB RAM minimum (16GB recommended)
- **Storage**: 10GB free space minimum

### Required Software
- PostgreSQL 12+
- Python 3.9+
- pip (Python package manager)
- git (for cloning/version control)
- curl (for API testing)

### Optional Software
- Ollama (for LLM-powered agent analysis)
- Apache Kafka (for streaming data collection)

📖 Detailed Setup Guide
Step 1: System Dependencies
  # macOS
  
  python -m venv venv

  # Install Homebrew if not already installed
  /bin/ -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  # Install system dependencies
  brew install postgresql
  brew install python@3.10
  brew install git

  # Ubuntu Linux

  # Update package manager
  sudo apt update

  # Install dependencies
  sudo apt install -y postgresql postgresql-contrib
  sudo apt install -y python3.10 python3.10-venv python3-pip
  sudo apt install -y git curl build-essential

Step 2: Database Setup

2.1 Start PostgreSQL Service
# macOS:
brew services start postgresql

# Ubuntu:
sudo systemctl start postgresql
sudo systemctl enable postgresql

2.2 Create Database and User
# Connect to PostgreSQL as superuser
psql

# In psql, run these commands:
CREATE DATABASE anomaly_detection;
CREATE USER anomaly_user WITH ENCRYPTED PASSWORD 'St@rW@rs!';
GRANT ALL PRIVILEGES ON DATABASE anomaly_detection TO anomaly_user;
\q

Step 2.2.1: Configuration
2.2.1 Review Configuration File

Edit config/config.yaml to match your environment:

# Database configuration
database:
  type: postgresql
  connection:
    host: localhost
    port: 5432
    database: anomaly_detection
    user: anomaly_user
    password: PASSWORD

# Agent configuration (for LLM analysis)
agents:
  enabled: true
  llm:
    provider: ollama
    model: mistral
    base_url: http://localhost:11434

# Alert configuration
alerts:
  enabled: true
  threshold: high
  channels:
    - console

2.3 Initialize Database Schema

# Run the database build script
chmod +x utils/build_db.sh
./utils/build_db.sh

This creates all necessary tables and populates sample data.

Step 3: LLM Setup (Ollama)

3.1 Install Ollama
# macOS:
brew install ollama

# Ubuntu:
curl -fsSL https://ollama.ai/install.sh | sh

3.2 Start Ollama Service
# Start Ollama (in a separate terminal or background)
ollama serve

# In another terminal, pull the Mistral model
ollama pull mistral

Step 4: Python Environment

4.1 Create Virtual Environment
# Create virtual environment
python3.10 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate

4.2 Install Python Dependencies

# Upgrade pip
pip install --upgrade pip
pip install -r requirements.txt

5.2 Create Required Directories

# Create directory structure
mkdir -p storage/{models,anomalies,processed,state}
mkdir -p data/{input,test,validation}
mkdir -p logs
mkdir -p reports/{test,validation}
mkdir -p config

Step 6: API Service Setup
6.1 Start the API Service

# Using the startup script (recommended)
# Ubuntu:

chmod +x sop_system_startup.sh
./sysadmin/sop_system_startup.sh

# Or macOS or manually:

# Start API service with auto-initialization
python api_services.py --config config/config.yaml --auto-init --host 0.0.0.0 --port 8000

6.2 Verify API Service

# Check health endpoint
curl http://localhost:8000/

# Expected response:
{"status": "healthy", "version": "2.0.0", "initialized": true, ...}

6.3 Initialize System

# Initialize system with configuration
python api_client.py init config/config.yaml

# Check system status
python api_client.py system-status

Step 7: Testing the System

7.1 Load Sample Data
Create test data in data/test/sample_data.json:
[
  {
    "timestamp": "2024-01-15T10:30:00Z",
    "cpu_usage": 45.2,
    "memory_usage": 62.3,
    "network_in": 1024,
    "network_out": 2048,
    "process_count": 125
  },
  {
    "timestamp": "2024-01-15T10:31:00Z",
    "cpu_usage": 98.5,
    "memory_usage": 95.2,
    "network_in": 50000,
    "network_out": 100000,
    "process_count": 250
  }
]

7.2 Test API Operations

# List available models
python api_client.py list-models

# Process data through pipeline
python api_client.py process-data data/test/sample_data.json

# Check agents status
python api_client.py agents-status

# Test alert system
python api_client.py test-alert

🔄 Pipeline Operations

Test Pipeline
The test pipeline is used for model development and experimentation:

# Run full test pipeline
./pipelines/test_pipeline.sh config/config.yaml

# Run specific stages
./pipelines/test_pipeline.sh --skip-collection      # Skip data collection
./pipelines/test_pipeline.sh --skip-preprocessing   # Skip preprocessing
./pipelines/test_pipeline.sh --skip-training       # Skip model training

Test Pipeline Stages:

Data Collection - Gather test data
Preprocessing - Normalize and clean data
Feature Engineering - Extract relevant features
Data Splitting - Create train/validation/test sets
Model Training - Train all enabled models
Model Evaluation - Assess model performance
Model Export - Save trained models

Validation Pipeline
Validate trained models before production deployment:

# Run validation pipeline
./pipelines/validation_pipeline.sh

# With custom thresholds
./pipelines/validation_pipeline.sh --min-precision 0.8 --min-recall 0.7

Validation Pipeline Stages:

Load validation dataset
Preprocess validation data
Load trained models
Run model validation
Calculate performance metrics
Compare with baselines
Generate validation report
Promote validated models

Detection Pipeline

Run anomaly detection in production:

# Batch detection mode (default)
./pipelines/detect_anomalies_pipeline.sh

# Continuous monitoring mode
./pipelines/detect_anomalies_pipeline.sh --continuous

# With specific thresholds
./pipelines/detect_anomalies_pipeline.sh --critical-threshold 0.95 --high-threshold 0.85

# Disable certain features
./pipelines/detect_anomalies_pipeline.sh --no-agents --no-alerts

Detection Pipeline Stages:

Data collection (batch/streaming)
Real-time preprocessing
Feature extraction
Load production models
Anomaly detection
Agent analysis (if enabled)
Alert generation
Results storage

🛠️ System Management
Starting the System

# Full system startup
./sysadmin/sop_system_startup.sh

# This script:
# 1. Checks prerequisites
# 2. Starts PostgreSQL
# 3. Starts Ollama (for agents)
# 4. Clears old processes
# 5. Starts API service
# 6. Loads saved models

Stopping the System

# Graceful shutdown
# Ubuntu
./sysadmin/sop_system_shutdown.sh

# This script:
# 1. Checks for active jobs
# 2. Stops API service
# 3. Stops Ollama
# 4. Optionally stops PostgreSQL

Restarting API Service
# Quick API restart (preserves database/Ollama)

# Ubuntu:
./sysadmin/sop_restart_api.sh

Monitoring
# View API logs
tail -f logs/api_services_*.log

# Check system status
python api_client.py system-status

# List running jobs
python api_client.py list-jobs --status running

# Monitor WebSocket events (requires wscat)
wscat -c ws://localhost:8000/ws

Database Management
# Clean all data (reset system)
./utils/cleanup.sh

# Rebuild database schema
./utils/build_db.sh

# Backup database
pg_dump -U anomaly_user -d anomaly_detection > backup.sql

# Restore database
psql -U anomaly_user -d anomaly_detection < backup.sql

🐛 Troubleshooting

Common Issues
API Service Won't Start
# Check if port 8000 is in use
lsof -i :8000

# Kill process using port
kill -9 $(lsof -t -i :8000)

# Check API logs
tail -n 100 logs/api_services_*.log

Database Connection Failed
# Verify PostgreSQL is running

# macOS:
brew services list | grep postgresql

# Ubuntu:
sudo systemctl status postgresql

# Test database connection
PGPASSWORD="St@rW@rs!" psql -h localhost -U anomaly_user -d anomaly_detection -c "SELECT 1;"
Ollama/Agent Issues

# Check if Ollama is running
curl http://localhost:11434/api/tags

# List available models
ollama list

# Re-pull Mistral model
ollama pull mistral
Model Training Fails

# Check available memory
free -h  # Linux
vm_stat  # macOS

# Reduce batch size in config
# Edit config/config.yaml and reduce batch_size parameters

# Train single model
python api_client.py train-model isolation_forest_model data/test/sample_data.json

Log Locations

API Service: logs/api_services_*.log
Ollama: logs/ollama_*.log
Pipeline logs: logs/*_pipeline_*.log
PostgreSQL: /var/log/postgresql/ or check with brew services info postgresql

Performance Tuning

Database Optimization
sql-- Add indexes for common queries
CREATE INDEX idx_anomalies_timestamp ON anomalies(timestamp);
CREATE INDEX idx_anomalies_score ON anomalies(score);

API Performance

# Increase worker threads
python api_services.py --workers 4

Model Performance

Reduce model complexity in config.yaml
Use ensemble only when needed
Disable unused models

## How the Current Correlation Works:
1. Correlation Factors (Current Implementation):

Same Source IP (40% weight): Strong indicator of related activity
Same Location (20% weight): Anomalies from same data center/region
Similar Score (20% weight): Anomalies with scores within 0.1 of each other
Same Model (10% weight): Detected by the same ML model
Time Proximity (30% weight): Occurred within 1 hour of each other

2. Correlation Process:

Extracts key attributes from the target anomaly
Compares with all other anomalies
Calculates a correlation score (0-1)
Only includes anomalies with >30% correlation
Sorts by correlation strength

3. Enhanced Correlation System (in the artifact):
The enhanced version adds:
Network Correlation:

Same source IP (35%)
Same destination IP (25%)
Identical network flow bonus (15%)
Same ports and protocols

Location Correlation:

Same server (25%)
Same cluster (10%)
Same service (15%)
Same data center (15%)

Temporal Correlation:

Within 1 minute (40%)
Within 5 minutes (30%)
Within 1 hour (20%)
Same hour of day (10%)
Same day of week (5%)

Pattern Correlation:

Similar anomaly scores
Same severity level
Overlapping features
Similar data volumes

4. Optimization Features:

Groups anomalies by key attributes for faster lookup
Only analyzes likely candidates
Weighted scoring system
Detailed breakdown of correlation reasons

5. Visualization:
The correlation network shows:

Target anomaly in the center (red)
Related anomalies around it
Line thickness = correlation strength
Hover shows correlation reasons

To Use the Enhanced System:

Replace the render_correlation_analysis function in your anomalies.py with the enhanced version
Add the visualization function
The system will now detect more sophisticated correlations

This gives you much better insight into:

Attack campaigns (multiple anomalies from same source)
System failures (anomalies on same server/service)
Time-based patterns (scheduled attacks, peak hours)
Feature patterns (similar attack signatures)
