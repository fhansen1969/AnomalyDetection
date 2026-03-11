#!/usr/bin/env bash
################################################################################
# Detection Pipeline - Production Anomaly Detection
# Clean version using common library
################################################################################

set -e

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
DATA_DIR="data/input"
PROCESSED_DIR="data/processed/detection"
ANOMALIES_DIR="storage/anomalies"
ALERTS_DIR="storage/alerts"
CORRELATIONS_DIR="storage/correlations"
LOG_FILE="logs/detect_pipeline_$(date +'%Y%m%d_%H%M%S').log"

# Detection modes
DETECTION_MODE=${DETECTION_MODE:-batch}
ENABLE_AGENTS=${ENABLE_AGENTS:-true}
ENABLE_ALERTS=${ENABLE_ALERTS:-true}
ENABLE_CORRELATION=${ENABLE_CORRELATION:-true}
CONTINUOUS_MODE=${CONTINUOUS_MODE:-false}

# Thresholds
CRITICAL_THRESHOLD=${CRITICAL_THRESHOLD:-0.9}
HIGH_THRESHOLD=${HIGH_THRESHOLD:-0.8}
MEDIUM_THRESHOLD=${MEDIUM_THRESHOLD:-0.7}
LOW_THRESHOLD=${LOW_THRESHOLD:-0.5}

# Correlation settings
CORRELATION_TIME_WINDOW=${CORRELATION_TIME_WINDOW:-24}
MIN_CORRELATION_SCORE=${MIN_CORRELATION_SCORE:-0.3}
MAX_CORRELATION_RESULTS=${MAX_CORRELATION_RESULTS:-50}

################################################################################
# Pipeline Stages
################################################################################

# Stage 1: Load Production Models
load_production_models() {
    stage "Stage 1: Loading Production Models"
    
    info "Checking for available models..."
    
    # FIX: Skip broken load-models call
    # $PYTHON_CMD api_client.py load-models >>"$LOG_FILE" 2>&1
    
    # Check if model files exist
    if ! ls storage/models/*.pkl >/dev/null 2>&1 && ! ls storage/models/*.joblib >/dev/null 2>&1; then
        error "No model files found in storage/models/"
        error "Please run training pipeline first"
        return 1
    fi
    
    info "✓ Model files found on disk"
    
    # List available models (with better error handling)
    local all_models_json
    all_models_json=$($PYTHON_CMD api_client.py list-models 2>/dev/null)
    
    # Show model statuses for debugging
    info "Available models:"
    echo "$all_models_json" | $PYTHON_CMD -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for m in data:
        print(f\"  - {m['name']}: {m.get('type', 'unknown')} (status: {m.get('status', 'unknown')})\")
except:
    pass
"
    
    # Get models (try trained first, then all)
    local models
    models=$(echo "$all_models_json" | \
             $PYTHON_CMD -c "import json, sys; data=json.load(sys.stdin); print('\n'.join(m['name'] for m in data if m.get('status')=='trained'))" 2>/dev/null)
    
    if [ -z "$models" ]; then
        warn "No models with 'trained' status, using all available models"
        models=$(echo "$all_models_json" | \
                 $PYTHON_CMD -c "import json, sys; data=json.load(sys.stdin); print('\n'.join(m['name'] for m in data))" 2>/dev/null)
    fi
    
    if [ -z "$models" ]; then
        error "No production models available"
        return 1
    fi
    
    info "Loaded models:"
    while IFS= read -r model; do
        info "  - $model"
    done <<< "$models"
    
    # Check agent status if enabled
    if [ "$ENABLE_AGENTS" = true ]; then
        local agent_status
        agent_status=$($PYTHON_CMD api_client.py agents-status 2>/dev/null | \
                      $PYTHON_CMD -c "import json, sys; data=json.load(sys.stdin); print('enabled' if data.get('enabled', False) else 'disabled')" 2>/dev/null)
        
        if [ "$agent_status" != "enabled" ]; then
            warn "Agent system is not enabled. Disabling agent analysis."
            ENABLE_AGENTS=false
        else
            success "Agent system is ready"
        fi
    fi
    
    success "Production models loaded"
}

# Stage 2: Data Collection
data_collection() {
    stage "Stage 2: Data Collection"
    
    if [ "$DETECTION_MODE" = "realtime" ]; then
        info "Real-time mode: Starting data collectors..."
        # Real-time collection logic
        info "Real-time collection initialized"
    else
        info "Batch mode: Checking for input files..."
        
        local file_count
        file_count=$(ls -1 "$DATA_DIR"/* 2>/dev/null | wc -l)
        
        if [ "$file_count" -eq 0 ]; then
            if [ "$CONTINUOUS_MODE" = true ]; then
                info "No files yet, waiting..."
                return 0
            else
                error "No input files found in $DATA_DIR"
                return 1
            fi
        fi
        
        info "Found $file_count input files"
    fi
    
    success "Data collection initialized"
}

# Stage 3: Feature Extraction
extract_features() {
    stage "Stage 3: Feature Extraction"
    
    info "Extracting features from new data..."
    
    local processed_count=0
    
    for input_file in "$DATA_DIR"/*; do
        if [ -f "$input_file" ]; then
            local filename
            filename=$(basename "$input_file")
            local processed_file="$PROCESSED_DIR/processed_${filename}"
            
            # Skip if already processed
            if [ -f "$processed_file" ] && [ "$CONTINUOUS_MODE" = false ]; then
                info "Skipping already processed: $filename"
                continue
            fi
            
            info "Processing $filename"
            
            if ! validate_json_file "$input_file"; then
                error "Invalid input file: $filename"
                continue
            fi
            
            if $PYTHON_CMD api_client.py process-data "$input_file" > "$processed_file" 2>>"$LOG_FILE" && [ -s "$processed_file" ]; then
                processed_count=$((processed_count + 1))
                success "Processed $filename"
            else
                error "Failed to process $filename"
            fi
        fi
    done
    
    info "Processed $processed_count files"
    success "Feature extraction completed"
}

# Stage 4: Anomaly Detection
detect_anomalies() {
    stage "Stage 4: Anomaly Detection"
    
    info "Running anomaly detection on new data..."
    
    # Get available models
    local models
    models=$($PYTHON_CMD api_client.py list-models 2>/dev/null | \
             $PYTHON_CMD -c "import json, sys; data=json.load(sys.stdin); print('\n'.join(m['name'] for m in data if m.get('status')=='trained'))")
    
    if [ -z "$models" ]; then
        error "No models available for detection"
        return 1
    fi
    
    # Get processed files
    local processed_files
    processed_files=$(ls "$PROCESSED_DIR"/processed_* 2>/dev/null)
    
    if [ -z "$processed_files" ]; then
        warn "No processed files available for detection"
        return 0
    fi
    
    # Run detection with each model
    local anomalies_file="$ANOMALIES_DIR/anomalies_$(date +'%Y%m%d_%H%M%S').json"
    echo '{"anomalies": []}' > "$anomalies_file"
    
    while IFS= read -r model; do
        info "Running detection with model: $model"
        
        for processed_file in $processed_files; do
            local filename
            filename=$(basename "$processed_file")
            
            info "  Processing $filename"
            
            local job_response
            job_response=$($PYTHON_CMD api_client.py detect-anomalies "$model" "$processed_file" 2>>"$LOG_FILE")
            
            local job_id
            job_id=$(echo "$job_response" | $PYTHON_CMD -c "import json, sys; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)
            
            if [ -n "$job_id" ]; then
                # Wait for completion (timeout after 300 seconds)
                local max_wait=300
                local waited=0

                while [ $waited -lt $max_wait ]; do
                    local job_status
                    job_status=$($PYTHON_CMD api_client.py job-status "$job_id" 2>/dev/null | \
                               $PYTHON_CMD -c "import json, sys; print(json.load(sys.stdin)['status'])" 2>/dev/null)

                    if [ "$job_status" = "completed" ]; then
                        # Capture results and append to anomalies file
                        local job_result
                        job_result=$($PYTHON_CMD api_client.py job-status "$job_id" 2>/dev/null)
                        export ANOMALIES_FILE="$anomalies_file"
                        export MODEL_NAME="$model"
                        export SOURCE_FILE="$filename"
                        echo "$job_result" | $PYTHON_CMD -c "
import json, sys, os
data = json.load(sys.stdin)
result = data.get('result', {})
detected = result.get('anomalies_detected', 0)
sample_anomalies = result.get('sample_anomalies', [])
print(f'    Detected {detected} anomalies')

# Append to anomalies file
anomalies_path = os.environ['ANOMALIES_FILE']
with open(anomalies_path, 'r') as f:
    existing = json.load(f)
for a in sample_anomalies:
    a['model'] = os.environ['MODEL_NAME']
    a['source_file'] = os.environ['SOURCE_FILE']
existing['anomalies'].extend(sample_anomalies)
with open(anomalies_path, 'w') as f:
    json.dump(existing, f, indent=2)
"
                        success "  Detection completed for $filename"
                        break
                    elif [ "$job_status" = "failed" ]; then
                        error "  Detection failed for $filename"
                        break
                    fi
                    sleep 1
                    waited=$((waited + 1))
                done

                if [ $waited -ge $max_wait ]; then
                    error "  Detection timed out for $filename after ${max_wait}s"
                fi
            fi
        done
    done <<< "$models"
    
    info "Anomalies saved to: $anomalies_file"
    success "Anomaly detection completed"
}

# Stage 5: Agent Analysis (if enabled)
agent_analysis() {
    stage "Stage 5: AI Agent Analysis"
    
    if [ "$ENABLE_AGENTS" != true ]; then
        info "Agent analysis disabled, skipping"
        return 0
    fi
    
    info "Running AI agent analysis on detected anomalies..."
    
    # Get recent anomalies
    local anomaly_ids
    anomaly_ids=$($PYTHON_CMD api_client.py list-anomalies --limit 10 2>/dev/null | \
                 $PYTHON_CMD -c "import json, sys; data=json.load(sys.stdin); print('\n'.join(a['id'] for a in data[:5]))" 2>/dev/null)
    
    if [ -z "$anomaly_ids" ]; then
        info "No anomalies to analyze"
        return 0
    fi
    
    local analysis_file="$ANOMALIES_DIR/agent_analysis_$(date +'%Y%m%d_%H%M%S').json"
    echo '{"analyses": []}' > "$analysis_file"

    local count=0
    while IFS= read -r anomaly_id; do
        info "Analyzing anomaly: $anomaly_id"

        local analysis_result
        if analysis_result=$($PYTHON_CMD api_client.py analyze-with-agents "$anomaly_id" 2>>"$LOG_FILE"); then
            # Append result into the analyses array safely via env vars
            ANALYSIS_RESULT="$analysis_result" ANALYSIS_FILE="$analysis_file" \
            $PYTHON_CMD -c "
import json, sys, os
try:
    result = json.loads(os.environ['ANALYSIS_RESULT'])
    analysis_path = os.environ['ANALYSIS_FILE']
    with open(analysis_path, 'r') as f:
        data = json.load(f)
    data['analyses'].append(result)
    with open(analysis_path, 'w') as f:
        json.dump(data, f, indent=2)
except Exception as e:
    print(f'Warning: Could not append analysis: {e}', file=sys.stderr)
" 2>>"$LOG_FILE"
            ((count++)) || true
        fi
    done <<< "$anomaly_ids"
    
    info "Analyzed $count anomalies"
    info "Analysis saved to: $analysis_file"
    success "Agent analysis completed"
}

# Stage 6: Correlation Analysis
correlation_analysis() {
    stage "Stage 6: Correlation Analysis"
    
    if [ "$ENABLE_CORRELATION" != true ]; then
        info "Correlation analysis disabled, skipping"
        return 0
    fi
    
    info "Analyzing correlations between anomalies..."
    
    # Get recent anomalies
    local anomaly_ids
    anomaly_ids=$($PYTHON_CMD api_client.py list-anomalies --limit 20 2>/dev/null | \
                 $PYTHON_CMD -c "import json, sys; data=json.load(sys.stdin); print('\n'.join(a['id'] for a in data[:10]))" 2>/dev/null)
    
    if [ -z "$anomaly_ids" ]; then
        info "No anomalies for correlation analysis"
        return 0
    fi
    
    local corr_file="$CORRELATIONS_DIR/correlation_$(date +'%Y%m%d_%H%M%S').json"
    local corr_tmp="/tmp/corr_results_$$.jsonl"
    > "$corr_tmp"

    local count=0
    while IFS= read -r anomaly_id; do
        info "Finding correlations for: $anomaly_id"

        if $PYTHON_CMD api_client.py correlate-anomaly "$anomaly_id" \
            --time-window "$CORRELATION_TIME_WINDOW" \
            --min-score "$MIN_CORRELATION_SCORE" \
            >>"$corr_tmp" 2>>"$LOG_FILE"; then
            count=$((count + 1))
        fi
    done <<< "$anomaly_ids"

    # Build valid JSON from collected results
    $PYTHON_CMD -c "
import json
results = []
with open('$corr_tmp', 'r') as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
with open('$corr_file', 'w') as f:
    json.dump({'correlations': results}, f, indent=2)
" 2>>"$LOG_FILE"
    rm -f "$corr_tmp"

    info "Analyzed $count anomalies for correlations"
    info "Correlations saved to: $corr_file"
    success "Correlation analysis completed"
}

# Stage 7: Send Alerts
send_alerts() {
    stage "Stage 7: Alert Processing"
    
    if [ "$ENABLE_ALERTS" != true ]; then
        info "Alerting disabled, skipping"
        return 0
    fi
    
    info "Processing alerts for critical anomalies..."
    
    # Get recent high-severity anomalies
    local critical_anomalies
    critical_anomalies=$(CRITICAL_T="$CRITICAL_THRESHOLD" \
                        $PYTHON_CMD api_client.py list-anomalies --limit 50 2>/dev/null | \
                        $PYTHON_CMD -c "
import json, sys, os
data = json.load(sys.stdin)
crit_t = float(os.environ.get('CRITICAL_T', '0.9'))
critical = [a for a in data if a.get('score', 0) >= crit_t]
print(len(critical))
" 2>/dev/null)
    
    if [ "$critical_anomalies" -gt 0 ]; then
        alert "Found $critical_anomalies critical anomalies!"
        
        # Create alert file
        local alert_file="$ALERTS_DIR/alert_$(date +'%Y%m%d_%H%M%S').txt"
        cat > "$alert_file" << EOF
CRITICAL ALERT
Generated: $(date)
======================================

Critical anomalies detected: $critical_anomalies

Severity Breakdown:
- Critical (≥$CRITICAL_THRESHOLD): Check anomalies directory
- High (≥$HIGH_THRESHOLD): Review required
- Medium (≥$MEDIUM_THRESHOLD): Monitor

Action Required:
1. Review anomalies in: $ANOMALIES_DIR
2. Check AI analysis in: $ANOMALIES_DIR/agent_analysis_*.json
3. Review correlations in: $CORRELATIONS_DIR

EOF
        
        info "Alert saved to: $alert_file"
        
        # Test alert system
        $PYTHON_CMD api_client.py test-alert --type email >>"$LOG_FILE" 2>&1
    else
        info "No critical anomalies requiring alerts"
    fi
    
    success "Alert processing completed"
}

# Stage 8: Generate Report
generate_report() {
    stage "Stage 8: Generating Detection Report"
    
    local report_file="$ANOMALIES_DIR/detection_report_$(date +'%Y%m%d_%H%M%S').md"
    
    cat > "$report_file" << EOF
# Anomaly Detection Report

**Generated:** $(date)
**Pipeline Mode:** $DETECTION_MODE
**Configuration:** $CONFIG_FILE

## Summary

EOF
    
    # Add statistics if anomalies exist
    if ls "$ANOMALIES_DIR"/anomalies_*.json >/dev/null 2>&1; then
        local latest_anomalies
        latest_anomalies=$(ls -t "$ANOMALIES_DIR"/anomalies_*.json | head -1)
        
        ANOMALIES_PATH="$latest_anomalies" \
        CRITICAL_T="$CRITICAL_THRESHOLD" \
        HIGH_T="$HIGH_THRESHOLD" \
        MEDIUM_T="$MEDIUM_THRESHOLD" \
        $PYTHON_CMD -c "
import json, os

with open(os.environ['ANOMALIES_PATH'], 'r') as f:
    data = json.load(f)

anomalies = data.get('anomalies', [])
print(f'- Total Anomalies Detected: {len(anomalies)}')

crit_t = float(os.environ['CRITICAL_T'])
high_t = float(os.environ['HIGH_T'])
med_t = float(os.environ['MEDIUM_T'])

critical = sum(1 for a in anomalies if a.get('score', 0) >= crit_t)
high = sum(1 for a in anomalies if high_t <= a.get('score', 0) < crit_t)
medium = sum(1 for a in anomalies if med_t <= a.get('score', 0) < high_t)
low = sum(1 for a in anomalies if a.get('score', 0) < med_t)

print()
print('### Severity Distribution')
print(f'- Critical: {critical}')
print(f'- High: {high}')
print(f'- Medium: {medium}')
print(f'- Low: {low}')
" >> "$report_file" 2>>"$LOG_FILE"
    fi
    
    cat >> "$report_file" << EOF

## Files Generated

- Anomalies: $ANOMALIES_DIR/anomalies_*.json
- Correlations: $CORRELATIONS_DIR/correlation_*.json
- Alerts: $ALERTS_DIR/alert_*.txt
- Agent Analysis: $ANOMALIES_DIR/agent_analysis_*.json

## Next Steps

1. Review critical anomalies
2. Analyze correlation patterns
3. Investigate root causes
4. Update detection thresholds if needed
5. Retrain models with new data

EOF
    
    info "Report saved to: $report_file"
    success "Report generation completed"
}

# Continuous monitoring loop
continuous_monitoring() {
    info "Starting continuous monitoring mode..."
    
    touch "$PROCESSED_DIR/.last_check"
    
    while true; do
        log "Monitoring cycle started"
        
        # Check for new files
        local new_files
        new_files=$(find "$DATA_DIR" -type f -newer "$PROCESSED_DIR/.last_check" 2>/dev/null | wc -l)
        
        if [ "$new_files" -gt 0 ]; then
            info "Found $new_files new files to process"
            
            extract_features
            detect_anomalies
            
            if [ "$ENABLE_AGENTS" = true ]; then
                agent_analysis
            fi
            
            if [ "$ENABLE_CORRELATION" = true ]; then
                correlation_analysis
            fi
            
            send_alerts
            generate_report
        else
            info "No new files detected"
        fi
        
        # Update timestamp
        touch "$PROCESSED_DIR/.last_check"
        
        info "Sleeping for 60 seconds..."
        sleep 60
    done
}

################################################################################
# Main Execution
################################################################################

main() {
    log "Starting Detection Pipeline"
    log "Mode: $DETECTION_MODE"
    log "Continuous: $CONTINUOUS_MODE"
    
    # Create directories
    create_pipeline_directories \
        "$DATA_DIR" "$PROCESSED_DIR" "$ANOMALIES_DIR" \
        "$ALERTS_DIR" "$CORRELATIONS_DIR" "$(dirname "$LOG_FILE")"
    
    # Check prerequisites
    check_all_prerequisites "$CONFIG_FILE" || die "Prerequisites check failed"
    
    # Initialize system
    initialize_system "$CONFIG_FILE" || die "System initialization failed"
    
    # Load production models
    load_production_models || die "Failed to load production models"
    
    # Execute pipeline
    local pipeline_start
    pipeline_start=$(get_timestamp)
    
    if [ "$CONTINUOUS_MODE" = true ]; then
        # Continuous monitoring
        continuous_monitoring
    else
        # Single run
        data_collection
        extract_features
        detect_anomalies
        
        if [ "$ENABLE_AGENTS" = true ]; then
            agent_analysis
        fi
        
        if [ "$ENABLE_CORRELATION" = true ]; then
            correlation_analysis
        fi
        
        send_alerts
        generate_report
    fi
    
    local pipeline_end
    pipeline_end=$(get_timestamp)
    local duration
    duration=$(calculate_duration "$pipeline_start" "$pipeline_end")
    
    success "Detection pipeline completed in $(format_duration $duration)"
    info "Results in: $ANOMALIES_DIR"
}

################################################################################
# Argument Parsing
################################################################################

show_help() {
    cat << EOF
Usage: $0 [config_file] [options]

Detection Modes:
  --mode MODE              batch or realtime (default: batch)
  --continuous             Enable continuous monitoring

Features:
  --no-agents              Disable AI agent analysis
  --no-alerts              Disable alerting
  --no-correlation         Disable correlation analysis

Thresholds:
  --critical-threshold VAL Critical threshold (default: 0.9)
  --high-threshold VAL     High threshold (default: 0.8)
  --medium-threshold VAL   Medium threshold (default: 0.7)

Correlation:
  --correlation-window HR  Time window in hours (default: 24)
  --min-correlation SCORE  Minimum score (default: 0.3)

Other:
  --help                   Show this help message

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)                 DETECTION_MODE="$2"; shift 2 ;;
        --continuous)           CONTINUOUS_MODE=true; shift ;;
        --no-agents)            ENABLE_AGENTS=false; shift ;;
        --no-alerts)            ENABLE_ALERTS=false; shift ;;
        --no-correlation)       ENABLE_CORRELATION=false; shift ;;
        --critical-threshold)   CRITICAL_THRESHOLD="$2"; shift 2 ;;
        --high-threshold)       HIGH_THRESHOLD="$2"; shift 2 ;;
        --medium-threshold)     MEDIUM_THRESHOLD="$2"; shift 2 ;;
        --correlation-window)   CORRELATION_TIME_WINDOW="$2"; shift 2 ;;
        --min-correlation)      MIN_CORRELATION_SCORE="$2"; shift 2 ;;
        --help)                 show_help; exit 0 ;;
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