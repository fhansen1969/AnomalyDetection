# Anomaly Detection System - API Commands Guide

## System Management

### Start/Stop System
```bash
# Start API server
python api_server.py --config config/production_config.yaml

# Check system health
python api_client.py health

# Get system status
python api_client.py system-status

# Shutdown system
python api_client.py shutdown-system
```

## Model Management

### List and Load Models
```bash
# List all models
python api_client.py list-models

# Load models from storage
python api_client.py load-models

# List model files
python api_client.py list-model-files

# Create new model
python api_client.py create-model <model_name> <model_type>

# Delete model
python api_client.py delete-model <model_name>
```

### Train Models
```bash
# Train a specific model
python api_client.py train-model <model_name> <training_data.json>

# Check training job status
python api_client.py job-status <job_id>

# List all jobs
python api_client.py list-jobs
```

## Anomaly Detection

### Run Detection
```bash
# Detect anomalies with specific model
python api_client.py detect-anomalies <model_name> <data_file.json>

# Simple detection (uses default model)
python api_client.py detect-simple <data_file.json>

# Bulk detection
python api_client.py bulk-detect <model_name> <data_directory>

# Detailed analysis
python api_client.py analyze-detailed <model_name> <data_file.json>
```

### Manage Anomalies
```bash
# List detected anomalies
python api_client.py list-anomalies --limit 100

# Store anomalies
python api_client.py store-anomalies <anomalies.json>

# Export anomalies
python api_client.py export-anomalies --format json --output anomalies_export.json
```

## Correlation Analysis

```bash
# Check correlation between two anomalies
python api_client.py correlate-anomaly <anomaly_id_1> <anomaly_id_2>

# Get correlations for an anomaly
python api_client.py get-correlations <anomaly_id> --threshold 0.5

# Bulk correlation analysis
python api_client.py bulk-correlate <anomaly_ids_file.json>

# Generate correlation matrix
python api_client.py correlation-matrix <anomaly_id_1> <anomaly_id_2> ...

# Get correlation statistics
python api_client.py correlation-stats --time-window 3600 --min-score 0.5
```

## Alert Configuration

```bash
# Update alert configuration
python api_client.py update-alert-config <alert_name> <config_file.json>

# Test alert
python api_client.py test-alert <alert_name>
```

### Example Alert Configuration File:
```json
{
  "alert_name": "high_severity_network",
  "severity_threshold": 0.8,
  "enabled": true,
  "notification_channels": ["email", "slack"],
  "cooldown_period": 300,
  "aggregation_window": 60,
  "filters": {
    "alert_type": ["DDoS_suspected", "data_exfiltration_suspected"]
  }
}
```

## Data Processing

```bash
# Collect data from source
python api_client.py collect-data <source_name> --continuous

# List data collectors
python api_client.py list-collectors

# Process data through pipeline
python api_client.py process-data <input_file.json> --output processed.json

# Normalize data
python api_client.py normalize-data <raw_data.json>

# Extract features
python api_client.py extract-features <normalized_data.json>
```

## Agent Analysis

```bash
# Analyze with AI agents
python api_client.py analyze-with-agents <anomaly_id>

# Get agent workflow details
python api_client.py agent-workflow <anomaly_id>

# Test agents
python api_client.py test-agents

# Get agent status
python api_client.py agents-status

# Verbose agent analysis
python api_client.py analyze-with-agents-verbose <anomaly_id>
```

## Database Operations

```bash
# Check database status
python api_client.py database-status

# Check database health
python api_client.py database-health

# Store data
python api_client.py store-data <data_file.json>

# Load data
python api_client.py load-data --type anomalies --limit 100
```

## Monitoring and Debugging

```bash
# Stream real-time status
python api_client.py stream-status

# Debug collectors
python api_client.py debug-collectors

# Get processor status
python api_client.py processor-status <processor_name>

# List processors
python api_client.py list-processors

# Get job results
python api_client.py job-results <job_id>
```

## Example Workflows

### 1. Deploy Models to Production
```bash
# Start server
python api_server.py --config config/production_config.yaml

# Load trained models
python api_client.py load-models

# Configure alerts
python api_client.py update-alert-config network_anomaly network_alert.json
python api_client.py update-alert-config sw_severity sw_alert.json

# Start monitoring
python api_client.py stream-status
```

### 2. Run Anomaly Detection
```bash
# Process new data
python api_client.py normalize-data raw_data.json > normalized.json
python api_client.py extract-features normalized.json > features.json

# Detect anomalies
python api_client.py detect-anomalies statistical_model features.json

# Check results
python api_client.py list-anomalies --limit 10
```

### 3. Analyze Correlations
```bash
# Get recent anomalies
python api_client.py list-anomalies --limit 100 > anomalies.json

# Extract IDs and analyze
python api_client.py correlation-stats --time-window 3600

# Check specific correlation
python api_client.py correlate-anomaly anomaly_001 anomaly_002
```

## Configuration Options

Most commands support additional options:
- `--url`: API server URL (default: http://localhost:5000)
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `--help`: Show help for any command

Example:
```bash
python api_client.py --url http://prod-server:5000 --log-level DEBUG list-models
```
