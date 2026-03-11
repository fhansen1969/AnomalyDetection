# Pipelines Subdirectory Analysis

## Overview

The `pipelines/` subdirectory contains a comprehensive set of bash scripts that orchestrate the entire anomaly detection workflow from data generation through production detection. All pipelines use a common library (`lib_common.sh`) for shared functionality.

---

## Pipeline Scripts Inventory

### Core Pipeline Scripts

1. **`run_pipelines.sh`** - Master orchestrator
2. **`training_pipeline.sh`** - Model training pipeline
3. **`test_pipeline.sh`** - Model testing and evaluation
4. **`validation_pipeline.sh`** - Model validation pipeline
5. **`detect_anomalies_pipeline.sh`** - Production detection pipeline

**Note:** Data generation is handled automatically by the main pipelines using `api_client.py generate-data` when data is missing.

### Documentation

- `PIPELINE_README.md` - User guide
- `PIPELINE_DETAILS.md` - Technical details
- `PIPELINE_MASTER.md` - Master pipeline documentation
- `pipeline_architecture.svg` - Architecture diagram

---

## 1. Master Pipeline (`run_pipelines.sh`)

### Purpose
Orchestrates all pipeline stages in sequence, managing execution, timing, error handling, and reporting.

### Key Features
- **Stage Coordination**: Executes training, testing, validation, and detection pipelines
- **Error Handling**: `STOP_ON_ERROR` flag controls whether to continue on failure
- **Timing Tracking**: Tracks duration for each stage
- **Cleanup Control**: Per-stage cleanup flags
- **Comprehensive Reporting**: Generates summary reports

### Configuration
```bash
CONFIG_FILE="${CONFIG_FILE:-config/config.yaml}"
RUN_TRAINING=${RUN_TRAINING:-true}
RUN_TESTING=${RUN_TESTING:-true}
RUN_VALIDATION=${RUN_VALIDATION:-true}
RUN_DETECTION=${RUN_DETECTION:-false}
CLEANUP_TRAINING=${CLEANUP_TRAINING:-true}
STOP_ON_ERROR=${STOP_ON_ERROR:-true}
```

### Execution Flow
1. Check prerequisites
2. Execute training pipeline (if enabled)
3. Execute testing pipeline (if enabled)
4. Execute validation pipeline (if enabled)
5. Execute detection pipeline (if enabled)
6. Generate summary report

### Usage
```bash
# Run all pipelines
bash pipelines/run_pipelines.sh

# Run only training and testing
RUN_VALIDATION=false RUN_DETECTION=false bash pipelines/run_pipelines.sh

# Continue on errors
STOP_ON_ERROR=false bash pipelines/run_pipelines.sh
```

---

## 2. Training Pipeline (`training_pipeline.sh`)

### Purpose
Complete ML model training workflow from data collection through model export.

### Pipeline Stages

#### Stage 1: Data Collection
- Collects training data from `data/training/`
- Auto-generates synthetic data if none exists (2000 records, 30% anomalies)
- **FIX**: Skips `*_metadata.json` files

#### Stage 2: Data Preprocessing
- Processes each data file through `api_client.py process-data`
- Validates JSON files (must be arrays)
- **FIX**: Skips metadata files
- Output: `data/processed/training/preprocessed_*.json`

#### Stage 3: Feature Engineering
- Extracts features from preprocessed data
- Uses `api_client.py extract-features`
- Output: `data/processed/training/features_*.json`

#### Stage 4: Data Splitting
- Splits data into train/validation sets
- Uses `api_client.py split-data`
- Output: `train_split.json`, `val_split.json`

#### Stage 5: Model Training
- Trains all configured models
- Uses `api_client.py train-model` with `--wait` flag
- Tracks training jobs and waits for completion
- Models saved to `storage/models/`

#### Stage 6: Model Export and Verification
- Verifies model files exist on disk
- Checks model status via API
- Lists all saved model files
- Verifies model metadata

#### Stage 7: Generate Report
- Creates training summary report
- Includes model training statistics
- Saves to `reports/training/`

### Key Features
- **Anomaly Cleanup**: Removes anomalies created during training (baseline tracking)
- **Model Status Verification**: Ensures models are marked as "trained"
- **Comprehensive Logging**: All operations logged to timestamped log files

### Configuration
```bash
CONFIG_FILE="${1:-config/config.yaml}"
DATA_DIR="data/training"
PROCESSED_DIR="data/processed/training"
MODELS_DIR="storage/models"  # FIX: Central models directory
REPORTS_DIR="reports/training"

# Skip flags
SKIP_COLLECTION=${SKIP_COLLECTION:-false}
SKIP_PREPROCESSING=${SKIP_PREPROCESSING:-false}
SKIP_FEATURE_ENG=${SKIP_FEATURE_ENG:-false}
SKIP_SPLITTING=${SKIP_SPLITTING:-false}
SKIP_TRAINING=${SKIP_TRAINING:-false}
SKIP_EXPORT=${SKIP_EXPORT:-false}
CLEANUP_ANOMALIES=${CLEANUP_ANOMALIES:-true}
```

### Usage
```bash
# Full training pipeline
bash pipelines/training_pipeline.sh config/config.yaml

# Skip preprocessing if already done
SKIP_PREPROCESSING=true bash pipelines/training_pipeline.sh

# With cleanup disabled
CLEANUP_ANOMALIES=false bash pipelines/training_pipeline.sh
```

---

## 3. Test Pipeline (`test_pipeline.sh`)

### Purpose
Evaluates trained models on test data, performs correlation testing, and performance benchmarking.

### Pipeline Stages

#### Stage 1: Test Data Preparation
- Checks for test data in `data/test/`
- Auto-generates if missing (1000 records, 20% anomalies)
- **FIX**: Skips `*_metadata.json` files
- Processes data through pipeline
- Output: `data/processed/test/processed_*.json`

#### Stage 2: Model Evaluation
- Lists all available models via API
- **FIX**: Improved model detection (handles "not_trained" status)
- Evaluates only trained models
- Uses `api_client.py detect-anomalies` with `--wait`
- Generates evaluation reports
- Output: `reports/test/evaluation_report_*.txt`

#### Stage 3: Correlation Testing
- Tests correlation detection capabilities
- Creates synthetic correlated anomalies
- Validates correlation matrix generation
- Reports correlation test results
- Output: `reports/test/correlation_test_*.md`

#### Stage 4: Performance Testing
- Tests model performance on test data
- Measures detection speed
- Tests on different dataset sizes
- Generates performance reports
- Output: `reports/test/performance_test_*.txt`

#### Stage 5: Generate Report
- Creates comprehensive test summary
- Includes evaluation, correlation, and performance results
- Output: `reports/test/test_summary_*.md`

### Key Features
- **Model Status Handling**: Works with models that have "not_trained" status but are actually trained
- **Correlation Testing**: Validates correlation analysis capabilities
- **Performance Benchmarking**: Tests model speed and scalability

### Configuration
```bash
CONFIG_FILE="${1:-config/config.yaml}"
TEST_DATA_DIR="data/test"
PROCESSED_DIR="data/processed/test"
MODELS_DIR="storage/models"
REPORTS_DIR="reports/test"

SKIP_DATA_PREP=${SKIP_DATA_PREP:-false}
SKIP_EVALUATION=${SKIP_EVALUATION:-false}
SKIP_CORRELATION=${SKIP_CORRELATION:-false}
SKIP_PERFORMANCE=${SKIP_PERFORMANCE:-false}
CLEANUP_ANOMALIES=${CLEANUP_ANOMALIES:-true}
```

### Usage
```bash
# Full test pipeline
bash pipelines/test_pipeline.sh config/config.yaml

# Skip correlation testing
SKIP_CORRELATION=true bash pipelines/test_pipeline.sh

# Only evaluate models
SKIP_CORRELATION=true SKIP_PERFORMANCE=true bash pipelines/test_pipeline.sh
```

---

## 4. Validation Pipeline (`validation_pipeline.sh`)

### Purpose
Validates trained models on holdout datasets before production deployment.

### Pipeline Stages

#### Stage 1: Data Collection for Validation
- Collects validation data from `data/validation/`
- Auto-generates if missing (500 records, 25% anomalies)
- **FIX**: Skips `*_metadata.json` files during validation
- Validates data integrity (must be arrays)
- Output: Lists validation files with sizes

#### Stage 2: Data Preprocessing
- Processes validation data
- Uses `api_client.py process-data`
- Output: `data/processed/validation/processed_*.json`

#### Stage 3: Model Loading
- Loads trained models from storage
- Checks model status (prefers "trained" status)
- Falls back to all models if none marked as trained
- Lists models to validate

#### Stage 4: Model Validation
- Runs detection on validation data
- Uses `api_client.py detect-anomalies` with `--wait`
- Collects detection results
- Output: `reports/validation/validation_results_*.json`

#### Stage 5: Performance Metrics Calculation
- Calculates precision, recall, F1-score
- Calculates false positive rate
- Compares against validation thresholds
- Output: Metrics in validation results

#### Stage 6: Correlation Validation
- Tests correlation detection on validation anomalies
- Calculates correlation density metrics
- Validates cross-correlation functionality
- Output: Correlation validation results

#### Stage 7: Comparison with Baseline
- Compares validation results with baseline
- Checks for performance degradation
- Flags models that don't meet thresholds

#### Stage 8: Generate Validation Report
- Creates comprehensive validation report
- Includes metrics, correlation validation, baseline comparison
- Output: `reports/validation/validation_summary_*.md`

#### Stage 9: Model Promotion
- Promotes validated models to production
- Creates validation certificates
- Copies models to validated directory
- Output: `storage/models/validated/*_validation_cert.json`

### Key Features
- **Automatic Cleanup**: Removes validation anomalies after completion
- **Threshold Validation**: Configurable precision, recall, F1 thresholds
- **Correlation Validation**: Tests correlation capabilities
- **Model Promotion**: Automatically promotes validated models

### Configuration
```bash
CONFIG_FILE="${1:-config/validation_config.yaml}"
DATA_DIR="data/validation"
PROCESSED_DIR="data/processed/validation"
MODELS_DIR="storage/models"
VALIDATED_DIR="storage/models/validated"
REPORTS_DIR="reports/validation"

MIN_PRECISION=${MIN_PRECISION:-0.7}
MIN_RECALL=${MIN_RECALL:-0.6}
MIN_F1=${MIN_F1:-0.65}
MAX_FALSE_POSITIVE_RATE=${MAX_FALSE_POSITIVE_RATE:-0.3}
CLEANUP_ANOMALIES=${CLEANUP_ANOMALIES:-true}
```

### Usage
```bash
# Full validation pipeline
bash pipelines/validation_pipeline.sh config/validation_config.yaml

# With custom thresholds
MIN_PRECISION=0.8 MIN_RECALL=0.7 bash pipelines/validation_pipeline.sh

# Without cleanup
CLEANUP_ANOMALIES=false bash pipelines/validation_pipeline.sh
```

---

## 5. Detection Pipeline (`detect_anomalies_pipeline.sh`)

### Purpose
Production anomaly detection with real-time correlation analysis and alerting.

### Pipeline Stages

#### Stage 1: Load Production Models
- Loads validated models from storage
- Checks for model files on disk
- Lists available models with status
- Verifies agent system if enabled
- Output: List of production-ready models

#### Stage 2: Data Collection
- **Batch Mode**: Collects from `data/input/` directory
- **Real-time Mode**: Starts data collectors
- **Continuous Mode**: Monitors for new files
- Output: Collected data files

#### Stage 3: Feature Extraction
- Processes collected data
- Extracts features using configured processors
- Output: `data/processed/detection/processed_*.json`

#### Stage 4: Anomaly Detection
- Runs detection using production models
- Uses `api_client.py detect-anomalies` with `--wait`
- Stores detected anomalies
- Output: Anomalies stored in database and `storage/anomalies/`

#### Stage 5: Agent Analysis (if enabled)
- Analyzes anomalies using AI agents
- Uses `api_client.py analyze-with-agents` with `--wait`
- Provides intelligent analysis
- Output: Analysis results stored

#### Stage 6: Correlation Analysis (if enabled)
- Analyzes correlations between anomalies
- Uses correlation API endpoints
- Generates correlation matrices
- Identifies correlation clusters
- Output: `storage/correlations/correlation_*.json`

#### Stage 7: Send Alerts
- Sends alerts for high-severity anomalies
- Includes correlation insights in alerts
- Detects anomaly clusters
- Output: `storage/alerts/alert_*.txt`

#### Stage 8: Generate Report
- Creates detection summary report
- Includes anomaly counts, correlations, alerts
- Output: `reports/detection/detection_summary_*.md`

#### Continuous Monitoring Mode
- Monitors `data/input/` for new files every 60 seconds
- Processes only new files since last check
- Performs incremental correlation analysis
- Runs indefinitely until stopped

### Key Features
- **Multiple Modes**: Batch, real-time, continuous
- **Agent Integration**: Optional AI agent analysis
- **Correlation Analysis**: Real-time correlation detection
- **Alerting**: Configurable alert thresholds
- **Continuous Monitoring**: Long-running monitoring mode

### Configuration
```bash
CONFIG_FILE="${1:-config/config.yaml}"
DATA_DIR="data/input"
PROCESSED_DIR="data/processed/detection"
ANOMALIES_DIR="storage/anomalies"
ALERTS_DIR="storage/alerts"
CORRELATIONS_DIR="storage/correlations"

DETECTION_MODE=${DETECTION_MODE:-batch}  # batch|realtime
ENABLE_AGENTS=${ENABLE_AGENTS:-true}
ENABLE_ALERTS=${ENABLE_ALERTS:-true}
ENABLE_CORRELATION=${ENABLE_CORRELATION:-true}
CONTINUOUS_MODE=${CONTINUOUS_MODE:-false}

CRITICAL_THRESHOLD=${CRITICAL_THRESHOLD:-0.9}
HIGH_THRESHOLD=${HIGH_THRESHOLD:-0.8}
MEDIUM_THRESHOLD=${MEDIUM_THRESHOLD:-0.7}
LOW_THRESHOLD=${LOW_THRESHOLD:-0.5}

CORRELATION_TIME_WINDOW=${CORRELATION_TIME_WINDOW:-24}
MIN_CORRELATION_SCORE=${MIN_CORRELATION_SCORE:-0.3}
MAX_CORRELATION_RESULTS=${MAX_CORRELATION_RESULTS:-50}
```

### Usage
```bash
# Batch detection
bash pipelines/detect_anomalies_pipeline.sh config/config.yaml

# Real-time mode
DETECTION_MODE=realtime bash pipelines/detect_anomalies_pipeline.sh

# Continuous monitoring
CONTINUOUS_MODE=true bash pipelines/detect_anomalies_pipeline.sh

# Without agents or correlation
ENABLE_AGENTS=false ENABLE_CORRELATION=false bash pipelines/detect_anomalies_pipeline.sh

# Custom thresholds
CRITICAL_THRESHOLD=0.95 CORRELATION_TIME_WINDOW=48 bash pipelines/detect_anomalies_pipeline.sh
```

---

## Data Generation

**Note:** Data generation is handled automatically by the main pipelines. When data is missing, each pipeline automatically generates synthetic data using `api_client.py generate-data`:

- **Training Pipeline**: Generates 2000 records with 30% anomalies if no training data exists
- **Test Pipeline**: Generates 1000 records with 20% anomalies if no test data exists  
- **Validation Pipeline**: Generates 500 records with 25% anomalies if no validation data exists

You can also manually generate data using:
```bash
python api_client.py generate-data --output data/training/training_data.json --count 2000 --anomaly-ratio 0.3
```

---

## Common Patterns and Features

### 1. Metadata File Handling
**All pipelines now skip `*_metadata.json` files** (fixed in training and validation pipelines):
```bash
if [[ "$filename" == *_metadata.json ]]; then
    info "Skipping metadata file: $filename"
    continue
fi
```

### 2. Common Library Usage
All pipelines source `lib_common.sh` for:
- Logging functions (`info`, `success`, `error`, `warn`, `stage`)
- Validation functions (`validate_json_file`)
- Timing functions (`get_timestamp`, `calculate_duration`)
- Status checking (`check_status`)

### 3. Error Handling
- `set -e` for immediate exit on error (with graceful handling)
- Status checking after API calls
- Continue on non-critical errors
- Comprehensive error messages

### 4. Logging
- All pipelines create timestamped log files
- Logs saved to `logs/` directory
- Both file and console output
- Color-coded output for readability

### 5. Report Generation
- All pipelines generate summary reports
- Reports saved to `reports/` subdirectories
- Markdown format for readability
- Includes statistics, metrics, and summaries

### 6. Anomaly Cleanup
- Pipelines track baseline anomaly count
- Clean up anomalies created during execution
- Prevents test data from polluting production database

---

## Pipeline Workflow

### Typical Development Workflow

```
1. Data Generation
   └─> (Automatic data generation via api_client.py)
       └─> Creates training, test, validation data

2. Training
   └─> training_pipeline.sh
       └─> Trains models on training data
       └─> Saves models to storage/models/

3. Testing
   └─> test_pipeline.sh
       └─> Evaluates models on test data
       └─> Tests correlation capabilities
       └─> Performance benchmarking

4. Validation
   └─> validation_pipeline.sh
       └─> Validates models on holdout data
       └─> Promotes validated models

5. Production Detection
   └─> detect_anomalies_pipeline.sh
       └─> Detects anomalies in production data
       └─> Correlation analysis
       └─> Alerting
```

### Master Pipeline Workflow

```
run_pipelines.sh
├─> Training (if enabled)
│   └─> training_pipeline.sh
├─> Testing (if enabled)
│   └─> test_pipeline.sh
├─> Validation (if enabled)
│   └─> validation_pipeline.sh
└─> Detection (if enabled)
    └─> detect_anomalies_pipeline.sh
```

---

## Directory Structure

```
pipelines/
├── run_pipelines.sh              # Master orchestrator
├── training_pipeline.sh          # Training workflow
├── test_pipeline.sh               # Testing workflow
├── validation_pipeline.sh       # Validation workflow
├── detect_anomalies_pipeline.sh # Production detection
├── PIPELINE_README.md           # User guide
├── PIPELINE_DETAILS.md          # Technical details
├── PIPELINE_MASTER.md           # Master pipeline docs
└── pipeline_architecture.svg   # Architecture diagram
```

---

## Key Fixes and Improvements

### 1. Metadata File Skipping
- **Issue**: Pipelines tried to process metadata files as data
- **Fix**: Added check to skip `*_metadata.json` files
- **Files**: `training_pipeline.sh`, `validation_pipeline.sh`, `test_pipeline.sh`

### 2. Model Directory Path
- **Issue**: Models saved to wrong directory
- **Fix**: Changed from `storage/models/training/` to `storage/models/`
- **File**: `training_pipeline.sh`

### 3. Model Status Detection
- **Issue**: Models with "not_trained" status not recognized
- **Fix**: Improved model detection logic
- **Files**: `test_pipeline.sh`, `detect_anomalies_pipeline.sh`

### 4. Data Validation
- **Issue**: Validation pipeline failed on metadata files
- **Fix**: Skip metadata files during validation
- **File**: `validation_pipeline.sh`

---

## Best Practices

### 1. Pipeline Execution Order
Always run pipelines in this order:
1. Data generation (if needed)
2. Training
3. Testing
4. Validation
5. Detection

### 2. Configuration Management
- Use appropriate config files for each pipeline
- Keep training and validation data separate
- Use different configs for different environments

### 3. Error Handling
- Check logs after each pipeline run
- Use debug pipeline to diagnose issues
- Verify model status before proceeding

### 4. Data Management
- Keep metadata files separate from data files
- Clean up test anomalies after pipelines
- Archive old reports and logs

### 5. Model Management
- Verify models are saved after training
- Check model status via API
- Promote only validated models to production

---

## Summary

The pipelines subdirectory provides a complete, production-ready ML pipeline system with:

- **5 Core Pipeline Scripts**: Covering all aspects from training to production detection
- **Automatic Data Generation**: Built into each pipeline when data is missing
- **Comprehensive Documentation**: User guides and technical details
- **Common Library Integration**: Shared functionality via `lib_common.sh`
- **Error Handling**: Robust error handling and recovery
- **Logging and Reporting**: Detailed logs and summary reports
- **Metadata Handling**: Proper handling of metadata files
- **Model Management**: Complete model lifecycle management

All pipelines are designed to work together seamlessly, with the master pipeline orchestrating the entire workflow.

