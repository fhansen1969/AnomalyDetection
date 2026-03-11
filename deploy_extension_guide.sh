#!/usr/bin/env bash
################################################################################
# Deployment Guide for Anomaly Detection Extensions
#
# This script provides automated deployment utilities for new collectors,
# feature extractors, models, and alert channels.
################################################################################

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_ROOT/config"
LOG_FILE="$PROJECT_ROOT/logs/deploy_extension_$(date +'%Y%m%d_%H%M%S').log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo "$(date +'%Y-%m-%d %H:%M:%S') - $*" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}✅ $*${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}❌ $*${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}⚠️  $*${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}ℹ️  $*${NC}" | tee -a "$LOG_FILE"
}

################################################################################
# UTILITY FUNCTIONS
################################################################################

check_dependencies() {
    local component="$1"
    local dependencies="$2"

    info "Checking dependencies for $component..."

    for dep in $dependencies; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            error "Missing dependency: $dep"
            return 1
        fi
    done

    success "All dependencies satisfied for $component"
}

validate_config() {
    local config_file="$1"

    info "Validating configuration file: $config_file"

    if [ ! -f "$config_file" ]; then
        error "Configuration file not found: $config_file"
        return 1
    fi

    # Basic YAML validation
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c "import yaml; yaml.safe_load(open('$config_file'))" 2>/dev/null; then
            success "Configuration file is valid YAML"
        else
            error "Configuration file contains invalid YAML"
            return 1
        fi
    fi
}

backup_existing_config() {
    local config_file="$1"
    local backup_dir="$PROJECT_ROOT/backups/extensions"

    mkdir -p "$backup_dir"

    if [ -f "$config_file" ]; then
        local backup_file="$backup_dir/$(basename "$config_file" .yaml)_$(date +'%Y%m%d_%H%M%S').yaml"
        cp "$config_file" "$backup_file"
        info "Backed up existing config to: $backup_file"
    fi
}

################################################################################
# EXTENSION DEPLOYMENT FUNCTIONS
################################################################################

deploy_collector() {
    local collector_name="$1"
    local collector_type="$2"

    log "Deploying collector: $collector_name ($collector_type)"

    # Check if collector file exists
    local collector_file="$PROJECT_ROOT/anomaly_detection/collectors/${collector_name}_collector.py"
    if [ ! -f "$collector_file" ]; then
        error "Collector file not found: $collector_file"
        return 1
    fi

    # Validate collector implementation
    if ! python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
try:
    from anomaly_detection.collectors.${collector_name}_collector import ${collector_type^}Collector
    collector = ${collector_type^}Collector('test', {})
    print('Collector implementation valid')
except Exception as e:
    print(f'Collector validation failed: {e}')
    sys.exit(1)
" 2>>"$LOG_FILE"; then
        error "Collector implementation validation failed"
        return 1
    fi

    success "Collector implementation validated"

    # Update configuration
    local config_file="$CONFIG_DIR/config.yaml"
    backup_existing_config "$config_file"

    # Add collector to enabled list if not already present
    if ! grep -q "$collector_name" "$config_file"; then
        info "Adding $collector_name to enabled collectors"

        # This is a simplified update - in practice you'd want more sophisticated YAML editing
        python3 -c "
import yaml
import sys

with open('$config_file', 'r') as f:
    config = yaml.safe_load(f)

if 'collectors' not in config:
    config['collectors'] = {'enabled': []}

if '$collector_name' not in config['collectors']['enabled']:
    config['collectors']['enabled'].append('$collector_name')

# Add basic collector config if not present
if '$collector_name' not in config['collectors']:
    config['collectors']['$collector_name'] = {
        'enabled': True,
        'batch_size': 1000
    }

with open('$config_file', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print('Configuration updated')
" 2>>"$LOG_FILE"
    fi

    success "Collector $collector_name deployed successfully"
}

deploy_feature_extractor() {
    local extractor_name="$1"
    local extractor_type="$2"

    log "Deploying feature extractor: $extractor_name ($extractor_type)"

    # Check if extractor file exists
    local extractor_file="$PROJECT_ROOT/anomaly_detection/processors/${extractor_name}_extractor.py"
    if [ ! -f "$extractor_file" ]; then
        error "Feature extractor file not found: $extractor_file"
        return 1
    fi

    # Validate extractor implementation
    if ! python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
try:
    from anomaly_detection.processors.${extractor_name}_extractor import ${extractor_type^}Extractor
    extractor = ${extractor_type^}Extractor('test', {})
    print('Feature extractor implementation valid')
except Exception as e:
    print(f'Feature extractor validation failed: {e}')
    sys.exit(1)
" 2>>"$LOG_FILE"; then
        error "Feature extractor implementation validation failed"
        return 1
    fi

    success "Feature extractor implementation validated"

    # Update configuration
    local config_file="$CONFIG_DIR/config.yaml"
    backup_existing_config "$config_file"

    # Add extractor to processors if not already present
    python3 -c "
import yaml
import sys

with open('$config_file', 'r') as f:
    config = yaml.safe_load(f)

if 'processors' not in config:
    config['processors'] = {'feature_extractors': []}

# Check if extractor already exists
existing_extractors = [e.get('name') for e in config['processors']['feature_extractors']]
if '$extractor_name' not in existing_extractors:
    config['processors']['feature_extractors'].append({
        'name': '$extractor_name',
        'numerical_fields': ['value'],
        'categorical_fields': ['category']
    })

with open('$config_file', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print('Configuration updated')
" 2>>"$LOG_FILE"

    success "Feature extractor $extractor_name deployed successfully"
}

deploy_model() {
    local model_name="$1"
    local model_type="$2"

    log "Deploying model: $model_name ($model_type)"

    # Check if model file exists
    local model_file="$PROJECT_ROOT/anomaly_detection/models/${model_name}_model.py"
    if [ ! -f "$model_file" ]; then
        error "Model file not found: $model_file"
        return 1
    fi

    # Validate model implementation
    if ! python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
try:
    from anomaly_detection.models.${model_name}_model import ${model_type^}Model
    model = ${model_type^}Model('test', {'threshold': 0.7})
    print('Model implementation valid')
except Exception as e:
    print(f'Model validation failed: {e}')
    sys.exit(1)
" 2>>"$LOG_FILE"; then
        error "Model implementation validation failed"
        return 1
    fi

    success "Model implementation validated"

    # Update configuration
    local config_file="$CONFIG_DIR/config.yaml"
    backup_existing_config "$config_file"

    # Add model to enabled list if not already present
    python3 -c "
import yaml
import sys

with open('$config_file', 'r') as f:
    config = yaml.safe_load(f)

if 'models' not in config:
    config['models'] = {'enabled': []}

if '$model_name' not in config['models']['enabled']:
    config['models']['enabled'].append('$model_name')

# Add basic model config if not present
if '$model_name' not in config['models']:
    config['models']['$model_name'] = {
        'threshold': 0.7,
        'random_state': 42
    }

with open('$config_file', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print('Configuration updated')
" 2>>"$LOG_FILE"

    success "Model $model_name deployed successfully"
}

deploy_alert_channel() {
    local channel_name="$1"
    local channel_type="$2"

    log "Deploying alert channel: $channel_name ($channel_type)"

    # Check if alert channel file exists
    local channel_file="$PROJECT_ROOT/anomaly_detection/alerts/${channel_name}_alert.py"
    if [ ! -f "$channel_file" ]; then
        error "Alert channel file not found: $channel_file"
        return 1
    fi

    # Validate alert channel implementation
    if ! python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
try:
    from anomaly_detection.alerts.${channel_name}_alert import ${channel_type^}AlertChannel
    channel = ${channel_type^}AlertChannel({'enabled': True})
    print('Alert channel implementation valid')
except Exception as e:
    print(f'Alert channel validation failed: {e}')
    sys.exit(1)
" 2>>"$LOG_FILE"; then
        error "Alert channel implementation validation failed"
        return 1
    fi

    success "Alert channel implementation validated"

    # Update configuration
    local config_file="$CONFIG_DIR/config.yaml"
    backup_existing_config "$config_file"

    # Add alert channel to alerts section
    python3 -c "
import yaml
import sys

with open('$config_file', 'r') as f:
    config = yaml.safe_load(f)

if 'alerts' not in config:
    config['alerts'] = {'enabled': True}

# Add channel config
config['alerts']['${channel_name}'] = {
    'enabled': True,
    'type': '$channel_type'
}

with open('$config_file', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print('Configuration updated')
" 2>>"$LOG_FILE"

    success "Alert channel $channel_name deployed successfully"
}

################################################################################
# TESTING AND VALIDATION
################################################################################

run_integration_tests() {
    local extension_type="$1"
    local extension_name="$2"

    info "Running integration tests for $extension_type: $extension_name"

    if [ -f "$PROJECT_ROOT/test_integration_guide.py" ]; then
        if python3 "$PROJECT_ROOT/test_integration_guide.py" --integration 2>>"$LOG_FILE"; then
            success "Integration tests passed"
        else
            warning "Integration tests failed - check logs for details"
        fi
    else
        warning "Integration test script not found"
    fi
}

validate_deployment() {
    local extension_type="$1"
    local extension_name="$2"

    info "Validating deployment of $extension_type: $extension_name"

    # Test basic import
    if ! python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
try:
    if '$extension_type' == 'collector':
        from anomaly_detection.collectors.${extension_name}_collector import *
    elif '$extension_type' == 'feature_extractor':
        from anomaly_detection.processors.${extension_name}_extractor import *
    elif '$extension_type' == 'model':
        from anomaly_detection.models.${extension_name}_model import *
    elif '$extension_type' == 'alert_channel':
        from anomaly_detection.alerts.${extension_name}_alert import *
    print('Import successful')
except Exception as e:
    print(f'Import failed: {e}')
    sys.exit(1)
" 2>>"$LOG_FILE"; then
        error "Extension import validation failed"
        return 1
    fi

    # Test configuration loading
    if ! python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
import yaml

try:
    with open('$CONFIG_DIR/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    print('Configuration loaded successfully')
except Exception as e:
    print(f'Configuration loading failed: {e}')
    sys.exit(1)
" 2>>"$LOG_FILE"; then
        error "Configuration validation failed"
        return 1
    fi

    success "Deployment validation passed"
}

################################################################################
# MAIN DEPLOYMENT FUNCTIONS
################################################################################

deploy_extension() {
    local extension_type="$1"
    local extension_name="$2"
    local class_name="$3"

    log "Starting deployment of $extension_type: $extension_name"

    # Validate inputs
    if [ -z "$extension_type" ] || [ -z "$extension_name" ]; then
        error "Usage: $0 <extension_type> <extension_name> [class_name]"
        error "extension_type: collector|feature_extractor|model|alert_channel"
        exit 1
    fi

    # Check dependencies
    check_dependencies "$extension_type" "python3"

    # Deploy based on type
    case "$extension_type" in
        "collector")
            deploy_collector "$extension_name" "${class_name:-${extension_name}}"
            ;;
        "feature_extractor")
            deploy_feature_extractor "$extension_name" "${class_name:-${extension_name}}"
            ;;
        "model")
            deploy_model "$extension_name" "${class_name:-${extension_name}}"
            ;;
        "alert_channel")
            deploy_alert_channel "$extension_name" "${class_name:-${extension_name}}"
            ;;
        *)
            error "Unknown extension type: $extension_type"
            error "Supported types: collector, feature_extractor, model, alert_channel"
            exit 1
            ;;
    esac

    # Run validation
    validate_deployment "$extension_type" "$extension_name"

    # Run integration tests
    run_integration_tests "$extension_type" "$extension_name"

    success "Deployment completed successfully!"
    info "Next steps:"
    info "  1. Restart the API server: ./start_api.sh"
    info "  2. Test the extension with sample data"
    info "  3. Monitor logs for any issues"
    info "  4. Update documentation if needed"
}

show_help() {
    cat << EOF
Anomaly Detection Extension Deployment Guide

USAGE:
    $0 <extension_type> <extension_name> [class_name]

EXTENSION TYPES:
    collector         - Data collection components
    feature_extractor - Feature processing components
    model            - Anomaly detection models
    alert_channel    - Alert notification channels

EXAMPLES:
    $0 collector elasticsearch Elasticsearch
    $0 feature_extractor time_series TimeSeries
    $0 model lstm LSTM
    $0 alert_channel teams Teams

REQUIREMENTS:
    - Extension files must be in the correct directory
    - Python dependencies must be installed
    - Configuration file must be valid YAML

DEPLOYMENT PROCESS:
    1. Validate extension implementation
    2. Update configuration files
    3. Run integration tests
    4. Provide deployment summary

For detailed implementation guides, see the extension documentation.
EOF
}

################################################################################
# MAIN EXECUTION
################################################################################

main() {
    local extension_type="$1"
    local extension_name="$2"
    local class_name="$3"

    echo "🚀 Anomaly Detection Extension Deployment Tool"
    echo "=" * 50

    if [ "$extension_type" = "help" ] || [ "$extension_type" = "--help" ] || [ "$extension_type" = "-h" ]; then
        show_help
        exit 0
    fi

    if [ -z "$extension_type" ]; then
        error "Extension type required"
        echo ""
        show_help
        exit 1
    fi

    deploy_extension "$extension_type" "$extension_name" "$class_name"
}

# Run main function with all arguments
main "$@"
