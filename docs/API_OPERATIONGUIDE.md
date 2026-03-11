# Anomaly Detection API - Step-by-Step Operation Guide

## Prerequisites Setup

### 1. Install Dependencies
```bash
# Python dependencies
pip install fastapi uvicorn requests psycopg2-binary scikit-learn tensorflow torch numpy pandas pydantic websockets

# System dependencies
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
```

### 2. Setup PostgreSQL
```bash
# Start PostgreSQL
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE anomaly_detection;
CREATE USER anomaly_user WITH PASSWORD 'XXXXX';
GRANT ALL PRIVILEGES ON DATABASE anomaly_detection TO anomaly_user;
EOF
```

### 3. Install Ollama (for Agent System)
```bash
# Download and install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the Mistral model
ollama pull mistral

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

## Step 1: Start the API Server

# Checks if the API server is responsive and healthy
# Initializes the anomaly detection system with configuration settings
# Verifies the status of all system components

```bash
# Navigate to project directory
cd anomaly_detection

# Start the API server with auto-initialization
python api_services.py --config config/config.yaml --auto-init --verbose

# Or run in background
nohup python api_services.py --config config/config.yaml --auto-init > api_server.log 2>&1 &
```

**Expected Output:**
```
INFO: Started server process [12345]
INFO: Waiting for application startup.
INFO: System initialization completed
INFO: Initialized components: 6 models, 2 processors, 1 collectors
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

## Step 2: Verify System Health

# Creates sample data files with both normal operating patterns and anomalous behavior
# Generates datasets for training and testing the anomaly detection models
# Organizes the data into appropriate directories for processing

```bash
# Check API health
./api_pipeline.sh health

# Or using curl
curl http://localhost:8000/
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "initialized": true,
  "system_time": "2025-01-15T12:00:00.000000"
}
```

## Step 3: Initialize the System

# Trains existing anomaly detection models using normal operating data
# Creates and trains a new isolation forest model with custom configuration
# Lists all available models and their current status

```bash
# Initialize with configuration
./api_pipeline.sh init

# Check system status
./api_pipeline.sh status
```

**What This Does:**
- Loads configuration from `config.yaml`
- Initializes storage manager (PostgreSQL)
- Creates database tables
- Loads enabled models
- Initializes processors and collectors
- Sets up agent system
- Configures alert manager

## Step 4: Create Training Data

# Runs anomaly detection using a single model (isolation forest) against test data
# Performs bulk detection using multiple models (isolation forest and statistical model)
# Identifies and lists high-severity anomalies detected in the system

```bash
# Create sample data files
./api_pipeline.sh create-data

# Verify files created
ls -la data/input/
```

**Files Created:**
- `training_data_normal.json` - Normal behavior patterns
- `detection_data_mixed.json` - Mix of normal and anomalous data
- `anomalies_detailed.json` - Pre-identified anomalies for agent analysis

## Step 5: Train Models

# Checks if the agent system (LLM-based analysis) is available
# If available, analyzes the detailed anomalies using AI agents
# Provides in-depth explanations and context for the detected anomalies
# Identifies patterns, root causes, and potential remediation steps

### Option A: Train Pre-configured Models
```bash
# Train Isolation Forest model
./api_pipeline.sh train isolation_forest_model data/input/training_data_normal.json

# Train Statistical model
./api_pipeline.sh train statistical_model data/input/training_data_normal.json
```

### Option B: Create and Train New Model
```bash
# Create model configuration
cat > config/custom_model.json << EOF
{
  "n_estimators": 200,
  "contamination": 0.03,
  "random_state": 42
}
EOF

# Create and train model
python api_client.py create-model isolation_forest config/custom_model.json
```

**Monitor Training Progress:**
```bash
# Check job status
python api_client.py job-status train_isolation_forest_model_20250115120000

# List all models
./api_pipeline.sh list-models
```

## Step 6: Detect Anomalies

# Performs real-time monitoring of the system for a brief period
# Displays live updates on model status, running jobs, and alerts

### Single Model Detection
```bash
# Run detection with specific threshold
./api_pipeline.sh detect isolation_forest_model data/input/detection_data_mixed.json 0.7
```

### Bulk Detection (Multiple Models)
```bash
# Run detection across multiple models
./api_pipeline.sh bulk-detect data/input/detection_data_mixed.json \
  isolation_forest_model statistical_model
```

**Expected Output:**
```
[INFO] Detection job started: detect_isolation_forest_model_20250115120500
✓ Detection completed successfully
{
  "model": "isolation_forest_model",
  "anomalies_detected": 4,
  "threshold": 0.7,
  "sample_anomalies": [...]
}
```

## Step 7: Review Detected Anomalies

# Exports all detection results, anomalies, and analysis to structured files
# Creates a summary report with key findings

```bash
# List all anomalies
./api_pipeline.sh list-anomalies

# Filter by severity
./api_pipeline.sh list-anomalies High 20

# Get detailed anomaly information
curl "http://localhost:8000/anomalies?severity=Critical&limit=5" | jq .
```

**Anomaly Format:**
```json
{
  "id": "anomaly-001",
  "timestamp": "2025-01-15T11:01:00Z",
  "model": "isolation_forest",
  "score": 0.92,
  "severity": "High",
  "original_data": {...},
  "details": {...}
}
```

## Step 8: Analyze with Intelligent Agents

### Basic Agent Analysis
```bash
# Analyze detected anomalies
./api_pipeline.sh analyze data/input/anomalies_detailed.json
```

### Detailed Analysis with Dialogue
```bash
# Run detailed analysis including agent dialogue
./api_pipeline.sh analyze data/input/anomalies_detailed.json --detailed
```

**Agent Analysis Process:**
1. **Security Analyst** - Initial assessment
2. **Threat Intelligence** - Threat correlation
3. **Remediation Expert** - Response planning
4. **Code Generator** - Automation scripts
5. **Security Reviewer** - Validation
6. **Data Collector** - Additional requirements

**Sample Output:**
```
=== Agent Analysis Summary ===
Anomalies Analyzed: 3
Total Agent Dialogues: 18

Average Agent Confidence:
- security_analyst: 85%
- threat_intel: 78%
- remediation: 82%

=== Anomaly: anomaly-001 ===
Severity: Critical
Threat Type: Crypto Mining
False Positive: false
Consensus: High confidence crypto mining activity detected
```

## Step 9: Real-time Monitoring

### Option A: Command Line Monitoring
```bash
# Monitor for 60 seconds
./api_pipeline.sh monitor 60
```

### Option B: WebSocket Connection
```python
# Python WebSocket client
import asyncio
import websockets
import json

async def monitor():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # Subscribe to alerts
        await websocket.send(json.dumps({
            "type": "subscribe",
            "topics": ["alerts", "anomalies"]
        }))
        
        # Receive updates
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Update: {data}")

asyncio.run(monitor())
```

## Step 10: Export and Review Results

```bash
# Export all results
./api_pipeline.sh export

# View export directory
ls -la results/export_*/

# Generate summary report
cat results/export_*/summary.txt
```

## Interactive Mode Operation

For a guided experience, use interactive mode:

```bash
./api_pipeline.sh interactive
```

**Menu Options:**
1. System Operations (health, init, status)
2. Data Management (create, process, list)
3. Model Operations (list, create, train)
4. Anomaly Detection (detect, bulk, list)
5. Agent Analysis (analyze, workflow, status)
6. Utilities (pipeline, cleanup, export)

## Complete Pipeline Example

Run the entire pipeline automatically:

```bash
./api_pipeline.sh pipeline
```

**This executes:**
1. System health check
2. Initialization
3. Data creation
4. Model training (2 models)
5. Anomaly detection
6. Agent analysis
7. Real-time monitoring (10 seconds)
8. Results export

## Troubleshooting Common Issues

### Issue: "Model not trained yet"
```bash
# Solution: Train the model first
./api_pipeline.sh train isolation_forest_model data/input/training_data_normal.json
```

### Issue: "Agent manager not initialized"
```bash
# Solution: Check Ollama is running
curl http://localhost:11434/api/tags

# Reinitialize system
./api_pipeline.sh init
```

### Issue: "Database connection failed"
```bash
# Solution: Check PostgreSQL
sudo systemctl status postgresql

# Test database connection
curl http://localhost:8000/database/status
```

## Next Steps

1. **Customize Models**: Adjust model parameters in `config.yaml`
2. **Add Data Sources**: Configure additional collectors (Kafka, SQL, REST)
3. **Set Up Alerts**: Configure email/webhook alerts for critical anomalies
4. **Tune Thresholds**: Adjust detection thresholds based on false positive rates
5. **Extend Agents**: Customize agent prompts for your specific use case

## Quick Reference Card

```bash
# Essential Commands
./api_pipeline.sh health          # Check system
./api_pipeline.sh init            # Initialize
./api_pipeline.sh create-data     # Create sample data
./api_pipeline.sh train <model>   # Train model
./api_pipeline.sh detect <model>  # Detect anomalies
./api_pipeline.sh analyze <file>  # Agent analysis
./api_pipeline.sh monitor         # Real-time monitoring
./api_pipeline.sh pipeline        # Run everything

# Useful Endpoints
GET  /                     # Health check
POST /init                 # Initialize system
GET  /models              # List models
POST /models/{name}/train # Train model
POST /models/{name}/detect # Detect anomalies
GET  /anomalies           # List anomalies
POST /agents/analyze      # Agent analysis
WS   /ws                  # WebSocket connection


Agent System Troubleshooting Guide
Issue: "Agent manager not initialized"
This error occurs when the agent system is not properly set up. Here's how to fix it:
Step 1: Check Ollama Installation
The agent system requires Ollama to be installed and running.
bash# Check if Ollama is installed
ollama --version

# If not installed, install it:
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve
Step 2: Pull Required Model
bash# Pull the Mistral model (or the model specified in your config)
ollama pull mistral

# Verify model is available
ollama list
Step 3: Verify Ollama is Running
bash# Check if Ollama API is accessible
curl http://localhost:11434/api/tags

# Expected response:
# {"models":[{"name":"mistral:latest","size":4109801984,...}]}
Step 4: Update Configuration
Ensure your config.yaml has agents enabled:
yamlagents:
  enabled: true  # This MUST be true
  llm:
    provider: ollama
    model: mistral
    base_url: http://localhost:11434
  # ... rest of agent configuration
Step 5: Restart API Server
After updating the configuration, restart the API server:
bash# Stop the current server (Ctrl+C or kill the process)
# Restart with the updated config
python api_services.py --config config/config.yaml --auto-init
Step 6: Verify Agent System Status
bash# Check agent status
curl http://localhost:8000/agents/status

# Expected response:
# {"enabled": true, "configured": true, ...}
Alternative: Run Without Agents
If you don't need agent analysis, you can run the pipeline without it:
Option 1: Disable in Config
yamlagents:
  enabled: false  # Disable agents entirely
Option 2: Skip Agent Analysis
bash# Run pipeline phases individually, skipping agent analysis
./api_pipeline.sh health
./api_pipeline.sh init
./api_pipeline.sh create-data
./api_pipeline.sh train isolation_forest_model data/input/training_data_normal.json
./api_pipeline.sh detect isolation_forest_model data/input/detection_data_mixed.json
./api_pipeline.sh list-anomalies
Common Issues and Solutions
1. Ollama Connection Refused
Error: connect ECONNREFUSED 127.0.0.1:11434
Solution: Start Ollama service
bash# In a separate terminal
ollama serve

# Or as a background service
nohup ollama serve > ollama.log 2>&1 &
2. Model Not Found
Error: model 'mistral' not found
Solution: Pull the model
bashollama pull mistral
3. Configuration Not Loaded
Error: Agent configuration not found
Solution: Ensure proper YAML formatting
yaml# Correct indentation is crucial
agents:
  enabled: true
  llm:
    provider: ollama
    model: mistral
    base_url: http://localhost:11434
4. Memory Issues
Error: Out of memory
Solution: Use a smaller model
bash# Use a smaller model like phi
ollama pull phi
# Update config.yaml to use 'phi' instead of 'mistral'
Quick Diagnostic Script
Save this as check_agents.sh:
bash#!/bin/bash

echo "=== Agent System Diagnostic ==="

# 1. Check Ollama
echo -n "1. Checking Ollama installation... "
if command -v ollama &> /dev/null; then
    echo "✓ Installed"
else
    echo "✗ Not installed"
    echo "   Run: curl -fsSL https://ollama.ai/install.sh | sh"
fi

# 2. Check Ollama service
echo -n "2. Checking Ollama service... "
if curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "✓ Running"
else
    echo "✗ Not running"
    echo "   Run: ollama serve"
fi

# 3. Check models
echo -n "3. Checking Ollama models... "
models=$(curl -s http://localhost:11434/api/tags 2>/dev/null | grep -o '"name":"[^"]*"' | wc -l)
if [ "$models" -gt 0 ]; then
    echo "✓ $models model(s) found"
    curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"'
else
    echo "✗ No models found"
    echo "   Run: ollama pull mistral"
fi

# 4. Check API server
echo -n "4. Checking API server... "
if curl -s http://localhost:8000/ &> /dev/null; then
    echo "✓ Running"
else
    echo "✗ Not running"
    echo "   Run: python api_services.py --config config/config.yaml"
fi

# 5. Check agent status
echo -n "5. Checking agent system... "
agent_status=$(curl -s http://localhost:8000/agents/status 2>/dev/null)
if echo "$agent_status" | grep -q '"enabled":true'; then
    echo "✓ Enabled"
else
    echo "✗ Not enabled"
    echo "   Check agents.enabled in config.yaml"
fi

echo ""
echo "=== Diagnostic Complete ==="
Make it executable:
bashchmod +x check_agents.sh
./check_agents.sh
Working Without Ollama
If you can't install Ollama, you can still use the anomaly detection features without agent analysis:
bash# Use the pipeline without agents
./api_pipeline.sh demo  # Will skip agent analysis automatically

# Or run specific commands
./api_pipeline.sh train isolation_forest_model data/training.json
./api_pipeline.sh detect isolation_forest_model data/test.json
./api_pipeline.sh list-anomalies
The system will still:

✓ Train ML models
✓ Detect anomalies
✓ Store results
✓ Generate alerts
✗ Provide agent-based analysis (requires Ollama)
```

