# API Architecture Deep Dive Analysis

## Overview

This document provides a comprehensive analysis of `api_services.py` (FastAPI server) and `api_client.py` (CLI client), explaining their architecture, workflows, and how they interact.

---

## 1. API Client (`api_client.py`)

### Purpose
The API client is a **command-line interface** that provides a Python client library and CLI tool to interact with the anomaly detection API service.

### Architecture

#### Core Class: `AnomalyDetectionClient`
- **Base URL**: Configurable (default: `http://localhost:8000`)
- **WebSocket Support**: Automatic conversion of HTTP to WebSocket URLs
- **Error Handling**: Comprehensive exception handling with detailed error messages

#### Key Methods by Category

##### System Management
- `health_check()` → `GET /`
- `initialize_system(config_path, auto_init)` → `POST /init`
- `get_config()` → `GET /config`
- `system_status()` → `GET /system/status`
- `shutdown_system()` → `POST /system/shutdown`
- `cleanup_system()` → `POST /system/cleanup`

##### Model Management
- `list_models()` → `GET /models`
- `create_model(model_type, config)` → `POST /models/create`
- `train_model(model_name, data)` → `POST /models/{model_name}/train`
- `delete_model(model_name)` → `DELETE /models/{model_name}`
- `load_models_from_storage()` → `POST /models/load-from-storage`
- `list_saved_model_files()` → `GET /models/saved-files`

##### Anomaly Detection
- `detect_anomalies(model_name, data, threshold)` → `POST /models/{model_name}/detect`
- `detect_anomalies_simple(model_name, data, threshold)` → `POST /detect`
- `bulk_detect_anomalies(models, data)` → `POST /bulk-detect`
- `list_anomalies(...)` → `GET /anomalies`
- `store_anomalies(anomalies)` → `POST /anomalies/store`

##### Data Processing
- `process_data(data)` → `POST /data/process`
- `normalize_data(data)` → `POST /processors/normalize`
- `extract_features(data)` → `POST /processors/extract_features`
- `store_processed_data(data)` → `POST /data/store`
- `load_processed_data(latest)` → `GET /data/load`

##### Correlation Analysis
- `correlate_anomalies(anomaly_id, ...)` → `POST /anomalies/correlate` (async)
- `get_anomaly_correlations(anomaly_id, ...)` → `GET /anomalies/{anomaly_id}/correlations` (sync)
- `bulk_correlate_anomalies(anomaly_ids, ...)` → `POST /anomalies/bulk-correlate`
- `generate_correlation_matrix(anomaly_ids, ...)` → `POST /anomalies/correlation-matrix`
- `get_correlation_statistics(...)` → `GET /anomalies/correlation-stats`

##### Agent Analysis
- `analyze_with_agents(anomalies)` → `POST /agents/analyze`
- `analyze_with_agents_verbose(anomalies, ...)` → `POST /agents/verbose-analyze`
- `analyze_with_agents_detailed(anomalies, ...)` → `POST /agents/analyze-detailed`
- `get_agent_workflow()` → `GET /agents/workflow`
- `get_agent_details(agent_name)` → `GET /agents/{agent_name}`
- `get_agent_activities(job_id)` → `GET /agents/activities/{job_id}`
- `get_agent_analysis_steps(job_id)` → `GET /agents/steps/{job_id}`

##### Job Management
- `get_job_status(job_id)` → `GET /jobs/{job_id}`
- `list_jobs(status, job_type, limit)` → `GET /jobs`
- `wait_for_job(job_id, timeout, poll_interval)` → Polls job status until completion
- `get_job_results(job_id)` → `GET /results/{job_id}`

##### Collectors & Processors
- `list_collectors()` → `GET /collectors`
- `collect_data(collector_name)` → `POST /collectors/{collector_name}/collect`
- `list_processors()` → `GET /processors`
- `get_processors_status()` → `GET /processors/status`

##### Database & Storage
- `check_database_status()` → `GET /database/status`
- `check_database_health()` → `GET /database/health`

##### Data Utilities
- `split_data(args)` → **Local operation** (not API call)
  - Splits data into train/validation sets
  - Handles multiple data formats (dict, list, nested structures)
  - Saves to specified output files
  
- `generate_data(args)` → **Local operation** (not API call)
  - Generates synthetic test data
  - Creates normal and anomaly records
  - Outputs plain array format (pipeline compatible)
  - Creates separate metadata file

##### Export & Utilities
- `export_anomalies(format, ...)` → `GET /export/anomalies`
- `get_stream_status()` → `GET /stream/status`

### CLI Interface

The `main()` function provides a comprehensive CLI with subcommands:

```bash
# System
python api_client.py init config/config.yaml
python api_client.py health
python api_client.py system-status

# Models
python api_client.py list-models
python api_client.py train-model isolation_forest_model data/train.json --wait
python api_client.py create-model isolation_forest config/isolation_forest.json

# Detection
python api_client.py detect-anomalies isolation_forest_model data/test.json --wait
python api_client.py bulk-detect model1 model2 data/test.json --wait

# Data Processing
python api_client.py process-data data/input.json
python api_client.py normalize-data data/input.json
python api_client.py extract-features data/input.json

# Agents
python api_client.py analyze-with-agents anomalies.json --wait
python api_client.py analyze-with-agents-verbose anomalies.json
python api_client.py agent-workflow

# Jobs
python api_client.py job-status <job_id>
python api_client.py list-jobs --status completed

# Utilities
python api_client.py split-data input.json --train-output train.json --val-output val.json
python api_client.py generate-data --output data/test.json --count 1000 --anomaly-ratio 0.3
```

### Key Features

1. **Automatic Job Polling**: Methods like `wait_for_job()` automatically poll for completion
2. **Error Handling**: Detailed error messages with connection status checks
3. **Data Loading**: `load_json_data()` helper handles various JSON formats
4. **WebSocket Support**: `WebSocketConnection` class for real-time updates
5. **Local Operations**: `split_data()` and `generate_data()` run locally (not API calls)

---

## 2. API Services (`api_services.py`)

### Purpose
The API service is a **FastAPI-based REST API server** that provides all the backend functionality for the anomaly detection system.

### Architecture

#### FastAPI Application
- **Framework**: FastAPI with async/await support
- **Lifespan Management**: `@asynccontextmanager` for startup/shutdown
- **CORS**: Enabled for all origins
- **Version**: 2.1.0

#### Global State Management

```python
# Global variables (initialized during startup)
config = None                    # System configuration
storage_manager = None          # Database/storage manager
models = {}                     # Dictionary of ML models
processors = {}                 # Data processors (normalizers, feature extractors)
collectors = {}                 # Data collectors
agent_manager = None            # AI agent manager
background_jobs = {}            # Background job tracking
background_jobs_lock = threading.Lock()  # Thread safety
alert_manager = None            # Alert manager
last_training_data = {}         # Cache of training data
```

#### System Initialization Flow

1. **`initialize_system(config_dict)`** - Called during `/init` endpoint:
   - Loads configuration from YAML/JSON
   - Initializes `StorageManager` (connection deferred to async startup)
   - Creates model instances based on config:
     - IsolationForestModel
     - OneClassSVMModel
     - AutoencoderModel
     - GANAnomalyDetector
     - EnsembleModel
     - StatisticalModel
   - Auto-loads saved models from `storage/models/` directory
   - Initializes processors (normalizers, feature extractors)
   - Initializes collectors (file, kafka, sql, rest_api)
   - Initializes AgentManager (if enabled)
   - Initializes AlertManager (if enabled)

2. **Lifespan Startup** (`lifespan()` function):
   - Connects to database (async-safe)
   - Creates database tables
   - Starts background sync task

3. **Lifespan Shutdown**:
   - Closes database connections
   - Cleans up resources

### Background Jobs System

All long-running operations use background jobs:

#### Job Structure
```python
{
    "job_id": "uuid",
    "type": "train|detect|collect|analyze|correlate",
    "status": "pending|running|completed|failed",
    "progress": 0.0-1.0,
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "end_time": "timestamp",
    "result": {...},
    "error": "error message"
}
```

#### Background Job Functions

1. **`train_model_job(model_name, data, job_id)`**
   - Processes data (normalization + feature extraction)
   - Trains the model
   - Saves model to storage
   - **Emergency fix**: Also saves directly to disk (`storage/models/`)
   - Updates job status

2. **`detect_anomalies_job(model_name, data_items, job_id, threshold)`**
   - Validates model is trained
   - Processes data
   - Runs detection
   - Stores anomalies in database
   - Sends alerts for high-severity anomalies
   - Updates job status

3. **`bulk_detect_anomalies_job(model_names, data_items, job_id)`**
   - Runs detection across multiple models
   - Aggregates results
   - Stores all anomalies

4. **`collect_data_job(collector_name, job_id)`**
   - Uses specified collector to gather data
   - Stores collected data

5. **`agent_analysis_job(anomalies, job_id)`**
   - Basic agent analysis
   - Stores analysis results

6. **`verbose_agent_analysis_job(anomalies, job_id)`**
   - Enhanced agent analysis with verbose output
   - Tracks agent activities
   - Calculates severity statistics

7. **`detailed_agent_analysis_job(anomalies, job_id, include_dialogue, include_evidence)`**
   - Most detailed agent analysis
   - Includes agent dialogue and evidence chains
   - Calculates confidence scores

8. **`correlation_analysis_job(anomaly_id, time_window, min_score, max_results, job_id)`**
   - Analyzes correlations for a single anomaly
   - Finds related anomalies within time window
   - Calculates correlation scores

### Key API Endpoints

#### System Endpoints
- `GET /` - Root/health check
- `GET /health` - Health check
- `POST /init` - Initialize system
- `GET /config` - Get configuration
- `GET /system/status` - System status
- `POST /system/shutdown` - Shutdown system
- `POST /system/cleanup` - Cleanup temporary files

#### Model Endpoints
- `GET /models` - List all models
- `POST /models/create` - Create new model
- `POST /models/{model_name}/train` - Train model (background job)
- `POST /models/{model_name}/detect` - Detect anomalies (background job)
- `DELETE /models/{model_name}` - Delete model
- `POST /models/load-from-storage` - Load saved models
- `GET /models/saved-files` - List saved model files

#### Detection Endpoints
- `POST /detect` - Simplified detection endpoint
- `POST /bulk-detect` - Multi-model detection (background job)

#### Anomaly Endpoints
- `GET /anomalies` - List anomalies (with filters)
- `POST /anomalies/store` - Store anomalies explicitly
- `POST /anomalies/correlate` - Correlate anomaly (background job)
- `GET /anomalies/{anomaly_id}/correlations` - Get correlations (sync)
- `POST /anomalies/bulk-correlate` - Bulk correlation
- `POST /anomalies/correlation-matrix` - Generate correlation matrix
- `GET /anomalies/correlation-stats` - Correlation statistics

#### Agent Endpoints
- `GET /agents/status` - Agent system status
- `GET /agents/test` - Test endpoint
- `POST /agents/analyze` - Basic agent analysis (background job)
- `POST /agents/verbose-analyze` - Verbose agent analysis (background job)
- `POST /agents/analyze-detailed` - Detailed agent analysis (background job)
- `GET /agents/workflow` - Get agent workflow
- `GET /agents/{agent_name}` - Get agent details
- `GET /agents/activities/{job_id}` - Get agent activities
- `GET /agents/steps/{job_id}` - Get analysis steps
- `GET /agents/dialogue/{job_id}/{anomaly_id}` - Get agent dialogue

#### Data Processing Endpoints
- `POST /data/process` - Process data through pipeline
- `POST /processors/normalize` - Normalize data
- `POST /processors/extract_features` - Extract features
- `POST /data/store` - Store processed data
- `GET /data/load` - Load processed data
- `GET /processors/status` - Processor status

#### Collector Endpoints
- `GET /collectors` - List collectors
- `POST /collectors/{collector_name}/collect` - Collect data (background job)
- `GET /debug/collectors` - Debug collector info

#### Job Endpoints
- `GET /jobs/{job_id}` - Get job status
- `GET /jobs` - List jobs (with filters)
- `GET /results/{job_id}` - Get detailed job results

#### Database Endpoints
- `GET /database/status` - Database status
- `GET /database/health` - Database health check (with auto-recovery)

#### Export Endpoints
- `GET /export/anomalies` - Export anomalies (JSON/CSV)

#### WebSocket
- `WS /ws` - WebSocket connection for real-time updates

### Data Processing Pipeline

The system uses a **processor pipeline**:

1. **Normalizers** - Normalize data (timestamps, numerical values)
2. **Feature Extractors** - Extract features from raw data
   - Handles numerical, categorical, boolean, text fields
   - Supports one-hot encoding for categorical data
   - Nested field support (e.g., `data.field.subfield`)

### Model Training Flow

1. Client calls `POST /models/{model_name}/train` with data
2. Server creates background job
3. `train_model_job()` executes:
   - Applies normalizers to data
   - Applies feature extractors
   - Calls `model.train(processed_data)`
   - Saves model via `storage_manager.save_model()`
   - **Emergency fix**: Also saves directly to disk
   - Updates job status to "completed"

### Anomaly Detection Flow

1. Client calls `POST /models/{model_name}/detect` with data
2. Server creates background job
3. `detect_anomalies_job()` executes:
   - Validates model is trained
   - Applies normalizers and feature extractors
   - Calls `model.detect(processed_data)`
   - Enhances anomalies with severity, location, timestamps
   - Stores anomalies in database
   - Sends alerts for high-severity anomalies
   - Updates job status

### Correlation Analysis

The system provides sophisticated correlation analysis:

1. **Time-based correlation**: Finds anomalies within a time window
2. **Feature-based correlation**: Compares anomaly features
3. **Location-based correlation**: Groups by location
4. **Score-based correlation**: Uses anomaly scores

Functions:
- `find_correlations()` - Main correlation finding logic
- `calculate_pairwise_correlation()` - Calculates correlation score between two anomalies
- `build_correlation_matrix()` - Creates correlation matrix for multiple anomalies

### Agent System Integration

The agent system provides intelligent analysis of anomalies:

1. **AgentManager** - Manages multiple AI agents:
   - Security Analyst
   - Threat Intelligence
   - Remediation Specialist

2. **Analysis Modes**:
   - Basic: Simple analysis
   - Verbose: Detailed with activity tracking
   - Detailed: Full dialogue and evidence chains

3. **Visualization**: `VerboseVisualizer` tracks all agent activities

---

## 3. How They Work Together

### Command Flow Example: Training a Model

```
1. User runs: python api_client.py train-model isolation_forest_model data/train.json --wait

2. api_client.py:
   - Loads data from data/train.json
   - Calls client.train_model("isolation_forest_model", data)
   - Makes POST request to http://localhost:8000/models/isolation_forest_model/train

3. api_services.py:
   - Receives request at POST /models/{model_name}/train
   - Creates background job with unique job_id
   - Returns job_id immediately
   - Starts train_model_job() in background

4. Background Job (train_model_job):
   - Processes data (normalization + feature extraction)
   - Trains model
   - Saves model to storage
   - Updates job status to "completed"

5. api_client.py (if --wait):
   - Polls GET /jobs/{job_id} until status is "completed"
   - Displays final result
```

### Command Flow Example: Detecting Anomalies

```
1. User runs: python api_client.py detect-anomalies isolation_forest_model data/test.json

2. api_client.py:
   - Loads data from data/test.json
   - Calls client.detect_anomalies("isolation_forest_model", data)
   - Makes POST request to http://localhost:8000/models/isolation_forest_model/detect

3. api_services.py:
   - Receives request
   - Creates background job
   - Returns job_id
   - Starts detect_anomalies_job() in background

4. Background Job:
   - Validates model is trained
   - Processes data
   - Runs detection
   - Stores anomalies in database
   - Sends alerts
   - Updates job status

5. User can check status: python api_client.py job-status <job_id>
```

### Data Processing Command Flow

```
1. User runs: python api_client.py process-data data/input.json

2. api_client.py:
   - Loads JSON data
   - Calls client.process_data(data)
   - Makes POST request to http://localhost:8000/data/process

3. api_services.py:
   - Receives data at POST /data/process
   - Applies all processors (normalizers + feature extractors)
   - Returns processed data immediately (synchronous)

4. api_client.py:
   - Prints processed data as JSON
```

### Local Operations (No API Call)

Some operations run entirely in the client:

1. **`split-data`**: Splits data locally, saves to files
2. **`generate-data`**: Generates synthetic data locally, saves to files

These don't require the API server to be running.

---

## 4. Key Implementation Details

### Error Handling

**Client (`api_client.py`)**:
- Connection errors: Checks if server is running
- HTTP errors: Extracts detailed error messages from API
- Timeout errors: Configurable timeout (default 300s)

**Server (`api_services.py`)**:
- Try-catch blocks around all operations
- Detailed error logging
- HTTPException with status codes
- Background job errors stored in job result

### Thread Safety

- `background_jobs_lock` protects shared `background_jobs` dictionary
- Database operations use `asyncio.to_thread()` for sync operations
- Storage manager operations are thread-safe

### Model Persistence

Models are saved in multiple ways:
1. **Via StorageManager**: `storage_manager.save_model(model)`
2. **Direct to disk**: Emergency fix saves to `storage/models/` directory
   - `.pkl` file (complete model)
   - `.joblib` file (underlying sklearn model)
   - `_metadata.json` file (model metadata)

### Auto-Loading Models

On system initialization, the system:
1. Checks `storage/models/` directory
2. Finds `.pkl` and `.joblib` files
3. Determines model type from filename or metadata
4. Creates model instance
5. Loads model state
6. Adds to `models` dictionary

### Data Format Handling

The system handles multiple data formats:
- Plain arrays: `[{...}, {...}]`
- Wrapped structures: `{"items": [...], "raw_data": [...]}`
- Single objects: `{...}`

Feature extractors handle:
- Nested fields: `data.field.subfield`
- Multiple field types: numerical, categorical, boolean, text
- Missing values gracefully

### Background Job Synchronization

Jobs are synchronized to database:
- `sync_jobs_to_database()` runs periodically
- Stores job status, results, errors
- Allows job history persistence

---

## 5. Important Notes

### Metadata Files

The `generate-data` command creates:
- `data.json` - Plain array of records (for pipelines)
- `data_metadata.json` - Metadata about the dataset

**Pipelines should skip `*_metadata.json` files** (they're not data arrays).

### Model Training Status

Models track training status via:
- `model.is_trained` flag
- `model.model_state` dictionary
- Presence of underlying model object

### Detection Thresholds

- Default threshold: 0.5
- Can be overridden per detection request
- Threshold affects anomaly score interpretation

### Agent Analysis

Three levels of agent analysis:
1. **Basic**: Simple analysis result
2. **Verbose**: Includes activity tracking
3. **Detailed**: Includes dialogue and evidence chains

### Correlation Analysis

- **Time window**: Default 24 hours
- **Min correlation score**: Default 0.3
- **Correlation factors**: Time, features, location, score

---

## 6. Summary

### `api_client.py` (Client)
- **Purpose**: CLI tool and Python client library
- **Key Features**: 
  - Comprehensive command interface
  - Automatic job polling
  - Local data utilities (split, generate)
  - WebSocket support

### `api_services.py` (Server)
- **Purpose**: FastAPI REST API server
- **Key Features**:
  - Background job system
  - Model management
  - Data processing pipeline
  - Agent integration
  - Correlation analysis
  - Database persistence

### Integration
- Client makes HTTP requests to server
- Server processes requests (sync or async background jobs)
- Client polls for job completion when needed
- Both handle errors gracefully with detailed messages

This architecture provides a clean separation between client (CLI) and server (API), with comprehensive functionality for anomaly detection, model training, and intelligent analysis.

