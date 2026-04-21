#!/usr/bin/env bash
################################################################################
# Cleanup Script - Reset System for Fresh Start
# Includes database cleanup and directory structure reset
#
# Usage:
#   ./cleanup.sh                  # Interactive mode (prompts for each step)
#   ./cleanup.sh --force          # Non-interactive: cleans everything without prompts
#   ./cleanup.sh --all            # Alias for --force
#   ./cleanup.sh --db             # Database cleanup only (interactive)
#   ./cleanup.sh --db --force     # Database cleanup only, non-interactive
#   ./cleanup.sh --dirs --cache   # Specific sections, interactive
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config/config.yaml"

# ---------------------------------------------------------------------------
# Read database credentials from config/config.yaml (database.connection)
# Falls back to known defaults if the file or keys are missing.
# ---------------------------------------------------------------------------
parse_yaml_value() {
    # Usage: parse_yaml_value <file> <key>
    # Searches for "  key: value" under the database.connection section.
    local file="$1" key="$2"
    # Extract the value with a simple grep+sed; handles quoted and unquoted values.
    grep -A 20 "^database:" "$file" 2>/dev/null \
        | grep -A 10 "connection:" \
        | grep "^\s*${key}:" \
        | head -1 \
        | sed "s/.*${key}:\s*['\"]*//" \
        | sed "s/['\"\r]*//" \
        | tr -d '[:space:]'
}

if [ -f "$CONFIG_FILE" ]; then
    _host=$(parse_yaml_value "$CONFIG_FILE" "host")
    _port=$(parse_yaml_value "$CONFIG_FILE" "port")
    _db=$(parse_yaml_value "$CONFIG_FILE" "database")
    _user=$(parse_yaml_value "$CONFIG_FILE" "user")
    _pass=$(parse_yaml_value "$CONFIG_FILE" "password")
fi

# Environment variable overrides take precedence; config.yaml is the next source;
# then built-in defaults.
DB_HOST="${DB_HOST:-${_host:-localhost}}"
DB_PORT="${DB_PORT:-${_port:-5432}}"
DB_NAME="${DB_NAME:-${_db:-anomaly_detection}}"
DB_USER="${DB_USER:-${_user:-anomaly_user}}"
DB_PASSWORD="${DB_PASSWORD:-${_pass:-St@rW@rs!}}"

# output_dir from config (system.output_dir); default is "results"
if [ -f "$CONFIG_FILE" ]; then
    _output_dir=$(grep -A 5 "^system:" "$CONFIG_FILE" 2>/dev/null \
        | grep "output_dir:" | head -1 \
        | sed "s/.*output_dir:\s*['\"]*//" \
        | sed "s/['\"\r]*//" \
        | tr -d '[:space:]')
fi
OUTPUT_DIR="${_output_dir:-results}"

# Tables to truncate (operational data - NOT configuration tables like models/processors/collectors)
TRUNCATE_TABLES=(
    "agent_messages"
    "agent_activities"
    "anomaly_analysis"
    "background_jobs"
    "model_states"
    "processed_data"
    "system_status"
    "jobs"
    "anomalies"
)

# Tracking for summary report
CLEANED_DB=false
CLEANED_DIRS=()
CLEANED_LOGS=false
CLEANED_CACHE=false

################################################################################
# Helper Functions
################################################################################

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# confirm <prompt> [default]
# Returns 0 (yes) or 1 (no).
# In FORCE mode always returns 0 (yes).
confirm() {
    local prompt="$1"
    local default="${2:-n}"

    if [ "$FORCE" = true ]; then
        return 0
    fi

    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n]"
    else
        prompt="$prompt [y/N]"
    fi

    read -p "$prompt " response
    response=${response:-$default}

    case "$response" in
        [Yy]* ) return 0 ;;
        * ) return 1 ;;
    esac
}

# Run a psql command with the application user credentials.
# Exports PGPASSWORD so psql never prompts interactively.
run_psql() {
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        "$@"
}

# Check whether we can connect to the database as the application user.
can_connect() {
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "SELECT 1" \
        -q --no-align --tuples-only \
        > /dev/null 2>&1
}

################################################################################
# Cleanup Functions
################################################################################

cleanup_database() {
    log "Database cleanup: host=$DB_HOST port=$DB_PORT db=$DB_NAME user=$DB_USER"

    # Check if PostgreSQL client is available
    if ! command -v psql &> /dev/null; then
        warn "PostgreSQL client (psql) not found — skipping database cleanup"
        return 0
    fi

    # Verify connectivity before asking the user
    if ! can_connect; then
        error "Cannot connect to $DB_NAME as $DB_USER on $DB_HOST:$DB_PORT"
        error "Check credentials in config/config.yaml (database.connection) or set DB_* env vars."
        return 1
    fi

    echo ""
    echo "  Tables that will be TRUNCATED (data cleared, schema kept):"
    for t in "${TRUNCATE_TABLES[@]}"; do
        echo "    - $t"
    done
    echo "  Tables NOT touched (configuration): models, processors, collectors"
    echo ""

    if ! confirm "Truncate all operational tables in '$DB_NAME'?" "n"; then
        warn "Skipped database cleanup"
        return 0
    fi

    log "Truncating tables..."

    # Build a single TRUNCATE statement with CASCADE so FK dependencies don't block.
    # Tables are listed leaf-first (children before parents) but CASCADE handles order.
    local sql=""
    sql+="BEGIN;"$'\n'
    for table in "${TRUNCATE_TABLES[@]}"; do
        sql+="TRUNCATE TABLE IF EXISTS ${table} CASCADE;"$'\n'
    done
    # Reset system_status to a clean initialized state after truncation
    sql+="INSERT INTO system_status (key, value, updated_at)"$'\n'
    sql+="VALUES ('status', '{\"initialized\": true}'::jsonb, NOW())"$'\n'
    sql+="ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();"$'\n'
    sql+="COMMIT;"$'\n'

    if echo "$sql" | run_psql -f - 2>&1; then
        success "Database tables truncated successfully"
        CLEANED_DB=true

        # Report row counts
        log "Row counts after cleanup:"
        for table in "${TRUNCATE_TABLES[@]}"; do
            local count
            count=$(run_psql -t -c "SELECT COUNT(*) FROM ${table}" 2>/dev/null | tr -d '[:space:]') || count="?"
            echo "    ${table}: ${count} rows"
        done
    else
        error "Failed to truncate database tables"
        return 1
    fi
}

cleanup_directories() {
    log "Cleaning up output/results directories..."

    local dirs_to_clean=(
        "$OUTPUT_DIR"
        "reports"
        "data/processed"
        "data/training"
        "data/validation"
        "data/test"
        "storage/anomalies"
        "storage/processed"
        "storage/state"
        "storage/backups"
    )

    for dir in "${dirs_to_clean[@]}"; do
        local full_path="$PROJECT_ROOT/$dir"
        if [ -d "$full_path" ]; then
            if confirm "Remove '$dir'?" "n"; then
                rm -rf "$full_path"
                success "Removed $dir"
                CLEANED_DIRS+=("$dir")
            else
                warn "Skipped $dir"
            fi
        fi
    done

    # Recreate the output_dir empty so the rest of the system doesn't error
    if [[ " ${CLEANED_DIRS[*]} " == *" $OUTPUT_DIR "* ]]; then
        mkdir -p "$PROJECT_ROOT/$OUTPUT_DIR"
        log "Recreated empty $OUTPUT_DIR directory"
    fi
}

cleanup_logs() {
    log "Cleaning up log files..."

    local logs_dir="$PROJECT_ROOT/logs"

    if [ ! -d "$logs_dir" ]; then
        log "No logs directory found — nothing to clean"
        return 0
    fi

    if confirm "Remove ALL log files?" "n"; then
        rm -rf "$logs_dir"
        mkdir -p "$logs_dir"
        success "Log directory cleared (directory recreated empty)"
        CLEANED_LOGS=true
    else
        if confirm "Remove log files older than 7 days?" "y"; then
            local count
            count=$(find "$logs_dir" -type f -name "*.log" -mtime +7 | wc -l | tr -d '[:space:]')
            find "$logs_dir" -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true
            success "Removed $count log file(s) older than 7 days"
            CLEANED_LOGS=true
        else
            warn "Skipped log cleanup"
        fi
    fi
}

cleanup_cache() {
    log "Cleaning up Python cache files..."

    find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.tmp" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.log.tmp" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name ".DS_Store" -delete 2>/dev/null || true

    success "Python cache files cleaned"
    CLEANED_CACHE=true
}

stop_services() {
    log "Checking for running services..."

    if pgrep -f "api_services.py" > /dev/null 2>&1; then
        if confirm "Stop API service (api_services.py)?" "y"; then
            pkill -f "api_services.py" || true
            sleep 2
            success "API service stopped"
        fi
    fi

    if pgrep -f "pipeline.sh" > /dev/null 2>&1; then
        if confirm "Stop pipeline processes?" "y"; then
            pkill -f "pipeline.sh" || true
            sleep 1
            success "Pipeline processes stopped"
        fi
    fi
}

print_summary() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║                   CLEANUP SUMMARY                     ║"
    echo "╚════════════════════════════════════════════════════════╝"

    if [ "$CLEANED_DB" = true ]; then
        echo -e "  ${GREEN}✓${NC} Database tables truncated ($DB_NAME)"
    fi

    if [ ${#CLEANED_DIRS[@]} -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} Directories removed:"
        for d in "${CLEANED_DIRS[@]}"; do
            echo "       - $d"
        done
    fi

    if [ "$CLEANED_LOGS" = true ]; then
        echo -e "  ${GREEN}✓${NC} Log files cleaned"
    fi

    if [ "$CLEANED_CACHE" = true ]; then
        echo -e "  ${GREEN}✓${NC} Python cache cleaned"
    fi

    echo ""
    echo "Next steps:"
    echo "  1. Run utils/build_db.sh to recreate database schema and directories"
    echo "  2. Start API service: ./start_api.sh"
    echo "  3. Run training pipeline if needed"
    echo ""
}

################################################################################
# Main Function (interactive)
################################################################################

main() {
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║        ANOMALY DETECTION SYSTEM CLEANUP                ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""

    if [ "$FORCE" = true ]; then
        warn "Running in non-interactive (--force) mode — all sections will be cleaned"
    else
        warn "This will clean up your anomaly detection system."
        warn "Some actions are destructive and cannot be undone."
    fi
    echo ""

    if ! confirm "Continue with cleanup?" "n"; then
        log "Cleanup cancelled"
        exit 0
    fi

    echo ""

    stop_services
    echo ""

    cleanup_cache
    echo ""

    cleanup_logs
    echo ""

    cleanup_directories
    echo ""

    cleanup_database
    echo ""

    print_summary
}

################################################################################
# Argument Parsing
################################################################################

show_help() {
    cat << EOF
Usage: $0 [options]

Options:
  --force, --all  Non-interactive: clean everything without prompting
  --dirs          Clean output/results directories (interactive unless --force)
  --db            Clean database tables (interactive unless --force)
  --cache         Clean Python cache files
  --logs          Clean log files (interactive unless --force)
  --help          Show this help message

Environment Variables (override config.yaml values):
  DB_HOST         Database host     (config default: localhost)
  DB_PORT         Database port     (config default: 5432)
  DB_NAME         Database name     (config default: anomaly_detection)
  DB_USER         Database user     (config default: anomaly_user)
  DB_PASSWORD     Database password (config default: read from config.yaml)

Database credentials are read from:
  config/config.yaml  ->  database.connection.{host,port,database,user,password}

Tables truncated by --db (operational data only):
  anomalies, jobs, background_jobs, agent_messages, agent_activities,
  anomaly_analysis, system_status, model_states, processed_data

Tables NOT touched (configuration data):
  models, processors, collectors

Examples:
  $0                        # Fully interactive cleanup
  $0 --force                # Clean everything without prompting
  $0 --db                   # Database only, interactive
  $0 --db --force           # Database only, non-interactive
  $0 --dirs --cache         # Directories + cache, interactive

EOF
}

# Flags
FORCE=false
CLEAN_DIRS=false
CLEAN_DB=false
CLEAN_CACHE=false
CLEAN_LOGS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force|--all)
            FORCE=true
            shift
            ;;
        --dirs)
            CLEAN_DIRS=true
            shift
            ;;
        --db)
            CLEAN_DB=true
            shift
            ;;
        --cache)
            CLEAN_CACHE=true
            shift
            ;;
        --logs)
            CLEAN_LOGS=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# If --force with no section flags, treat as "clean everything"
SPECIFIC_SECTIONS=false
if [ "$CLEAN_DIRS" = true ] || [ "$CLEAN_DB" = true ] || [ "$CLEAN_CACHE" = true ] || [ "$CLEAN_LOGS" = true ]; then
    SPECIFIC_SECTIONS=true
fi

if [ "$SPECIFIC_SECTIONS" = true ]; then
    # Run only the requested sections
    if [ "$FORCE" = true ]; then
        warn "Non-interactive mode: cleaning selected sections without prompting"
    fi
    [ "$CLEAN_CACHE" = true ] && { cleanup_cache; echo ""; }
    [ "$CLEAN_LOGS" = true ] && { cleanup_logs; echo ""; }
    [ "$CLEAN_DIRS" = true ] && { cleanup_directories; echo ""; }
    [ "$CLEAN_DB" = true ] && { cleanup_database; echo ""; }
    print_summary
else
    # Full cleanup (interactive or forced)
    main
fi
