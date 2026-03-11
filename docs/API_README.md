# Anomaly Detection API - Complete Documentation

## Table of Contents
1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [System Architecture](#system-architecture)
4. [API Endpoints Reference](#api-endpoints-reference)
5. [Key Features](#key-features)
6. [Usage Guide](#usage-guide)
7. [Agent System](#agent-system)
8. [Examples and Workflows](#examples-and-workflows)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Anomaly Detection API is a comprehensive system for detecting, analyzing, and responding to anomalies in various data sources. It combines multiple machine learning models, intelligent agent-based analysis, and real-time monitoring capabilities.

### Key Capabilities
- **Multiple ML Models**: Isolation Forest, One-Class SVM, Autoencoder, GAN, Statistical, and Ensemble models
- **Intelligent Agent Analysis**: Multi-agent system for detailed anomaly investigation
- **Real-time Processing**: Stream processing with WebSocket support
- **Flexible Data Sources**: File, Kafka, SQL, and REST API collectors
- **Alert Management**: Email and webhook alerts for critical anomalies
- **Scalable Architecture**: Background job processing for heavy workloads

---

## Getting Started

### Prerequisites
- Python 3.8+
- PostgreSQL (for data storage)
- Ollama (for agent LLM capabilities)
- API server running on port 8000

### Quick Start

1. **Start the API Server**:
```bash
cd anomaly_detection
python api_services.py --config config/config.yaml --auto-init
```

2. **Run Quick Demo**:
```bash
./api_pipeline.sh demo
```

3. **Run Complete Pipeline**:
```bash
./api_pipeline.sh pipeline
```

4. **Interactive Mode**:
```bash
./api_pipeline.sh interactive
```

---

## System Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                     │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│  Collectors │   Models    │   Agents    │   Storage       │
├─────────────┼─────────────┼─────────────┼─────────────────┤
│ • File      │ • Isolation │ • Security  │ • PostgreSQL    │
│ • Kafka     │   Forest    │   Analyst   │ • File System   │
│ • SQL       │ • SVM       │ • Threat    │ • Model Store   │
│ • REST API  │ • Autoenc.  │   Intel     │                 │
│             │ • GAN       │ • Remediat. │                 │
│             │ • Statist.  │ • Code Gen  │                 │
│             │ • Ensemble  │ • Review    │                 │
└─────────────┴─────────────┴─────────────┴─────────────────┘
```

### Data Flow

1. **Collection** → Data ingested from various sources
2. **Processing** → Normalization and feature extraction
3. **Detection** → ML models identify anomalies
4. **Analysis** → Agents investigate and classify
5. **Response** → Alerts and remediation actions

---

## API Endpoints Reference

### System Management

#### Health Check
```http
GET /
```
Returns system health status.

#### Initialize System
```http
POST /init
{
  "config_path": "config/config.yaml",
  "auto_init": true
}
```
Initializes the system with configuration.

#### System Status
```http
GET /system/status
```
Returns comprehensive system status including all components.

### Model Operations

#### List Models
```http
GET /models
```
Returns all available models with their status.

#### Create Model
```http
POST /models/create
{
  "type": "isolation_forest",
  "config": {
    "n_estimators": 100,
    "contamination": 0.05
  }
}
```

#### Train Model
```http
POST /models/{model_name}/train
{
  "items": [
    {"timestamp": "2025-01-15T10:00:00Z", "cpu_usage": 25, ...}
  ]
}
```

#### Detect Anomalies
```http
POST /models/{model_name}/detect?threshold=0.7
{
  "items": [
    {"timestamp": "2025-01-15T11:00:00Z", "cpu_usage": 95, ...}
  ]
}
```

### Agent Analysis

#### Analyze with Agents
```http
POST /agents/analyze
[
  {
    "id": "anomaly-001",
    "timestamp": "2025-01-15T11:01:00Z",
    "score": 0.92,
    ...
  }
]
```

#### Detailed Agent Analysis
```http
POST /agents/analyze-detailed?include_dialogue=true&include_evidence=true
```
Provides comprehensive analysis with agent dialogue and evidence chains.

#### Get Agent Workflow
```http
GET /agents/workflow
```
Returns the agent collaboration workflow.

### Data Management

#### Process Data
```http
POST /data/process
{
  "items": [...]
}
```
Processes data through normalization and feature extraction.

#### Store Data
```http
POST /data/store
{
  "items": [...]
}
```

#### Load Data
```http
GET /data/load?latest=false
```

### Anomaly Management

#### List Anomalies
```http
GET /anomalies?severity=High&limit=100
```
Query parameters:
- `model`: Filter by model name
- `min_score`: Minimum anomaly score
- `status`: Filter by status
- `severity`: Critical, High, Medium, Low
- `limit`: Maximum results

### Real-time Features

#### WebSocket Connection
```ws
ws://localhost:8000/ws
```
For real-time updates and alerts.

#### Server-Sent Events
```http
GET /status/realtime
```
Stream real-time system status.

### Job Management

#### Get Job Status
```http
GET /jobs/{job_id}
```

#### List Jobs
```http
GET /jobs?status=completed&limit=10
```

---

## Key Features

### 1. Multi-Model Anomaly Detection

The system supports multiple ML models that can be used individually or in ensemble:

- **Isolation Forest**: Effective for high-dimensional data
- **One-Class SVM**: Good for novelty detection
- **Autoencoder**: Neural network-based reconstruction
- **GAN**: Generative approach for complex patterns
- **Statistical**: Time-series based detection
- **Ensemble**: Combines multiple models

### 2. Intelligent Agent System

Six specialized agents collaborate to analyze anomalies:

1. **Security Analyst**: Initial assessment and severity classification
2. **Threat Intelligence**: Correlates with known threats
3. **Remediation Expert**: Provides actionable response steps
4. **Code Generator**: Creates remediation scripts
5. **Security Reviewer**: Validates recommendations
6. **Data Collector**: Identifies additional data needs

### 3. Real-time Capabilities

- WebSocket support for live updates
- Server-Sent Events for status monitoring
- Asynchronous job processing
- Real-time alert notifications

### 4. Flexible Data Collection

Supports multiple data sources:
- File-based (JSON, CSV)
- Kafka streams
- SQL databases
- REST APIs

---

## Usage Guide

### Step-by-Step Pipeline Operation

#### 1. System Initialization

```bash
# Check API health
./api_pipeline.sh health

# Initialize system
./api_pipeline.sh init

# Check status
./api_pipeline.sh status
```

#### 2. Data Preparation

```bash
# Create sample data
./api_pipeline.sh create-data

# Or use your own data
cat > data/metrics.json << EOF
[
  {"timestamp": "2025-01-15T10:00:00Z", "cpu": 25, "memory": 45},
  {"timestamp": "2025-01-15T10:01:00Z", "cpu": 30, "memory": 48}
]
EOF
```

#### 3. Model Training

```bash
# Train a single model
./api_pipeline.sh train isolation_forest_model data/metrics.json

# Create and train a new model
./api_pipeline.sh create-model isolation_forest config/model_config.json
```

#### 4. Anomaly Detection

```bash
# Detect with single model
./api_pipeline.sh detect isolation_forest_model data/test_data.json 0.8

# Bulk detection with multiple models
./api_pipeline.sh bulk-detect data/test_data.json isolation_forest_model statistical_model
```

#### 5. Agent Analysis

```bash
# Analyze detected anomalies
./api_pipeline.sh analyze data/anomalies.json --detailed

# View agent workflow
./api_pipeline.sh agent-workflow
```

#### 6. Monitoring

```bash
# Real-time monitoring for 60 seconds
./api_pipeline.sh monitor 60

# List recent anomalies
./api_pipeline.sh list-anomalies High 20
```

---

## Agent System

### Agent Workflow

```
Security Analyst → Threat Intel → Remediation
                                      ↓
Data Collector ← Security Review ← Code Generator
```

### Agent Capabilities

#### Security Analyst
- Severity assessment (Critical/High/Medium/Low)
- False positive detection
- Initial threat classification
- Resource impact analysis

#### Threat Intelligence
- Known threat pattern matching
- IOC correlation
- Attack technique mapping (MITRE ATT&CK)
- External threat feed integration

#### Remediation Expert
- Containment strategies
- Investigation procedures
- Recovery steps
- Prevention recommendations

#### Code Generator
- Automated response scripts
- Security patches
- Configuration updates
- Monitoring rules

#### Security Reviewer
- Quality assurance
- Completeness verification
- Best practices validation
- Risk assessment

#### Data Collector
- Evidence requirements
- Log collection strategies
- Forensic data identification
- Monitoring enhancements

### Agent Dialogue Example

```json
{
  "from": "security_analyst",
  "to": "threat_intel",
  "type": "question",
  "message": "Detected unusual network traffic pattern. Can you correlate with known C2 indicators?",
  "confidence": 0.85
}
```

---

## Examples and Workflows

### Example 1: Complete Detection Pipeline

```bash
#!/bin/bash

# 1. Initialize system
./api_pipeline.sh init

# 2. Create training data
./api_pipeline.sh create-data

# 3. Train models
./api_pipeline.sh train isolation_forest_model data/input/training_data_normal.json
./api_pipeline.sh train statistical_model data/input/training_data_normal.json

# 4. Run detection
./api_pipeline.sh detect isolation_forest_model data/input/detection_data_mixed.json 0.7

# 5. Analyze anomalies with agents
./api_pipeline.sh analyze data/anomalies/latest.json --detailed

# 6. Export results
./api_pipeline.sh export
```

### Example 2: Real-time Monitoring

```python
import asyncio
from api_client import AnomalyDetectionClient

async def monitor_anomalies():
    client = AnomalyDetectionClient("http://localhost:8000")
    
    # Connect to WebSocket
    ws = await client.websocket_connect(
        on_message=lambda msg: print(f"Alert: {msg}"),
        on_error=lambda err: print(f"Error: {err}")
    )
    
    # Subscribe to alerts
    await ws.subscribe(["alerts", "anomalies"])
    
    # Keep connection alive
    await asyncio.sleep(300)  # Monitor for 5 minutes
    await ws.close()

asyncio.run(monitor_anomalies())
```

### Example 3: Custom Model Configuration

```bash
# Create custom Isolation Forest configuration
cat > config/custom_if.json << EOF
{
  "n_estimators": 200,
  "contamination": 0.03,
  "max_features": 0.8,
  "bootstrap": true,
  "random_state": 42
}
EOF

# Create and train model
./api_pipeline.sh create-model isolation_forest config/custom_if.json

# Train with specific data
./api_pipeline.sh train isolation_forest_model_20250115120000 data/custom_training.json
```

### Example 4: Automated Response Workflow

```python
from api_client import AnomalyDetectionClient
import json

client = AnomalyDetectionClient("http://localhost:8000")

# 1. Detect anomalies
detection_job = client.detect_anomalies(
    "ensemble_model",
    data=[
        {"cpu": 95, "memory": 88, "network": 50000},
        {"cpu": 30, "memory": 45, "network": 1000}
    ],
    threshold=0.8
)

# 2. Wait for detection
result = client.wait_for_job(detection_job["job_id"])

# 3. If anomalies found, analyze with agents
if result["result"]["anomalies_detected"] > 0:
    anomalies = client.list_anomalies(min_score=0.8, limit=10)
    
    # 4. Get detailed agent analysis
    analysis = client.analyze_with_agents_detailed(
        anomalies,
        include_dialogue=True,
        include_evidence=True
    )
    
    # 5. Extract remediation recommendations
    for anomaly in analysis["result"]["detailed_results"]:
        if anomaly["analysis"]["severity"] in ["Critical", "High"]:
            print(f"CRITICAL ANOMALY: {anomaly['id']}")
            print(f"Remediation: {anomaly['analysis']['remediation_steps']}")
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. API Not Responding

**Symptom**: Health check fails
```bash
Error: API is not responding. Please ensure the API server is running
```

**Solution**:
```bash
# Check if server is running
ps aux | grep api_services.py

# Start server if not running
python api_services.py --config config/config.yaml --auto-init

# Check logs
tail -f api_pipeline.log
```

#### 2. Database Connection Issues

**Symptom**: Storage manager errors
```
Error: Failed to connect storage manager
```

**Solution**:
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Verify connection settings in config.yaml
# Ensure database exists
psql -U postgres -c "CREATE DATABASE anomaly_detection;"

# Test connection
curl http://localhost:8000/database/status
```

#### 3. Model Training Failures

**Symptom**: Training job fails
```
Job train_model_xxx failed: Model not found
```

**Solution**:
```bash
# List available models
./api_pipeline.sh list-models

# Initialize system to load models
./api_pipeline.sh init

# Create model if needed
./api_pipeline.sh create-model isolation_forest config/model_config.json
```

#### 4. Agent System Not Available

**Symptom**: Agent analysis fails
```
Error: Agent manager not initialized
```

**Solution**:
```yaml
# Ensure agents are enabled in config.yaml
agents:
  enabled: true
  llm:
    provider: ollama
    model: mistral
    base_url: http://localhost:11434
```

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Restart with proper config
./api_pipeline.sh init
```

#### 5. WebSocket Connection Issues

**Symptom**: Real-time updates not working
```
WebSocket connection failed
```

**Solution**:
```python
# Test WebSocket endpoint
import websockets
import asyncio

async def test_ws():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        msg = await websocket.recv()
        print(msg)

asyncio.run(test_ws())
```

### Performance Optimization

#### 1. Batch Processing
```bash
# Process large datasets in batches
split -l 1000 large_dataset.json batch_
for file in batch_*; do
    ./api_pipeline.sh detect isolation_forest_model "$file"
done
```

#### 2. Model Caching
```bash
# Load saved models on startup
./api_pipeline.sh load-models

# Save trained models
ls storage/models/
```

#### 3. Parallel Detection
```python
import concurrent.futures
from api_client import AnomalyDetectionClient

client = AnomalyDetectionClient()

def detect_batch(model, data_batch):
    return client.detect_anomalies(model, data_batch)

# Parallel detection across models
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    models = ["isolation_forest_model", "statistical_model", "autoencoder_model"]
    futures = [executor.submit(detect_batch, model, data) for model in models]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]
```

### Debugging Tips

#### 1. Enable Verbose Logging
```bash
# Run with verbose output
./api_pipeline.sh --verbose pipeline

# Check API logs
tail -f logs/api_services.log
```

#### 2. Test Individual Components
```bash
# Test collectors
./api_pipeline.sh debug-collectors

# Test processors
curl http://localhost:8000/processors/status

# Test specific model
curl -X POST http://localhost:8000/models/isolation_forest_model/detect \
  -H "Content-Type: application/json" \
  -d '{"items": [{"cpu": 95, "memory": 88}]}'
```

#### 3. Monitor Background Jobs
```bash
# List all jobs
curl http://localhost:8000/jobs | jq .

# Check specific job
curl http://localhost:8000/jobs/train_model_20250115120000 | jq .

# Monitor running jobs
watch -n 2 'curl -s http://localhost:8000/jobs?status=running | jq .'
```

---

## Advanced Configuration

### Custom Agent Prompts

```yaml
# config.yaml
agents:
  security_analyst:
    system_prompt: |
      You are an expert security analyst specializing in APT detection.
      Focus on: behavioral analysis, lateral movement, data exfiltration.
      Use MITRE ATT&CK framework for classification.
```

### Model Ensemble Configuration

```yaml
models:
  ensemble:
    weights:
      isolation_forest: 0.4
      statistical: 0.3
      autoencoder: 0.3
    voting_strategy: "weighted"
    threshold: 0.75
```

### Alert Routing

```yaml
alerts:
  rules:
    - condition:
        severity: "Critical"
        score: ">0.9"
      channels: ["email", "webhook", "pagerduty"]
    - condition:
        severity: "High"
        model: "ensemble_model"
      channels: ["email", "slack"]
```

---

## Best Practices

### 1. Model Selection
- Use **Isolation Forest** for general anomaly detection
- Use **Statistical** models for time-series data
- Use **Autoencoders** for complex patterns
- Use **Ensemble** for critical systems

### 2. Threshold Tuning
- Start with default threshold (0.7)
- Adjust based on false positive rate
- Use different thresholds per model
- Monitor and refine over time

### 3. Data Quality
- Ensure consistent timestamps
- Handle missing values appropriately
- Normalize features before training
- Include relevant context in anomalies

### 4. Agent Analysis
- Use detailed analysis for critical anomalies
- Review agent dialogue for insights
- Implement suggested remediations
- Track false positive feedback

### 5. System Maintenance
- Regularly retrain models
- Clean up old jobs and data
- Monitor system performance
- Update agent prompts based on findings

---

## API Client Examples

### Python Client Usage

```python
from api_client import AnomalyDetectionClient

# Initialize client
client = AnomalyDetectionClient("http://localhost:8000")

# Complete workflow
def anomaly_detection_workflow():
    # 1. Initialize system
    client.initialize_system("config/config.yaml")
    
    # 2. Train model
    training_data = [
        {"timestamp": "2025-01-15T10:00:00Z", "cpu": 25, "memory": 45},
        # ... more data
    ]
    train_job = client.train_model("isolation_forest_model", training_data)
    client.wait_for_job(train_job["job_id"])
    
    # 3. Detect anomalies
    test_data = [
        {"timestamp": "2025-01-15T11:00:00Z", "cpu": 95, "memory": 88},
        # ... more data
    ]
    detect_job = client.detect_anomalies("isolation_forest_model", test_data, threshold=0.8)
    result = client.wait_for_job(detect_job["job_id"])
    
    # 4. Analyze with agents if anomalies found
    if result["result"]["anomalies_detected"] > 0:
        anomalies = client.list_anomalies(min_score=0.8)
        analysis = client.analyze_with_agents_detailed(anomalies)
        
        # Process results
        for anomaly in analysis["result"]["detailed_results"]:
            print(f"Anomaly {anomaly['id']}: {anomaly['analysis']['severity']}")
            print(f"Recommendation: {anomaly['analysis']['remediation_steps']}")

# Run workflow
anomaly_detection_workflow()
```

### Curl Examples

```bash
# Initialize system
curl -X POST http://localhost:8000/init \
  -H "Content-Type: application/json" \
  -d '{"config_path": "config/config.yaml"}'

# Train model
curl -X POST http://localhost:8000/models/isolation_forest_model/train \
  -H "Content-Type: application/json" \
  -d @training_data.json

# Detect anomalies
curl -X POST "http://localhost:8000/models/isolation_forest_model/detect?threshold=0.8" \
  -H "Content-Type: application/json" \
  -d @test_data.json

# Get job status
curl http://localhost:8000/jobs/detect_isolation_forest_model_20250115120000

# List anomalies
curl "http://localhost:8000/anomalies?severity=High&limit=10"
```

---

## Conclusion

The Anomaly Detection API provides a comprehensive solution for identifying and responding to anomalies in your systems. By combining multiple ML models with intelligent agent analysis, it offers both accuracy and actionable insights.

Key takeaways:
- Start with the interactive menu or demo for familiarization
- Use the complete pipeline for production deployments
- Leverage agent analysis for critical anomalies
- Monitor and tune the system based on your specific needs

For support and updates, check the project repository or run:
```bash
./api_pipeline.sh help
```