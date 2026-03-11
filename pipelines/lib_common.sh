#!/usr/bin/env bash
################################################################################
# Common Library for Pipeline Scripts
# Provides shared functions, logging, color codes, and utility helpers
################################################################################

# Prevent double-sourcing
if [ -n "${_LIB_COMMON_LOADED+x}" ]; then
    return 0 2>/dev/null || true
fi
_LIB_COMMON_LOADED=1

################################################################################
# Color Codes
################################################################################

readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly RED='\033[0;31m'
readonly CYAN='\033[0;36m'
readonly PURPLE='\033[0;35m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

################################################################################
# Python Detection
# Prefer the project venv if it exists, so all dependencies are available
################################################################################

# Resolve project root (parent of the pipelines/ directory)
_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PROJECT_ROOT="$(cd "$_LIB_DIR/.." && pwd)"

if [ -x "$_PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON_CMD="$_PROJECT_ROOT/venv/bin/python"
elif [ -x "$_PROJECT_ROOT/venv/bin/python3" ]; then
    PYTHON_CMD="$_PROJECT_ROOT/venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}[ERROR]${NC} No python interpreter found"
    exit 1
fi

################################################################################
# Logging Functions
################################################################################

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${CYAN}[WARNING]${NC} $1"
}

stage() {
    echo ""
    echo -e "${PURPLE}${BOLD}══════════════════════════════════════════${NC}"
    echo -e "${PURPLE}${BOLD}  $1${NC}"
    echo -e "${PURPLE}${BOLD}══════════════════════════════════════════${NC}"
}

alert() {
    echo -e "${RED}${BOLD}[ALERT]${NC} $1"
}

################################################################################
# Error Handling
################################################################################

die() {
    error "$1"
    exit 1
}

check_status() {
    local msg="$1"
    if [ $? -ne 0 ]; then
        error "$msg"
        return 1
    fi
    return 0
}

################################################################################
# Cleanup / Trap Management
################################################################################

_CLEANUP_FILES=()

register_cleanup_file() {
    _CLEANUP_FILES+=("$1")
}

_cleanup_handler() {
    for f in "${_CLEANUP_FILES[@]}"; do
        if [ -f "$f" ]; then
            rm -f "$f"
        fi
    done
}

trap _cleanup_handler EXIT

################################################################################
# Directory Helpers
################################################################################

create_pipeline_directories() {
    for dir in "$@"; do
        if [ -n "$dir" ]; then
            mkdir -p "$dir"
        fi
    done
}

################################################################################
# Timing Helpers
################################################################################

get_timestamp() {
    date +%s
}

calculate_duration() {
    local start="$1"
    local end="$2"
    echo $(( end - start ))
}

format_duration() {
    local seconds="$1"
    if [ "$seconds" -lt 60 ]; then
        echo "${seconds}s"
    elif [ "$seconds" -lt 3600 ]; then
        local mins=$(( seconds / 60 ))
        local secs=$(( seconds % 60 ))
        echo "${mins}m ${secs}s"
    else
        local hours=$(( seconds / 3600 ))
        local mins=$(( (seconds % 3600) / 60 ))
        local secs=$(( seconds % 60 ))
        echo "${hours}h ${mins}m ${secs}s"
    fi
}

################################################################################
# Validation Helpers
################################################################################

validate_json_file() {
    local file="$1"
    if [ ! -f "$file" ]; then
        error "File not found: $file"
        return 1
    fi
    $PYTHON_CMD -c "import json; json.load(open('$file'))" 2>/dev/null
    return $?
}

################################################################################
# Prerequisites
################################################################################

check_all_prerequisites() {
    local config_file="${1:-config/config.yaml}"

    stage "Checking Prerequisites"

    # Check Python
    if ! command -v "$PYTHON_CMD" &>/dev/null; then
        error "Python ($PYTHON_CMD) is not available"
        return 1
    fi
    success "Python: $($PYTHON_CMD --version 2>&1)"

    # Check api_client.py
    if [ ! -f "api_client.py" ]; then
        error "api_client.py not found in $(pwd)"
        return 1
    fi
    success "api_client.py found"

    # Check config file
    if [ ! -f "$config_file" ]; then
        error "Config file not found: $config_file"
        return 1
    fi
    success "Config: $config_file"

    # Check API server is running
    local api_ok
    api_ok=$($PYTHON_CMD -c "
import sys
try:
    import requests
    r = requests.get('http://localhost:8000/', timeout=5)
    if r.status_code == 200:
        print('OK')
    else:
        print('FAIL')
except:
    print('FAIL')
" 2>/dev/null)

    if [ "$api_ok" != "OK" ]; then
        error "API server is not responding at http://localhost:8000"
        error "Please start it first:  bash start_api.sh"
        return 1
    fi
    success "API server is running"

    success "All prerequisites met"
    return 0
}

################################################################################
# System Initialization
################################################################################

initialize_system() {
    local config_file="${1:-config/config.yaml}"

    stage "Initializing System"

    info "Loading configuration from $config_file"

    $PYTHON_CMD api_client.py init "$config_file" 2>&1

    if [ $? -eq 0 ]; then
        success "System initialized successfully"
    else
        error "Failed to initialize system"
        return 1
    fi
}

################################################################################
# Anomaly Baseline / Cleanup Helpers
################################################################################

record_baseline_anomalies() {
    local config_file="$1"
    local baseline_file="$2"

    info "Recording baseline anomaly count..."

    local count
    count=$($PYTHON_CMD api_client.py list-anomalies --limit 1 2>/dev/null | \
            $PYTHON_CMD -c "import json, sys; data=json.load(sys.stdin); print(len(data))" 2>/dev/null || echo "0")

    echo "$count" > "$baseline_file"
    info "Baseline anomaly count: $count"
}

cleanup_anomalies_after_baseline() {
    local config_file="$1"
    local baseline_file="$2"

    if [ ! -f "$baseline_file" ]; then
        warn "Baseline file not found, skipping cleanup"
        return 0
    fi

    stage "Cleaning Up Pipeline Anomalies"

    info "Removing anomalies created during this pipeline run..."

    $PYTHON_CMD -c "
import yaml, sys, json
try:
    with open('$config_file', 'r') as f:
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
    cursor.execute('''
        DELETE FROM anomalies
        WHERE created_at > NOW() - INTERVAL '2 hours'
    ''')
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    print(f'Cleaned up {deleted} pipeline anomalies')
except Exception as e:
    print(f'Warning: Could not clean up anomalies: {e}', file=sys.stderr)
" 2>&1

    success "Anomaly cleanup completed"
}
