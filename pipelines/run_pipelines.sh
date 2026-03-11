#!/usr/bin/env bash
################################################################################
# Master Pipeline Orchestrator
# Simplified version that coordinates all pipeline stages
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

CONFIG_FILE="${CONFIG_FILE:-config/config.yaml}"
LOG_DIR="logs/master_pipeline"
LOG_FILE="$LOG_DIR/run_$(date +'%Y%m%d_%H%M%S').log"
REPORT_DIR="reports/master_pipeline"
REPORT_FILE="$REPORT_DIR/summary_$(date +'%Y%m%d_%H%M%S').md"

# Pipeline stage control
RUN_TRAINING=${RUN_TRAINING:-true}
RUN_TESTING=${RUN_TESTING:-true}
RUN_VALIDATION=${RUN_VALIDATION:-true}
RUN_DETECTION=${RUN_DETECTION:-true}

# Cleanup options (disabled by default to preserve anomalies for correlation analysis)
CLEANUP_TRAINING=${CLEANUP_TRAINING:-false}
CLEANUP_TESTING=${CLEANUP_TESTING:-false}
CLEANUP_VALIDATION=${CLEANUP_VALIDATION:-false}

# Error handling
STOP_ON_ERROR=${STOP_ON_ERROR:-true}

# Timing tracking
declare -A STAGE_START_TIMES
declare -A STAGE_END_TIMES
declare -A STAGE_DURATIONS
declare -A STAGE_STATUS

################################################################################
# Pipeline Stage Execution
################################################################################

run_pipeline_stage() {
    local stage_name="$1"
    local pipeline_script="$2"
    shift 2
    local args="$@"
    
    stage "Executing: $stage_name"
    
    # Check if pipeline script exists
    if [ ! -f "$pipeline_script" ]; then
        error "Pipeline script not found: $pipeline_script"
        STAGE_STATUS[$stage_name]="FAILED"
        return 1
    fi
    
    # Make script executable
    chmod +x "$pipeline_script"
    
    # Start timer
    STAGE_START_TIMES[$stage_name]=$(get_timestamp)
    
    # Execute pipeline — capture real exit code via PIPESTATUS
    info "Running: $pipeline_script $args"
    echo ""
    echo "========== Pipeline Output Begin =========="

    local exit_code
    set +e
    bash "$pipeline_script" $args 2>&1 | tee -a "$LOG_FILE"
    exit_code=${PIPESTATUS[0]}
    set -e

    echo "========== Pipeline Output End =========="
    echo ""

    STAGE_END_TIMES[$stage_name]=$(get_timestamp)
    STAGE_DURATIONS[$stage_name]=$(calculate_duration "${STAGE_START_TIMES[$stage_name]}" "${STAGE_END_TIMES[$stage_name]}")

    if [ $exit_code -eq 0 ]; then
        STAGE_STATUS[$stage_name]="SUCCESS"
        local duration_str
        duration_str=$(format_duration "${STAGE_DURATIONS[$stage_name]}")
        success "$stage_name completed in $duration_str"
        return 0
    else
        STAGE_STATUS[$stage_name]="FAILED"
        error "$stage_name failed (exit code: $exit_code)"
        return 1
    fi
}

################################################################################
# Pipeline Stages
################################################################################

run_training() {
    if [ "$RUN_TRAINING" != "true" ]; then
        info "Skipping training stage"
        STAGE_STATUS["Training"]="SKIPPED"
        return 0
    fi
    
    local cleanup_flag=""
    if [ "$CLEANUP_TRAINING" = "true" ]; then
        cleanup_flag="--cleanup-anomalies"
    else
        cleanup_flag="--no-cleanup"
    fi
    
    run_pipeline_stage "Training" "$SCRIPT_DIR/training_pipeline.sh" "$CONFIG_FILE" $cleanup_flag
}

run_testing() {
    if [ "$RUN_TESTING" != "true" ]; then
        info "Skipping testing stage"
        STAGE_STATUS["Testing"]="SKIPPED"
        return 0
    fi
    
    local cleanup_flag=""
    if [ "$CLEANUP_TESTING" = "true" ]; then
        cleanup_flag="--cleanup-anomalies"
    else
        cleanup_flag="--no-cleanup"
    fi
    
    run_pipeline_stage "Testing" "$SCRIPT_DIR/test_pipeline.sh" "$CONFIG_FILE" $cleanup_flag
}

run_validation() {
    if [ "$RUN_VALIDATION" != "true" ]; then
        info "Skipping validation stage"
        STAGE_STATUS["Validation"]="SKIPPED"
        return 0
    fi
    
    run_pipeline_stage "Validation" "$SCRIPT_DIR/validation_pipeline.sh" "$CONFIG_FILE"
}

run_detection() {
    if [ "$RUN_DETECTION" != "true" ]; then
        info "Skipping detection stage"
        STAGE_STATUS["Detection"]="SKIPPED"
        return 0
    fi
    
    run_pipeline_stage "Detection" "$SCRIPT_DIR/detect_anomalies_pipeline.sh" "$CONFIG_FILE"
}

################################################################################
# Reporting
################################################################################

generate_summary_report() {
    stage "Generating Summary Report"
    
    cat > "$REPORT_FILE" << EOF
# Master Pipeline Execution Report

**Generated:** $(date)
**Configuration:** $CONFIG_FILE

## Execution Summary

EOF
    
    # Add stage results
    echo "### Pipeline Stages" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    local all_stages=("Training" "Testing" "Validation" "Detection")
    
    for stage in "${all_stages[@]}"; do
        local status="${STAGE_STATUS[$stage]:-NOT_RUN}"
        local duration="${STAGE_DURATIONS[$stage]:-0}"
        local duration_str
        duration_str=$(format_duration "$duration")
        
        case "$status" in
            SUCCESS)
                echo "- ✅ **$stage**: Success ($duration_str)" >> "$REPORT_FILE"
                ;;
            FAILED)
                echo "- ❌ **$stage**: Failed ($duration_str)" >> "$REPORT_FILE"
                ;;
            SKIPPED)
                echo "- ⏭️ **$stage**: Skipped" >> "$REPORT_FILE"
                ;;
            *)
                echo "- ⚪ **$stage**: Not Run" >> "$REPORT_FILE"
                ;;
        esac
    done
    
    # Add overall statistics
    local success_count=0
    local failed_count=0
    local skipped_count=0
    
    for stage in "${all_stages[@]}"; do
        case "${STAGE_STATUS[$stage]}" in
            SUCCESS) success_count=$((success_count + 1)) ;;
            FAILED) failed_count=$((failed_count + 1)) ;;
            SKIPPED) skipped_count=$((skipped_count + 1)) ;;
        esac
    done
    
    echo "" >> "$REPORT_FILE"
    echo "### Statistics" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "- Successful Stages: $success_count" >> "$REPORT_FILE"
    echo "- Failed Stages: $failed_count" >> "$REPORT_FILE"
    echo "- Skipped Stages: $skipped_count" >> "$REPORT_FILE"
    
    # Calculate total duration
    local total_duration=0
    for stage in "${all_stages[@]}"; do
        local dur="${STAGE_DURATIONS[$stage]:-0}"
        total_duration=$((total_duration + dur))
    done
    
    echo "- Total Duration: $(format_duration $total_duration)" >> "$REPORT_FILE"
    
    # Add next steps
    echo "" >> "$REPORT_FILE"
    echo "## Next Steps" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    if [ $failed_count -gt 0 ]; then
        echo "⚠️ Some stages failed. Review logs at: $LOG_FILE" >> "$REPORT_FILE"
    elif [ "${STAGE_STATUS[Validation]}" = "SUCCESS" ]; then
        echo "✅ All validation passed! Ready for production deployment." >> "$REPORT_FILE"
    else
        echo "ℹ️ Review individual pipeline reports for detailed results." >> "$REPORT_FILE"
    fi
    
    info "Summary report saved to: $REPORT_FILE"
    success "Report generation completed"
}

################################################################################
# Main Execution
################################################################################

main() {
    # Print banner
    echo -e "${BOLD}${PURPLE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${PURPLE}║     ANOMALY DETECTION MASTER PIPELINE                  ║${NC}"
    echo -e "${BOLD}${PURPLE}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    log "Starting master pipeline execution"
    log "Configuration: $CONFIG_FILE"
    log "Log file: $LOG_FILE"
    echo ""
    
    # Create directories
    create_pipeline_directories "$LOG_DIR" "$REPORT_DIR"
    
    # Display configuration
    info "Pipeline Configuration:"
    info "  Training:   $RUN_TRAINING (cleanup: $CLEANUP_TRAINING)"
    info "  Testing:    $RUN_TESTING (cleanup: $CLEANUP_TESTING)"
    info "  Validation: $RUN_VALIDATION (cleanup: $CLEANUP_VALIDATION)"
    info "  Detection:  $RUN_DETECTION"
    info "  Stop on error: $STOP_ON_ERROR"
    echo ""
    
    # Check prerequisites
    check_all_prerequisites "$CONFIG_FILE" || die "Prerequisites check failed"
    
    # Track overall start time
    local pipeline_start
    pipeline_start=$(get_timestamp)
    
    # Execute pipeline stages
    local failed=false
    
    if run_training; then
        : # Success, continue
    else
        failed=true
        if [ "$STOP_ON_ERROR" = "true" ]; then
            error "Training failed, stopping pipeline"
        fi
    fi
    
    if [ "$failed" = "false" ] || [ "$STOP_ON_ERROR" != "true" ]; then
        if run_testing; then
            : # Success, continue
        else
            failed=true
            if [ "$STOP_ON_ERROR" = "true" ]; then
                error "Testing failed, stopping pipeline"
            fi
        fi
    fi
    
    if [ "$failed" = "false" ] || [ "$STOP_ON_ERROR" != "true" ]; then
        if run_validation; then
            : # Success, continue
        else
            failed=true
            if [ "$STOP_ON_ERROR" = "true" ]; then
                error "Validation failed, stopping pipeline"
            fi
        fi
    fi
    
    if [ "$failed" = "false" ] || [ "$STOP_ON_ERROR" != "true" ]; then
        if run_detection; then
            : # Success, continue
        else
            failed=true
        fi
    fi
    
    # Calculate total time
    local pipeline_end
    pipeline_end=$(get_timestamp)
    local total_duration
    total_duration=$(calculate_duration "$pipeline_start" "$pipeline_end")
    
    # Generate summary report
    generate_summary_report
    
    # Final status
    echo ""
    if [ "$failed" = "true" ]; then
        error "Master pipeline completed with errors"
        info "Total duration: $(format_duration $total_duration)"
        info "Check report: $REPORT_FILE"
        exit 1
    else
        success "Master pipeline completed successfully!"
        info "Total duration: $(format_duration $total_duration)"
        info "Check report: $REPORT_FILE"
        exit 0
    fi
}

################################################################################
# Argument Parsing
################################################################################

show_help() {
    cat << EOF
Usage: $0 [options]

Pipeline Control:
  --skip-training          Skip training stage
  --skip-testing           Skip testing stage  
  --skip-validation        Skip validation stage
  --skip-detection         Skip detection stage
  --only-training          Run only training
  --only-testing           Run only testing
  --only-validation        Run only validation
  --only-detection         Run only detection

Cleanup Options:
  --cleanup-training       Clean up training anomalies (default)
  --no-cleanup-training    Keep training anomalies
  --cleanup-testing        Clean up testing anomalies (default)
  --no-cleanup-testing     Keep testing anomalies
  --cleanup-validation     Clean up validation anomalies (default)
  --no-cleanup-validation  Keep validation anomalies
  --cleanup-all            Enable all cleanup (default)
  --no-cleanup-all         Disable all cleanup

Configuration:
  --config FILE            Specify configuration file (default: config/config.yaml)

Error Handling:
  --stop-on-error          Stop if any stage fails (default)
  --continue-on-error      Continue even if stages fail

Other:
  --help                   Show this help message

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        # Stage control
        --skip-training)        RUN_TRAINING=false; shift ;;
        --skip-testing)         RUN_TESTING=false; shift ;;
        --skip-validation)      RUN_VALIDATION=false; shift ;;
        --skip-detection)       RUN_DETECTION=false; shift ;;
        
        --only-training)
            RUN_TRAINING=true
            RUN_TESTING=false
            RUN_VALIDATION=false
            RUN_DETECTION=false
            shift
            ;;
        --only-testing)
            RUN_TRAINING=false
            RUN_TESTING=true
            RUN_VALIDATION=false
            RUN_DETECTION=false
            shift
            ;;
        --only-validation)
            RUN_TRAINING=false
            RUN_TESTING=false
            RUN_VALIDATION=true
            RUN_DETECTION=false
            shift
            ;;
        --only-detection)
            RUN_TRAINING=false
            RUN_TESTING=false
            RUN_VALIDATION=false
            RUN_DETECTION=true
            shift
            ;;
        
        # Cleanup options
        --cleanup-training)      CLEANUP_TRAINING=true; shift ;;
        --no-cleanup-training)   CLEANUP_TRAINING=false; shift ;;
        --cleanup-testing)       CLEANUP_TESTING=true; shift ;;
        --no-cleanup-testing)    CLEANUP_TESTING=false; shift ;;
        --cleanup-validation)    CLEANUP_VALIDATION=true; shift ;;
        --no-cleanup-validation) CLEANUP_VALIDATION=false; shift ;;
        --cleanup-all)
            CLEANUP_TRAINING=true
            CLEANUP_TESTING=true
            CLEANUP_VALIDATION=true
            shift
            ;;
        --no-cleanup-all)
            CLEANUP_TRAINING=false
            CLEANUP_TESTING=false
            CLEANUP_VALIDATION=false
            shift
            ;;
        
        # Configuration
        --config)               CONFIG_FILE="$2"; shift 2 ;;
        
        # Error handling
        --stop-on-error)        STOP_ON_ERROR=true; shift ;;
        --continue-on-error)    STOP_ON_ERROR=false; shift ;;
        
        # Help
        --help)                 show_help; exit 0 ;;
        
        *)
            error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main