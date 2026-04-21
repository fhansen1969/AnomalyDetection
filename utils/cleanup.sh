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
# Read SQLite database path from config/config.yaml (database.path or database.file_path)
# ---------------------------------------------------------------------------
parse_yaml_value() {
    local file="$1" key="$2"
    grep -A 10 "^database:" "$file" 2>/dev/null \
        | grep "^[[:space:]]*${key}:" \
        | head -1 \
        | sed "s/.*${key}:[[:space:]]*//" \
        | sed "s/['\"]//g" \
        | tr -d '[:space:]'
}

if [ -f "$CONFIG_FILE" ]; then
    _db_path=$(parse_yaml_value "$CONFIG_FILE" "path")
    [ -z "$_db_path" ] && _db_path=$(parse_yaml_value "$CONFIG_FILE" "file_path")
fi
DB_PATH="${DB_PATH:-${_db_path:-storage/anomaly_detection.db}}"
# Resolve relative paths against the project root
if [[ "$DB_PATH" != /* ]]; then
    DB_PATH="$PROJECT_ROOT/$DB_PATH"
fi

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

# Run a sqlite3 command against the configured database file.
run_sqlite() {
    sqlite3 "$DB_PATH" "$@"
}

# Check whether the SQLite database file exists and is readable.
can_connect() {
    if [ ! -f "$DB_PATH" ]; then
        echo "Database file not found: $DB_PATH" >&2
        return 1
    fi
    sqlite3 "$DB_PATH" "SELECT 1;" > /dev/null 2>&1
}

################################################################################
# Cleanup Functions
################################################################################

cleanup_database() {
    log "Database cleanup: $DB_PATH"

    if ! command -v sqlite3 &> /dev/null; then
        warn "sqlite3 not found — skipping database cleanup"
        return 0
    fi

    if ! can_connect; then
        error "Cannot open database: $DB_PATH"
        error "Run the application once to create the database, or check DB_PATH."
        return 1
    fi

    echo ""
    echo "  Tables that will be cleared (data deleted, schema kept):"
    for t in "${TRUNCATE_TABLES[@]}"; do
        echo "    - $t"
    done
    echo "  Tables NOT touched (configuration): models, processors, collectors"
    echo ""

    if ! confirm "Clear all operational tables in '$DB_PATH'?" "n"; then
        warn "Skipped database cleanup"
        return 0
    fi

    log "Clearing tables..."

    # SQLite: use DELETE instead of TRUNCATE; wrap in a transaction.
    local sql="PRAGMA foreign_keys=OFF;"$'\n'"BEGIN;"$'\n'
    for table in "${TRUNCATE_TABLES[@]}"; do
        sql+="DELETE FROM ${table};"$'\n'
    done
    # Seed system_status so the dashboard doesn't fail on startup
    sql+="INSERT OR REPLACE INTO system_status (key, value, updated_at)"$'\n'
    sql+="VALUES ('status', '{\"initialized\": true}', datetime('now'));"$'\n'
    sql+="COMMIT;"$'\n'"PRAGMA foreign_keys=ON;"$'\n'

    if echo "$sql" | run_sqlite 2>&1; then
        success "Database tables cleared successfully"
        CLEANED_DB=true

        log "Row counts after cleanup:"
        for table in "${TRUNCATE_TABLES[@]}"; do
            local count
            count=$(run_sqlite "SELECT COUNT(*) FROM ${table};" 2>/dev/null) || count="?"
            echo "    ${table}: ${count} rows"
        done
    else
        error "Failed to clear database tables"
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
        echo -e "  ${GREEN}✓${NC} Database tables cleared ($DB_PATH)"
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

Environment Variables:
  DB_PATH         Override the SQLite database file path

SQLite database path is read from:
  config/config.yaml  ->  database.path  (override with DB_PATH env var)

Tables cleared by --db (operational data only):
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
