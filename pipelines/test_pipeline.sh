#!/usr/bin/env bash
################################################################################
# Test Pipeline - Model Testing and Evaluation
# FIXED VERSION - Skips metadata files and improved model detection
################################################################################

# Use set -e but allow functions to handle errors gracefully
set -e
# However, we'll use || true for critical sections that should continue on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source common library
if [ -f "$SCRIPT_DIR/lib_common.sh" ]; then
    source "$SCRIPT_DIR/lib_common.sh"
elif [ -f "lib_common.sh" ]; then
    source "lib_common.sh"
else
    echo "ERROR: lib_common.sh not found"
    exit 1
fi

################################################################################
# Configuration
################################################################################

CONFIG_FILE="${1:-config/config.yaml}"
TEST_DATA_DIR="data/test"
PROCESSED_DIR="data/processed/test"
MODELS_DIR="storage/models"
REPORTS_DIR="reports/test"
LOG_FILE="logs/test_pipeline_$(date +'%Y%m%d_%H%M%S').log"

# Pipeline control flags
SKIP_DATA_PREP=${SKIP_DATA_PREP:-false}
SKIP_EVALUATION=${SKIP_EVALUATION:-false}
SKIP_CORRELATION=${SKIP_CORRELATION:-false}
SKIP_PERFORMANCE=${SKIP_PERFORMANCE:-false}
CLEANUP_ANOMALIES=${CLEANUP_ANOMALIES:-true}

# Baseline tracking
BASELINE_FILE="/tmp/anomaly_baseline_test_$$"

################################################################################
# Pipeline Stages
################################################################################

# Stage 1: Test Data Preparation
test_data_preparation() {
    stage "Stage 1: Test Data Preparation"
    
    if [ "$SKIP_DATA_PREP" = true ]; then
        info "Skipping test data preparation"
        return 0
    fi
    
    # Check for existing test data
    if [ ! -d "$TEST_DATA_DIR" ] || [ -z "$(ls -A "$TEST_DATA_DIR" 2>/dev/null)" ]; then
        info "Generating test data..."
        
        python api_client.py generate-data \
            --output "$TEST_DATA_DIR/test_data.json" \
            --count 1000 \
            --anomaly-ratio 0.2 \
            >>"$LOG_FILE" 2>&1
        
        check_status "Failed to generate test data" || return 1
    fi
    
    # List test files
    local file_count
    file_count=$(ls -1 "$TEST_DATA_DIR"/* 2>/dev/null | wc -l)
    info "Found $file_count test data files"
    
    # Preprocess test data
    for datafile in "$TEST_DATA_DIR"/*; do
        if [ -f "$datafile" ]; then
            local filename
            filename=$(basename "$datafile")
            
            # FIX #1: Skip metadata files
            if [[ "$filename" == *_metadata.json ]]; then
                info "Skipping metadata file: $filename"
                continue
            fi
            
            local processed_file="$PROCESSED_DIR/processed_${filename}"
            
            info "Processing $filename"
            
            if ! validate_json_file "$datafile"; then
                error "Invalid test file: $filename"
                continue
            fi
            
            python api_client.py process-data "$datafile" > "$processed_file" 2>>"$LOG_FILE"
            
            if [ $? -eq 0 ] && [ -s "$processed_file" ]; then
                success "Processed $filename"
            else
                error "Failed to process $filename"
            fi
        fi
    done
    
    success "Test data preparation completed"
}

# Stage 2: Model Evaluation
model_evaluation() {
    stage "Stage 2: Model Evaluation"
    
    if [ "$SKIP_EVALUATION" = true ]; then
        info "Skipping model evaluation"
        return 0
    fi
    
    # FIX #2: Improved model detection with debugging
    info "Checking for trained models..."
    
    # First, check if API is responding
    if ! python api_client.py list-models >/dev/null 2>&1; then
        error "Cannot connect to API to list models"
        error "Make sure the API service is running"
        return 1
    fi
    
    # Get ALL models (not just trained)
    local all_models_json
    all_models_json=$(python api_client.py list-models 2>/dev/null)
    
    if [ -z "$all_models_json" ]; then
        error "API returned empty response for list-models"
        return 1
    fi
    
    # Debug: Show all models and their statuses
    info "Available models:"
    echo "$all_models_json" | python -c "
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
    
    # Get list of trained models
    local models
    models=$(echo "$all_models_json" | \
             python -c "import json, sys; data=json.load(sys.stdin); print('\n'.join(m['name'] for m in data if m.get('status')=='trained'))" 2>/dev/null)
    
    # FIX #3: If no trained models but models exist with files, use them anyway
    if [ -z "$models" ]; then
        warn "No models with 'trained' status found"
        
        # Check if model files exist (try multiple paths)
        local model_files_found=false
        local check_paths=("$MODELS_DIR" "$SCRIPT_DIR/../storage/models" "storage/models" "./storage/models")
        
        for check_path in "${check_paths[@]}"; do
            if [ -d "$check_path" ] && (ls "$check_path"/*.pkl >/dev/null 2>&1 || ls "$check_path"/*.joblib >/dev/null 2>&1); then
                warn "However, model files exist on disk at: $check_path"
                info "Attempting to use models from disk despite status..."
                model_files_found=true
                break
            fi
        done
        
        if [ "$model_files_found" = true ]; then
            # Get all model names (not just trained ones)
            models=$(echo "$all_models_json" | \
                     python -c "import json, sys; data=json.load(sys.stdin); print('\n'.join(m['name'] for m in data))" 2>/dev/null)
            
            if [ -z "$models" ]; then
                # Last resort: try to get model names from API system status
                warn "Could not get model names from list-models, trying system-status..."
                local system_status
                system_status=$(python api_client.py system-status 2>/dev/null)
                if [ -n "$system_status" ]; then
                    models=$(echo "$system_status" | \
                             python -c "import json, sys; data=json.load(sys.stdin); models=data.get('models',{}); print('\n'.join(models.keys()) if isinstance(models, dict) else '\n'.join(str(m) for m in models))" 2>/dev/null)
                fi
            fi
            
            if [ -z "$models" ]; then
                error "No models available at all - cannot proceed with evaluation"
                error "Please ensure models are trained and available"
                return 1
            fi
            
            info "Found models to evaluate: $(echo "$models" | tr '\n' ' ')"
        else
            # More helpful error message
            error "No trained models available for evaluation"
            error "Model files not found in any of these locations:"
            for check_path in "${check_paths[@]}"; do
                error "  - $check_path"
            done
            error "Please run training pipeline first"
            error "Current working directory: $(pwd)"
            error "MODELS_DIR variable: $MODELS_DIR"
            return 1
        fi
    else
        info "Evaluating models: $(echo "$models" | tr '\n' ' ')"
    fi
    
    # Find test data
    local test_file
    test_file=$(ls "$PROCESSED_DIR"/processed_test_*.json 2>/dev/null | head -1)
    
    if [ -z "$test_file" ] || [ ! -f "$test_file" ]; then
        # Try alternate pattern
        test_file=$(ls "$PROCESSED_DIR"/processed_*.json 2>/dev/null | grep -v metadata | head -1)
    fi
    
    if [ -z "$test_file" ] || [ ! -f "$test_file" ]; then
        error "No processed test data available"
        info "Available files in $PROCESSED_DIR:"
        ls -la "$PROCESSED_DIR" 2>&1 | tee -a "$LOG_FILE"
        return 1
    fi
    
    info "Using test data: $(basename "$test_file")"
    
    # Evaluate each model
    local eval_report="$REPORTS_DIR/evaluation_report_$(date +'%Y%m%d_%H%M%S').txt"
    echo "Model Evaluation Report" > "$eval_report"
    echo "Generated: $(date)" >> "$eval_report"
    echo "======================================" >> "$eval_report"
    
    while IFS= read -r model; do
        [ -z "$model" ] && continue
        
        info "Evaluating model: $model"
        
        # Run detection on test data
        local job_response
        job_response=$(python api_client.py detect-anomalies "$model" "$test_file" 2>>"$LOG_FILE")
        
        # Check if the response is valid JSON
        if ! echo "$job_response" | python -c "import json, sys; json.load(sys.stdin)" >/dev/null 2>&1; then
            error "Invalid response from API for model $model: $job_response"
            echo "Model: $model" >> "$eval_report"
            echo "  Status: FAILED - Invalid API response" >> "$eval_report"
            continue
        fi
        
        local job_id
        job_id=$(echo "$job_response" | python -c "import json, sys; data=json.load(sys.stdin); print(data.get('job_id', ''))" 2>/dev/null)
        
        if [ -z "$job_id" ]; then
            # Check if there's an error message
            local error_msg
            error_msg=$(echo "$job_response" | python -c "import json, sys; data=json.load(sys.stdin); print(data.get('detail', data.get('error', 'Unknown error')))" 2>/dev/null)
            error "Failed to start evaluation job for $model: $error_msg"
            echo "Model: $model" >> "$eval_report"
            echo "  Status: FAILED - $error_msg" >> "$eval_report"
            continue
        fi
        
        if [ -n "$job_id" ]; then
            # Wait for completion
            local max_wait=300  # 5 minutes max
            local waited=0
            while [ $waited -lt $max_wait ]; do
                local job_status
                job_status=$(python api_client.py job-status "$job_id" 2>/dev/null | \
                           python -c "import json, sys; print(json.load(sys.stdin)['status'])" 2>/dev/null)
                
                if [ "$job_status" = "completed" ]; then
                    echo "" >> "$eval_report"
                    echo "Model: $model" >> "$eval_report"
                    python api_client.py job-status "$job_id" 2>/dev/null | \
                        python -c "import json, sys; data=json.load(sys.stdin); result=data.get('result',{}); print(f\"  Anomalies detected: {result.get('anomalies_detected', 0)}\"); print(f\"  Detection rate: {result.get('detection_rate', 0):.2%}\")" \
                        >> "$eval_report" 2>>"$LOG_FILE"
                    success "Evaluation completed for $model"
                    break
                elif [ "$job_status" = "failed" ]; then
                    error "Evaluation failed for $model"
                    # Get error details
                    local error_details
                    error_details=$(python api_client.py job-status "$job_id" 2>/dev/null | \
                                  python -c "import json, sys; data=json.load(sys.stdin); result=data.get('result',{}); print(result.get('error', 'Unknown error'))" 2>/dev/null)
                    echo "Model: $model" >> "$eval_report"
                    echo "  Status: FAILED" >> "$eval_report"
                    echo "  Error: $error_details" >> "$eval_report"
                    break
                fi
                sleep 2
                waited=$((waited + 2))
            done
            
            if [ $waited -ge $max_wait ]; then
                warn "Evaluation timed out for $model after ${max_wait}s"
                echo "Model: $model" >> "$eval_report"
                echo "  Status: TIMEOUT" >> "$eval_report"
            fi
        fi
    done <<< "$models"
    
    info "Evaluation report saved to: $eval_report"
    success "Model evaluation completed"
}

# Stage 3: Correlation Testing
correlation_testing() {
    stage "Stage 3: Correlation Testing"
    
    if [ "$SKIP_CORRELATION" = true ]; then
        info "Skipping correlation testing"
        return 0
    fi
    
    info "Testing correlation analysis features..."
    
    # Get recent anomalies
    local anomalies
    anomalies=$(python api_client.py list-anomalies --limit 10 2>/dev/null | \
               python -c "import json, sys; data=json.load(sys.stdin); print('\n'.join(a['id'] for a in data[:5]))" 2>/dev/null)
    
    if [ -z "$anomalies" ]; then
        warn "No anomalies found for correlation testing"
        return 0
    fi
    
    local corr_report="$REPORTS_DIR/correlation_test_$(date +'%Y%m%d_%H%M%S').md"
    echo "# Correlation Analysis Test Report" > "$corr_report"
    echo "" >> "$corr_report"
    echo "**Generated:** $(date)" >> "$corr_report"
    echo "" >> "$corr_report"
    
    # Test correlation for first anomaly
    local first_anomaly
    first_anomaly=$(echo "$anomalies" | head -1)
    
    info "Testing correlation analysis for anomaly: $first_anomaly"
    
    python api_client.py correlate-anomaly "$first_anomaly" \
        --time-window 24 \
        --min-score 0.3 \
        >>"$corr_report" 2>>"$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        success "Correlation testing completed"
    else
        warn "Correlation testing encountered issues"
    fi
    
    info "Correlation report saved to: $corr_report"
}

# Stage 4: Performance Testing
performance_testing() {
    stage "Stage 4: Performance Testing"
    
    if [ "$SKIP_PERFORMANCE" = true ]; then
        info "Skipping performance testing"
        return 0
    fi
    
    info "Testing model performance on test data..."
    
    local perf_report="$REPORTS_DIR/performance_test_$(date +'%Y%m%d_%H%M%S').txt"
    echo "Performance Test Report" > "$perf_report"
    echo "Generated: $(date)" >> "$perf_report"
    echo "======================================" >> "$perf_report"
    
    # Get models
    local models
    models=$(python api_client.py list-models 2>/dev/null | \
             python -c "import json, sys; data=json.load(sys.stdin); print('\n'.join(m['name'] for m in data))")
    
    if [ -z "$models" ]; then
        warn "No models available for performance testing"
        return 0
    fi
    
    # Get test files
    local test_files
    test_files=$(ls "$PROCESSED_DIR"/processed_*.json 2>/dev/null | grep -v metadata)
    
    if [ -z "$test_files" ]; then
        error "No test data available"
        return 1
    fi
    
    # Test each model on each file
    for test_file in $test_files; do
        local test_name
        test_name=$(basename "$test_file")
        
        local record_count
        record_count=$(python -c "import json; data=json.load(open('$test_file')); print(len(data))" 2>/dev/null)
        
        echo "" >> "$perf_report"
        echo "Test Dataset: $test_name ($record_count records)" >> "$perf_report"
        echo "----------------------------" >> "$perf_report"
        
        while IFS= read -r model; do
            [ -z "$model" ] && continue
            
            info "Testing $model on $test_name"
            
            local start_time
            start_time=$(get_timestamp)
            
            local job_response
            job_response=$(python api_client.py detect-anomalies "$model" "$test_file" 2>>"$LOG_FILE")
            
            local job_id
            job_id=$(echo "$job_response" | python -c "import json, sys; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)
            
            if [ -n "$job_id" ]; then
                # Wait for completion
                while true; do
                    local job_status
                    job_status=$(python api_client.py job-status "$job_id" 2>/dev/null | \
                               python -c "import json, sys; print(json.load(sys.stdin)['status'])" 2>/dev/null)
                    
                    if [ "$job_status" = "completed" ] || [ "$job_status" = "failed" ]; then
                        local end_time
                        end_time=$(get_timestamp)
                        local duration
                        duration=$(calculate_duration "$start_time" "$end_time")
                        
                        echo "Model: $model" >> "$perf_report"
                        echo "  Processing time: $(format_duration $duration)" >> "$perf_report"
                        
                        if [ $record_count -gt 0 ]; then
                            local rps
                            rps=$(python -c "print(f'{$record_count / max($duration, 1):.2f}')")
                            echo "  Records/second: $rps" >> "$perf_report"
                        fi
                        
                        if [ "$job_status" = "completed" ]; then
                            python api_client.py job-status "$job_id" 2>/dev/null | \
                                python -c "import json, sys; data=json.load(sys.stdin); result=data.get('result',{}); print(f\"  Anomalies detected: {result.get('anomalies_detected', 0)}\"); print(f\"  Detection rate: {result.get('anomalies_detected', 0) / $record_count * 100:.2f}%\" if $record_count > 0 else \"  Detection rate: N/A\")" \
                                >> "$perf_report" 2>>"$LOG_FILE"
                        else
                            echo "  Status: FAILED" >> "$perf_report"
                        fi
                        echo "" >> "$perf_report"
                        break
                    fi
                    sleep 1
                done
            fi
        done <<< "$models"
    done
    
    info "Performance report saved to: $perf_report"
    success "Performance testing completed"
}

# Stage 5: Generate Report
generate_report() {
    stage "Generating Test Report"
    
    local report_file="$REPORTS_DIR/test_summary_$(date +'%Y%m%d_%H%M%S').md"
    
    cat > "$report_file" << EOF
# Test Pipeline Summary Report

**Generated:** $(date)
**Configuration:** $CONFIG_FILE

## Test Configuration

- Test Data Directory: $TEST_DATA_DIR
- Reports Directory: $REPORTS_DIR
- Cleanup Anomalies: $CLEANUP_ANOMALIES

## Models Tested

EOF

    # List tested models
    python api_client.py list-models 2>/dev/null | python -c "
import json, sys
data = json.load(sys.stdin)
for model in data:
    status = model.get('status', 'unknown')
    model_type = model.get('type', 'unknown')
    print(f\"- **{model['name']}**: {model_type} (status: {status})\")
" >> "$report_file" 2>>"$LOG_FILE"

    echo "" >> "$report_file"
    echo "## Test Results Summary" >> "$report_file"
    echo "" >> "$report_file"
    
    # Check which stages completed
    if ls "$REPORTS_DIR"/evaluation_report_*.txt 1>/dev/null 2>&1; then
        echo "✓ Model evaluation completed" >> "$report_file"
    else
        echo "✗ Model evaluation was not performed" >> "$report_file"
    fi
    
    if ls "$REPORTS_DIR"/correlation_test_*.md 1>/dev/null 2>&1; then
        echo "✓ Correlation analysis tested" >> "$report_file"
    else
        echo "✗ Correlation analysis was not tested" >> "$report_file"
    fi
    
    if ls "$REPORTS_DIR"/performance_test_*.txt 1>/dev/null 2>&1; then
        echo "✓ Performance testing completed" >> "$report_file"
    else
        echo "✗ Performance testing was not performed" >> "$report_file"
    fi
    
    echo "" >> "$report_file"
    echo "## Next Steps" >> "$report_file"
    echo "" >> "$report_file"
    echo "1. Review evaluation metrics" >> "$report_file"
    echo "2. Analyze correlation test results" >> "$report_file"
    echo "3. Check performance metrics" >> "$report_file"
    echo "4. Run validation pipeline" >> "$report_file"
    
    if [ "$CLEANUP_ANOMALIES" = "true" ]; then
        echo "5. Test anomalies have been cleaned up" >> "$report_file"
    fi
    
    info "Report saved to: $report_file"
    success "Report generation completed"
}

################################################################################
# Main Execution
################################################################################

main() {
    log "Starting Test Pipeline"
    log "Configuration: $CONFIG_FILE"
    
    # Create directories
    create_pipeline_directories \
        "$TEST_DATA_DIR" "$PROCESSED_DIR" \
        "$REPORTS_DIR" "$(dirname "$LOG_FILE")"
    
    # Check prerequisites
    check_all_prerequisites "$CONFIG_FILE" || die "Prerequisites check failed"
    
    # Initialize system
    initialize_system "$CONFIG_FILE" || die "System initialization failed"
    
    # Record baseline before testing
    if [ "$CLEANUP_ANOMALIES" = "true" ]; then
        record_baseline_anomalies "$CONFIG_FILE" "$BASELINE_FILE"
    fi
    
    # Execute pipeline stages
    local pipeline_start
    pipeline_start=$(get_timestamp)
    
    test_data_preparation
    model_evaluation
    correlation_testing
    performance_testing
    
    local pipeline_end
    pipeline_end=$(get_timestamp)
    
    # Cleanup anomalies if enabled
    if [ "$CLEANUP_ANOMALIES" = "true" ]; then
        cleanup_anomalies_after_baseline "$CONFIG_FILE" "$BASELINE_FILE"
    fi
    
    # Generate report
    generate_report
    
    local duration
    duration=$(calculate_duration "$pipeline_start" "$pipeline_end")
    success "Test pipeline completed in $(format_duration $duration)"
}

################################################################################
# Argument Parsing
################################################################################

show_help() {
    cat << EOF
Usage: $0 [config_file] [options]

Options:
  --skip-data-prep     Skip test data preparation
  --skip-evaluation    Skip model evaluation
  --skip-correlation   Skip correlation testing
  --skip-performance   Skip performance testing
  --cleanup-anomalies  Clean up test anomalies (default)
  --no-cleanup         Keep test anomalies
  --help               Show this help message

FIXED VERSION - Includes:
  - Skips metadata files during processing
  - Improved model detection and debugging
  - Better error messages
  - Timeout handling for long-running jobs

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-data-prep)     SKIP_DATA_PREP=true; shift ;;
        --skip-evaluation)    SKIP_EVALUATION=true; shift ;;
        --skip-correlation)   SKIP_CORRELATION=true; shift ;;
        --skip-performance)   SKIP_PERFORMANCE=true; shift ;;
        --cleanup-anomalies)  CLEANUP_ANOMALIES=true; shift ;;
        --no-cleanup)         CLEANUP_ANOMALIES=false; shift ;;
        --help)               show_help; exit 0 ;;
        *)
            if [[ -f "$1" ]]; then
                CONFIG_FILE="$1"
            fi
            shift
            ;;
    esac
done

# Run main function
main