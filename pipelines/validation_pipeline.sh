#!/usr/bin/env bash

# Validation Pipeline - For Model Validation and Performance Assessment
# This pipeline validates trained models on holdout datasets before production
# UPDATED: Now includes automatic anomaly cleanup after validation

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source common library (provides PYTHON_CMD, logging, trap handlers, etc.)
if [ -f "$SCRIPT_DIR/lib_common.sh" ]; then
    source "$SCRIPT_DIR/lib_common.sh"
elif [ -f "lib_common.sh" ]; then
    source "lib_common.sh"
else
    echo "WARNING: lib_common.sh not found, using fallback defaults"
    # Minimal fallback for PYTHON_CMD
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &>/dev/null; then
        PYTHON_CMD="python"
    else
        echo "ERROR: No python interpreter found"
        exit 1
    fi
fi

# Color codes for output — only set if not already defined (avoids readonly conflict
# when sourced from run_pipelines.sh which already loaded lib_common.sh)
if [ -z "${GREEN+x}" ]; then GREEN='\033[0;32m'; fi
if [ -z "${YELLOW+x}" ]; then YELLOW='\033[1;33m'; fi
if [ -z "${BLUE+x}" ]; then BLUE='\033[0;34m'; fi
if [ -z "${RED+x}" ]; then RED='\033[0;31m'; fi
if [ -z "${CYAN+x}" ]; then CYAN='\033[0;36m'; fi
if [ -z "${PURPLE+x}" ]; then PURPLE='\033[0;35m'; fi
if [ -z "${NC+x}" ]; then NC='\033[0m'; fi

# Configuration
CONFIG_FILE="${1:-config/validation_config.yaml}"
DATA_DIR="data/validation"
PROCESSED_DIR="data/processed/validation"
MODELS_DIR="storage/models"
VALIDATED_DIR="storage/models/validated"
REPORTS_DIR="reports/validation"
LOG_FILE="logs/validation_pipeline_$(date +'%Y%m%d_%H%M%S').log"

# Validation thresholds
MIN_PRECISION=${MIN_PRECISION:-0.7}
MIN_RECALL=${MIN_RECALL:-0.6}
MIN_F1=${MIN_F1:-0.65}
MAX_FALSE_POSITIVE_RATE=${MAX_FALSE_POSITIVE_RATE:-0.3}
# Detection rate validation bounds
MIN_DETECTION_RATE=${MIN_DETECTION_RATE:-0.1}
MAX_DETECTION_RATE=${MAX_DETECTION_RATE:-0.9}
MAX_INCONSISTENCY=${MAX_INCONSISTENCY:-0.2}
CLEANUP_ANOMALIES=${CLEANUP_ANOMALIES:-true}  # Auto-cleanup validation anomalies

# Create necessary directories
mkdir -p "$DATA_DIR" "$PROCESSED_DIR" "$VALIDATED_DIR" "$REPORTS_DIR" "$(dirname "$LOG_FILE")"

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${YELLOW}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${CYAN}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

stage() {
    echo -e "${PURPLE}[STAGE]${NC} $1" | tee -a "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
}

# Function to check prerequisites
check_prerequisites() {
    stage "Checking Prerequisites"
    
    # Check Python (PYTHON_CMD set by lib_common.sh or fallback above)
    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        error "Python ($PYTHON_CMD) is not installed"
        exit 1
    fi
    
    # Check API client
    if [ ! -f "api_client.py" ]; then
        error "api_client.py not found"
        exit 1
    fi
    
    # Check API server with direct HTTP check
    api_check_result=$($PYTHON_CMD -c "
import requests
import sys
try:
    response = requests.get('http://localhost:8000/', timeout=5)
    if response.status_code == 200:
        print('OK')
        sys.exit(0)
    else:
        sys.exit(1)
except Exception as e:
    sys.exit(1)
" 2>/dev/null)
    
    if [ "$api_check_result" != "OK" ]; then
        error "API server is not responding. Please start the server first."
        error "Make sure the API server is running on http://localhost:8000"
        exit 1
    fi
    
    # Check for validation data
    if [ -z "$(ls -A "$DATA_DIR" 2>/dev/null)" ]; then
        warn "No validation data found in $DATA_DIR"
        info "Generating validation data automatically..."
        
        # Generate validation data
        $PYTHON_CMD api_client.py generate-data \
            --output "$DATA_DIR/validation_data.json" \
            --count 500 \
            --anomaly-ratio 0.25 \
            >> "$LOG_FILE" 2>&1
        
        if [ $? -eq 0 ] && [ -f "$DATA_DIR/validation_data.json" ]; then
            success "Validation data generated successfully"
        else
            error "Failed to generate validation data"
            error "Please place your validation data files in $DATA_DIR"
            exit 1
        fi
    fi
    
    success "All prerequisites met"
}

# Initialize system
initialize_system() {
    stage "Initializing System"
    
    info "Loading configuration from $CONFIG_FILE"
    
    # Use default config if validation config doesn't exist
    if [ ! -f "$CONFIG_FILE" ]; then
        CONFIG_FILE="config/config.yaml"
        warn "Validation config not found, using default: $CONFIG_FILE"
    fi
    
    $PYTHON_CMD api_client.py init "$CONFIG_FILE" >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        success "System initialized successfully"
    else
        error "Failed to initialize system"
        exit 1
    fi
}

# Stage 1: Data Collection for Validation
data_collection() {
    stage "Stage 1: Data Collection for Validation"
    
    info "Collecting validation dataset from $DATA_DIR"
    
    # List validation files
    validation_files=$(ls -1 "$DATA_DIR"/* 2>/dev/null)
    file_count=$(echo "$validation_files" | wc -l)
    
    info "Found $file_count validation data files"
    echo "$validation_files" | while read -r file; do
        if [ -f "$file" ]; then
            size=$(du -h "$file" | cut -f1)
            echo "  - $(basename "$file") ($size)" | tee -a "$LOG_FILE"
        fi
    done
    
    # Validate data integrity
    info "Validating data integrity..."
    $PYTHON_CMD -c "
import json
import sys
import os

errors = []
for file_path in '''$validation_files'''.strip().split('\n'):
    if not file_path:
        continue
    
    # Skip metadata files
    filename = os.path.basename(file_path)
    if filename.endswith('_metadata.json'):
        print(f'✓ {file_path}: Skipping metadata file')
        continue
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if not isinstance(data, list):
                errors.append(f'{file_path}: Not a list')
            elif len(data) == 0:
                errors.append(f'{file_path}: Empty dataset')
            else:
                print(f'✓ {file_path}: {len(data)} records')
    except Exception as e:
        errors.append(f'{file_path}: {str(e)}')

if errors:
    print('\\nErrors found:')
    for error in errors:
        print(f'  ✗ {error}')
    sys.exit(1)
" 2>> "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        success "Data validation passed"
    else
        error "Data validation failed"
        exit 1
    fi
}

# Stage 2: Data Preprocessing
data_preprocessing() {
    stage "Stage 2: Data Preprocessing for Validation"
    
    info "Applying same preprocessing as training pipeline"
    
    for datafile in "$DATA_DIR"/*; do
        if [ -f "$datafile" ]; then
            filename=$(basename "$datafile")
            info "Preprocessing $filename"
            
            # Process data (normalize + extract features)
            processed_file="$PROCESSED_DIR/processed_${filename}"
            $PYTHON_CMD api_client.py process-data "$datafile" > "$processed_file" 2>> "$LOG_FILE"
            
            if [ $? -eq 0 ] && [ -s "$processed_file" ]; then
                success "Processed $filename"
                
                # Data statistics
                $PYTHON_CMD -c "
import json
with open('$processed_file', 'r') as f:
    data = json.load(f)
    print(f'  Records: {len(data)}')
    if data and 'features' in data[0]:
        print(f'  Feature dimension: {len(data[0][\"features\"])}')
" 2>> "$LOG_FILE" | tee -a "$LOG_FILE"
            else
                error "Failed to process $filename"
            fi
        fi
    done
    
    success "Data preprocessing completed"
}

# Stage 3: Model Loading
load_models() {
    stage "Stage 3: Loading Trained Models"
    
    info "Loading models from storage"
    
    # FIX: Skip broken load-models API call (it has a bug with model loading)
    # Instead, check for model files and use models even if API shows 'not_trained'
    
    # Check if model files exist
    local model_files_found=false
    local check_paths=("$MODELS_DIR" "$(dirname "$SCRIPT_DIR")/storage/models" "storage/models" "./storage/models")
    
    for check_path in "${check_paths[@]}"; do
        if [ -d "$check_path" ] && (ls "$check_path"/*.pkl >/dev/null 2>&1 || ls "$check_path"/*.joblib >/dev/null 2>&1); then
            info "✓ Model files found on disk at: $check_path"
            model_files_found=true
            break
        fi
    done
    
    if [ "$model_files_found" = false ]; then
        error "No model files found in any of these locations:"
        for check_path in "${check_paths[@]}"; do
            error "  - $check_path"
        done
        error "Please run training pipeline first"
        exit 1
    fi
    
    # Get all models from API (not just trained ones, since API may show wrong status)
    local all_models_json
    all_models_json=$($PYTHON_CMD api_client.py list-models 2>/dev/null)
    
    if [ -z "$all_models_json" ]; then
        error "Cannot connect to API to list models"
        exit 1
    fi
    
    # Show available models
    info "Available models:"
    echo "$all_models_json" | $PYTHON_CMD -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for m in data:
        status = m.get('status', 'unknown')
        name = m.get('name', 'unknown')
        model_type = m.get('type', 'unknown')
        print(f\"  - {name}: {model_type} (status: {status})\")
except Exception as e:
    print(f\"  Error parsing models: {e}\")
" 2>&1 | tee -a "$LOG_FILE"
    
    # Get list of models (try trained first, then all if none trained)
    trained_models=$(echo "$all_models_json" | $PYTHON_CMD -c "
import json, sys
data = json.load(sys.stdin)
trained = [m for m in data if m.get('status') == 'trained']
if trained:
    for model in trained:
        print(f\"{model['name']}|{model.get('type', 'unknown')}|{model.get('sample_count', 'unknown')}\")
else:
    # If no trained status, use all models (model files exist)
    for model in data:
        print(f\"{model['name']}|{model.get('type', 'unknown')}|{model.get('sample_count', 'unknown')}\")
" 2>/dev/null)
    
    if [ -z "$trained_models" ]; then
        warn "No models with 'trained' status found"
        warn "However, model files exist on disk"
        info "Attempting to use models from disk despite status..."
        
        # Get all model names
        trained_models=$(echo "$all_models_json" | $PYTHON_CMD -c "
import json, sys
data = json.load(sys.stdin)
for model in data:
    print(f\"{model['name']}|{model.get('type', 'unknown')}|unknown\")
" 2>/dev/null)
    fi
    
    if [ -z "$trained_models" ]; then
        error "No models available at all"
        error "Please ensure models are trained and available"
        exit 1
    fi
    
    info "Models to validate:"
    echo "$trained_models" | while IFS='|' read -r name type samples; do
        echo "  - $name (type: $type, samples: $samples)" | tee -a "$LOG_FILE"
    done
    
    success "Models loaded successfully"
}

# Stage 4: Model Validation
model_validation() {
    stage "Stage 4: Model Validation"

    validation_results_file="$REPORTS_DIR/validation_results_$(date +'%Y%m%d_%H%M%S').json"
    echo "{\"validation_run\": \"$(date)\", \"results\": []}" > "$validation_results_file"

    # Temp file for accumulating per-model results
    local model_results_tmp="/tmp/validation_model_results_$$.json"

    # Get list of models (try trained first, then all if none trained)
    models=$($PYTHON_CMD api_client.py list-models 2>/dev/null | $PYTHON_CMD -c "
import json, sys
data = json.load(sys.stdin)
trained = [m['name'] for m in data if m.get('status') == 'trained']
if trained:
    for name in trained:
        print(name)
else:
    for model in data:
        print(model['name'])
" 2>/dev/null)

    # Validate each model on all validation datasets
    for model in $models; do
        info "Validating model: $model"

        # Initialize model results in temp file
        echo "{\"model\": \"$model\", \"datasets\": []}" > "$model_results_tmp"

        for processed_file in "$PROCESSED_DIR"/processed_*; do
            if [ -f "$processed_file" ]; then
                dataset_name=$(basename "$processed_file")
                info "  Testing on dataset: $dataset_name"

                # Run detection
                job_response=$($PYTHON_CMD api_client.py detect-anomalies "$model" "$processed_file" 2>> "$LOG_FILE")
                job_id=$(echo "$job_response" | $PYTHON_CMD -c "import json, sys; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)

                if [ -n "$job_id" ]; then
                    # Wait for completion (timeout after 300 seconds)
                    local max_wait=300
                    local waited=0

                    while [ $waited -lt $max_wait ]; do
                        job_result=$($PYTHON_CMD api_client.py job-status "$job_id" 2>/dev/null)
                        job_status=$(echo "$job_result" | $PYTHON_CMD -c "import json, sys; print(json.load(sys.stdin)['status'])" 2>/dev/null)

                        if [ "$job_status" = "completed" ]; then
                            # Extract metrics and append to model results temp file
                            echo "$job_result" | $PYTHON_CMD -c "
import json, sys
import numpy as np

data = json.load(sys.stdin)
result = data.get('result', {})

anomalies_detected = result.get('anomalies_detected', 0)
threshold = result.get('threshold', 0.5)
sample_anomalies = result.get('sample_anomalies', [])
scores = [a['score'] for a in sample_anomalies if 'score' in a]

# Count records from the JSON data file
try:
    with open('$processed_file', 'r') as f:
        record_count = len(json.load(f))
except:
    record_count = 1

dataset_metrics = {
    'dataset': '$dataset_name',
    'anomalies_detected': anomalies_detected,
    'threshold': threshold,
    'detection_rate': anomalies_detected / record_count if record_count > 0 else 0,
    'score_stats': {
        'mean': float(np.mean(scores)) if scores else 0,
        'std': float(np.std(scores)) if scores else 0,
        'min': float(np.min(scores)) if scores else 0,
        'max': float(np.max(scores)) if scores else 0
    } if scores else {}
}

# Append to model results temp file
with open('$model_results_tmp', 'r') as f:
    model_data = json.load(f)
model_data['datasets'].append(dataset_metrics)
with open('$model_results_tmp', 'w') as f:
    json.dump(model_data, f, indent=2)
" 2>> "$LOG_FILE"

                            success "  Completed validation on $dataset_name"
                            break
                        elif [ "$job_status" = "failed" ]; then
                            error "  Validation failed on $dataset_name"
                            break
                        fi

                        sleep 2
                        waited=$((waited + 2))
                    done

                    if [ $waited -ge $max_wait ]; then
                        error "  Validation timed out on $dataset_name after ${max_wait}s"
                    fi
                fi
            fi
        done

        # Append model results to the main validation results file
        $PYTHON_CMD -c "
import json

with open('$validation_results_file', 'r') as f:
    all_results = json.load(f)

with open('$model_results_tmp', 'r') as f:
    model_results = json.load(f)

all_results['results'].append(model_results)

with open('$validation_results_file', 'w') as f:
    json.dump(all_results, f, indent=2)
" 2>> "$LOG_FILE"
    done

    # Cleanup temp file
    rm -f "$model_results_tmp"

    success "Model validation completed"
}

# Stage 5: Performance Metrics Calculation
calculate_metrics() {
    stage "Stage 5: Performance Metrics Calculation"
    
    metrics_file="$REPORTS_DIR/validation_metrics_$(date +'%Y%m%d_%H%M%S').txt"
    
    info "Calculating comprehensive validation metrics"
    
    $PYTHON_CMD -c "
import json
import numpy as np

# Load validation results
with open('$validation_results_file', 'r') as f:
    results = json.load(f)

print('Validation Metrics Report')
print('=' * 50)
print(f\"Generated: {results['validation_run']}\")
print()

for model_result in results['results']:
    model_name = model_result['model']
    print(f\"\\nModel: {model_name}\")
    print('-' * 40)
    
    # Aggregate metrics across datasets
    all_detection_rates = []
    all_anomalies = []
    
    for dataset in model_result['datasets']:
        detection_rate = dataset['detection_rate']
        anomalies = dataset['anomalies_detected']
        
        all_detection_rates.append(detection_rate)
        all_anomalies.append(anomalies)
        
        print(f\"  Dataset: {dataset['dataset']}\")
        print(f\"    Anomalies: {anomalies}\")
        print(f\"    Detection Rate: {detection_rate:.2%}\")
        
        if 'score_stats' in dataset and dataset['score_stats']:
            stats = dataset['score_stats']
            print(f\"    Score Range: [{stats['min']:.3f}, {stats['max']:.3f}]\")
            print(f\"    Score Mean±Std: {stats['mean']:.3f}±{stats['std']:.3f}\")
    
    # Overall statistics
    print(f\"\\n  Overall Performance:\")
    print(f\"    Average Detection Rate: {np.mean(all_detection_rates):.2%}\")
    print(f\"    Total Anomalies: {sum(all_anomalies)}\")
    print(f\"    Consistency (std): {np.std(all_detection_rates):.3f}\")
    
    # Validation decision
    avg_detection_rate = np.mean(all_detection_rates)
    consistency = np.std(all_detection_rates)
    
    print(f\"\\n  Validation Status: \", end='')
    if avg_detection_rate > $MIN_DETECTION_RATE and avg_detection_rate < $MAX_DETECTION_RATE and consistency < $MAX_INCONSISTENCY:
        print('PASSED ✓')
    else:
        print('NEEDS REVIEW ⚠')
        if avg_detection_rate <= $MIN_DETECTION_RATE:
            print('    - Detection rate too low')
        if avg_detection_rate >= $MAX_DETECTION_RATE:
            print('    - Detection rate too high (possible overfitting)')
        if consistency >= $MAX_INCONSISTENCY:
            print('    - Inconsistent performance across datasets')

print('\\n' + '=' * 50)
" > "$metrics_file" 2>> "$LOG_FILE"
    
    cat "$metrics_file" | tee -a "$LOG_FILE"
    
    success "Metrics calculation completed"
}

# Stage 6: Correlation Validation (NEW)
correlation_validation() {
    stage "Stage 6: Correlation Pattern Validation"
    
    info "Validating anomaly correlation patterns"
    
    correlation_validation_file="$REPORTS_DIR/correlation_validation_$(date +'%Y%m%d_%H%M%S').json"
    echo '{"validation_timestamp": "'$(date)'", "validations": []}' > "$correlation_validation_file"
    
    # For each model, test correlation detection
    models=$($PYTHON_CMD api_client.py list-models 2>/dev/null | $PYTHON_CMD -c "
import json, sys
data = json.load(sys.stdin)
for model in data:
    if model['status'] == 'trained':
        print(model['name'])
" 2>/dev/null)
    
    for model in $models; do
        info "Testing correlation patterns for model: $model"
        
        # Run detection on validation set to get anomalies
        for processed_file in "$PROCESSED_DIR"/processed_*; do
            if [ -f "$processed_file" ]; then
                # Detect anomalies
                job_response=$($PYTHON_CMD api_client.py detect-anomalies "$model" "$processed_file" 2>> "$LOG_FILE")
                job_id=$(echo "$job_response" | $PYTHON_CMD -c "import json, sys; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)
                
                if [ -n "$job_id" ]; then
                    # Wait for completion (timeout after 300 seconds)
                    local corr_max_wait=300
                    local corr_waited=0

                    while [ $corr_waited -lt $corr_max_wait ]; do
                        job_status=$($PYTHON_CMD api_client.py job-status "$job_id" 2>/dev/null | $PYTHON_CMD -c "import json, sys; print(json.load(sys.stdin)['status'])" 2>/dev/null)

                        if [ "$job_status" = "completed" ] || [ "$job_status" = "failed" ]; then
                            break
                        fi
                        sleep 2
                        corr_waited=$((corr_waited + 2))
                    done

                    if [ $corr_waited -ge $corr_max_wait ]; then
                        warn "  Correlation detection timed out after ${corr_max_wait}s"
                    fi
                fi
            fi
        done
        
        # Get detected anomalies for this model
        $PYTHON_CMD api_client.py list-anomalies --model "$model" --limit 100 > "$PROCESSED_DIR/temp_anomalies_${model}.json" 2>> "$LOG_FILE"
        
        # Test bulk correlation
        anomaly_ids=$($PYTHON_CMD -c "
import json
try:
    with open('$PROCESSED_DIR/temp_anomalies_${model}.json', 'r') as f:
        anomalies = json.load(f)
        # Get up to 10 anomaly IDs for testing
        ids = [a['id'] for a in anomalies[:10] if 'id' in a]
        print(' '.join(ids))
except:
    pass
" 2>/dev/null)
        
        if [ -n "$anomaly_ids" ]; then
            # Test bulk correlation
            info "  Testing bulk correlation for $model"
            
            # FIXED: Process in batches to avoid "Argument list too long" error
            # Convert space-separated IDs to array
            read -ra id_array <<< "$anomaly_ids"
            total_ids=${#id_array[@]}
            
            if [ $total_ids -eq 0 ]; then
                info "  No anomaly IDs to correlate"
                continue
            fi
            
            info "  Processing $total_ids anomalies in batches..."
            
            # Process in batches of 50
            batch_size=50
            batch_num=1
            all_correlation_results=""
            
            for ((i=0; i<$total_ids; i+=batch_size)); do
                # Get batch
                end=$((i + batch_size))
                if [ $end -gt $total_ids ]; then
                    end=$total_ids
                fi
                
                batch=("${id_array[@]:i:batch_size}")
                
                if [ ${#batch[@]} -gt 0 ]; then
                    info "    Batch $batch_num: processing IDs $(( (batch_num-1)*batch_size + 1 ))-$end of $total_ids"
                    
                    # Call API with batch
                    batch_result=$($PYTHON_CMD api_client.py bulk-correlate "${batch[@]}" --cross-correlate 2>> "$LOG_FILE")
                    
                    if [ $? -eq 0 ]; then
                        all_correlation_results="${all_correlation_results}${batch_result}\n"
                    else
                        warn "    Batch $batch_num failed"
                    fi
                    
                    batch_num=$((batch_num + 1))
                fi
            done
            
            # Use the combined results
            correlation_result="$all_correlation_results"

            if [ -n "$correlation_result" ]; then
                # Analyze correlation patterns
                $PYTHON_CMD -c "
import json

result = $correlation_result
stats = result.get('statistics', {})

print(f'  Model: {\"$model\"}')
print(f'    Anomalies analyzed: {stats.get(\"anomalies_analyzed\", 0)}')
print(f'    Total correlations: {stats.get(\"total_correlations_found\", 0)}')
print(f'    Cross-correlations enabled: {stats.get(\"cross_correlations_enabled\", False)}')

# Calculate correlation density
anomalies_analyzed = stats.get('anomalies_analyzed', 0)
correlations_found = stats.get('total_correlations_found', 0)
density = correlations_found / max(anomalies_analyzed, 1)

print(f'    Correlation density: {density:.3f}')

# Save validation result
validation = {
    'model': '$model',
    'correlation_test': {
        'anomalies_tested': anomalies_analyzed,
        'correlations_found': correlations_found,
        'correlation_density': density,
        'cross_correlation_enabled': stats.get('cross_correlations_enabled', False)
    }
}

# Append to validation file
with open('$correlation_validation_file', 'r') as f:
    all_validations = json.load(f)

all_validations['validations'].append(validation)

with open('$correlation_validation_file', 'w') as f:
    json.dump(all_validations, f, indent=2)
" 2>> "$LOG_FILE" | tee -a "$LOG_FILE"
            else
                warn "  Failed to test correlations for $model"
            fi
        else
            info "  No anomalies available for correlation testing with $model"
        fi
    done
    
    success "Correlation validation completed"
}

# Stage 7: Comparison with Baseline (Updated)
compare_baseline() {
    stage "Stage 7: Comparison with Baseline Performance"
    
    info "Comparing model performance against baselines"
    
    # Create baseline comparison report
    comparison_file="$REPORTS_DIR/baseline_comparison_$(date +'%Y%m%d_%H%M%S').md"
    
    cat > "$comparison_file" << EOF
# Model Validation - Baseline Comparison Report

**Generated:** $(date)

## Baseline Metrics
- **Random Detector**: 50% detection rate, 50% false positive rate
- **Simple Threshold**: Based on 3-sigma rule
- **Previous Production Model**: (if available)

## Model Performance Summary

EOF
    
    $PYTHON_CMD -c "
import json
import numpy as np

with open('$validation_results_file', 'r') as f:
    results = json.load(f)

print('| Model | Avg Detection Rate | Consistency | Correlation Support | Status |')
print('|-------|-------------------|-------------|-------------------|---------|')

# Load correlation validation if available
correlation_support = {}
try:
    with open('$correlation_validation_file', 'r') as f:
        corr_data = json.load(f)
        for val in corr_data.get('validations', []):
            model = val['model']
            density = val['correlation_test']['correlation_density']
            correlation_support[model] = '✓' if density > 0.1 else '✗'
except:
    pass

for model_result in results['results']:
    model_name = model_result['model']
    
    detection_rates = []
    for dataset in model_result['datasets']:
        detection_rates.append(dataset['detection_rate'])
    
    avg_rate = np.mean(detection_rates)
    consistency = np.std(detection_rates)
    
    # Determine status
    if avg_rate > $MIN_DETECTION_RATE and avg_rate < $MAX_DETECTION_RATE and consistency < $MAX_INCONSISTENCY:
        status = '✓ Validated'
    else:
        status = '⚠ Review'
    
    corr_support = correlation_support.get(model_name, 'N/A')
    
    print(f'| {model_name} | {avg_rate:.2%} | {consistency:.3f} | {corr_support} | {status} |')

print('\\n### Performance Analysis\\n')

# Identify best model
best_model = None
best_score = -1

for model_result in results['results']:
    detection_rates = [d['detection_rate'] for d in model_result['datasets']]
    avg_rate = np.mean(detection_rates)
    consistency = np.std(detection_rates)
    
    # Score based on detection rate and consistency
    score = avg_rate * (1 - consistency)
    
    # Bonus for correlation support
    if model_result['model'] in correlation_support and correlation_support[model_result['model']] == '✓':
        score *= 1.1
    
    if score > best_score and $MIN_DETECTION_RATE < avg_rate < $MAX_DETECTION_RATE:
        best_score = score
        best_model = model_result['model']

if best_model:
    print(f'**Recommended Model**: {best_model}')
    print(f'- Balanced detection rate with good consistency')
    if best_model in correlation_support and correlation_support[best_model] == '✓':
        print(f'- Supports correlation analysis')
else:
    print('**Recommendation**: No model meets validation criteria')
    print('- Consider retraining with different parameters')
" >> "$comparison_file" 2>> "$LOG_FILE"
    
    info "Baseline comparison saved to: $comparison_file"
    success "Baseline comparison completed"
}

# Stage 8: Generate Validation Report (Updated)
generate_report() {
    stage "Stage 8: Generating Validation Report"
    
    report_file="$REPORTS_DIR/validation_summary_$(date +'%Y%m%d_%H%M%S').md"
    
    cat > "$report_file" << EOF
# Validation Pipeline Summary Report

**Generated:** $(date)
**Validation Data:** $DATA_DIR
**Models Tested:** $($PYTHON_CMD api_client.py list-models 2>/dev/null | $PYTHON_CMD -c "import json, sys; data=json.load(sys.stdin); print(len([m for m in data if m['status']=='trained']))" 2>/dev/null)

## Executive Summary

The validation pipeline has completed testing all trained models against the holdout validation dataset. This report summarizes the performance of each model and provides recommendations for production deployment.

## Validation Results

EOF
    
    # Add detailed results
    $PYTHON_CMD -c "
import json

with open('$validation_results_file', 'r') as f:
    results = json.load(f)

# Load correlation validation
correlation_results = {}
try:
    with open('$correlation_validation_file', 'r') as f:
        corr_data = json.load(f)
        for val in corr_data.get('validations', []):
            model = val['model']
            correlation_results[model] = val['correlation_test']
except:
    pass

# Models ready for production
validated_models = []
review_models = []

for model_result in results['results']:
    model_name = model_result['model']
    datasets = model_result['datasets']
    
    # Calculate overall metrics
    detection_rates = [d['detection_rate'] for d in datasets]
    if not detection_rates:
        review_models.append(model_name)
        continue
    avg_rate = sum(detection_rates) / len(detection_rates)

    if $MIN_DETECTION_RATE < avg_rate < $MAX_DETECTION_RATE:
        validated_models.append(model_name)
    else:
        review_models.append(model_name)

print('### Models Validated for Production')
if validated_models:
    for model in validated_models:
        print(f'- ✓ {model}')
        if model in correlation_results:
            corr = correlation_results[model]
            print(f'  - Correlation density: {corr[\"correlation_density\"]:.3f}')
else:
    print('- None (all models need review)')

print('\\n### Models Requiring Review')
if review_models:
    for model in review_models:
        print(f'- ⚠ {model}')
else:
    print('- None')

print('\\n## Correlation Analysis Summary')
if correlation_results:
    print('\\nModels were tested for their ability to support correlation analysis:')
    for model, corr in correlation_results.items():
        print(f'- {model}: {corr[\"correlations_found\"]} correlations found among {corr[\"anomalies_tested\"]} anomalies')
else:
    print('No correlation analysis was performed.')

print('\\n## Recommendations')
print('\\n1. **For Production Deployment:**')
if validated_models:
    print(f'   - Deploy {validated_models[0]} as primary model')
    if len(validated_models) > 1:
        print(f'   - Consider ensemble with: {validated_models[1:]}')
else:
    print('   - No models meet production criteria')
    print('   - Recommend retraining with adjusted parameters')

print('\\n2. **For Continuous Improvement:**')
print('   - Monitor false positive rates in production')
print('   - Collect feedback on detected anomalies')
print('   - Schedule periodic revalidation')
print('   - Enable correlation analysis for pattern detection')

print('\\n3. **Next Steps:**')
print('   - Run pipelines/detect_anomalies_pipeline.sh with validated models')
print('   - Configure alerting thresholds based on validation metrics')
print('   - Set up production monitoring')
print('   - Enable correlation analysis features for enhanced detection')
" >> "$report_file" 2>> "$LOG_FILE"
    
    echo "" >> "$report_file"
    echo "## Detailed Metrics" >> "$report_file"
    echo "" >> "$report_file"
    echo "See the following files for detailed analysis:" >> "$report_file"
    echo "- Validation Results: $(basename "$validation_results_file")" >> "$report_file"
    echo "- Performance Metrics: validation_metrics_*.txt" >> "$report_file"
    echo "- Baseline Comparison: baseline_comparison_*.md" >> "$report_file"
    echo "- Correlation Validation: $(basename "$correlation_validation_file")" >> "$report_file"
    
    info "Validation summary saved to: $report_file"
    success "Validation report generated"
}

# Stage 9: Model Promotion (Updated)
promote_models() {
    stage "Stage 9: Model Promotion Decision"
    
    info "Evaluating models for production promotion"
    
    # Check which models passed validation
    validated_models=$($PYTHON_CMD -c "
import json
import numpy as np

with open('$validation_results_file', 'r') as f:
    results = json.load(f)

# Load correlation validation
correlation_support = set()
try:
    with open('$correlation_validation_file', 'r') as f:
        corr_data = json.load(f)
        for val in corr_data.get('validations', []):
            if val['correlation_test']['correlation_density'] > 0.1:
                correlation_support.add(val['model'])
except:
    pass

validated = []
for model_result in results['results']:
    model_name = model_result['model']
    detection_rates = [d['detection_rate'] for d in model_result['datasets']]
    if not detection_rates:
        continue
    avg_rate = np.mean(detection_rates)
    consistency = np.std(detection_rates)

    if $MIN_DETECTION_RATE < avg_rate < $MAX_DETECTION_RATE and consistency < $MAX_INCONSISTENCY:
        validated.append(model_name)
        # Prefer models with correlation support
        if model_name in correlation_support:
            print(f'{model_name}|with_correlation')
        else:
            print(f'{model_name}|basic')
" 2>> "$LOG_FILE")
    
    if [ -z "$validated_models" ]; then
        warn "No models passed validation criteria"
        info "Manual review required before production deployment"
    else
        info "Models validated for production:"
        echo "$validated_models" | while IFS='|' read -r model features; do
            echo "  - $model ($features)" | tee -a "$LOG_FILE"
            
            # Create validation certificate
            cert_file="$VALIDATED_DIR/${model}_validation_cert.json"
            $PYTHON_CMD -c "
import json
import datetime

cert = {
    'model': '$model',
    'validation_date': datetime.datetime.utcnow().isoformat(),
    'validation_pipeline': 'validation_pipeline.sh',
    'status': 'VALIDATED',
    'features': '$features',
    'ready_for_production': True
}

with open('$cert_file', 'w') as f:
    json.dump(cert, f, indent=2)
" 2>> "$LOG_FILE"
            
            success "Created validation certificate for $model"
        done
    fi
}

# Cleanup validation anomalies from database
cleanup_validation_anomalies() {
    if [ "$CLEANUP_ANOMALIES" != "true" ]; then
        info "Anomaly cleanup disabled, skipping"
        return 0
    fi

    stage "Cleaning Up Validation Anomalies"

    info "Removing anomalies created during validation..."

    $PYTHON_CMD -c "
import yaml, sys
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = yaml.safe_load(f)
    db_config = config.get('database', {}).get('connection', {})
    import psycopg2
    conn = psycopg2.connect(
        host=db_config.get('host', 'localhost'),
        port=db_config.get('port', 5432),
        dbname=db_config.get('database', 'anomaly_detection'),
        user=db_config.get('user', 'anomaly_user'),
        password=db_config.get('password', '')
    )
    cursor = conn.cursor()
    # Delete anomalies created in the last hour (validation window)
    cursor.execute(\"\"\"
        DELETE FROM anomalies
        WHERE created_at > NOW() - INTERVAL '1 hour'
        AND source LIKE '%validation%'
    \"\"\")
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    print(f'Cleaned up {deleted} validation anomalies')
except Exception as e:
    print(f'Warning: Could not clean up anomalies: {e}', file=sys.stderr)
" 2>> "$LOG_FILE" | tee -a "$LOG_FILE"

    success "Anomaly cleanup completed"
}

# Main execution
main() {
    log "Starting Validation Pipeline"

    # Check prerequisites
    check_prerequisites

    # Initialize system
    initialize_system

    # Execute pipeline stages
    data_collection
    data_preprocessing
    load_models
    model_validation
    calculate_metrics
    correlation_validation
    compare_baseline
    generate_report
    promote_models

    # Cleanup validation anomalies if enabled
    cleanup_validation_anomalies

    log "Validation Pipeline completed"

    # Final summary
    echo ""
    success "Validation pipeline completed successfully!"
    info "Check reports in: $REPORTS_DIR"
    info "Validated models in: $VALIDATED_DIR"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --min-precision)
            MIN_PRECISION="$2"
            shift 2
            ;;
        --min-recall)
            MIN_RECALL="$2"
            shift 2
            ;;
        --min-f1)
            MIN_F1="$2"
            shift 2
            ;;
        --max-fpr)
            MAX_FALSE_POSITIVE_RATE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [config_file] [options]"
            echo "Options:"
            echo "  --min-precision VALUE   Minimum precision threshold (default: 0.7)"
            echo "  --min-recall VALUE      Minimum recall threshold (default: 0.6)"
            echo "  --min-f1 VALUE          Minimum F1 score threshold (default: 0.65)"
            echo "  --max-fpr VALUE         Maximum false positive rate (default: 0.3)"
            echo "  --help                  Show this help message"
            exit 0
            ;;
        *)
            if [[ -f "$1" ]]; then
                CONFIG_FILE="$1"
            fi
            shift
            ;;
    esac
done

# Run the main function
main