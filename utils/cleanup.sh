#!/usr/bin/env bash
################################################################################
# Cleanup Script - Reset System for Fresh Start
# Includes database cleanup and directory structure reset
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

# Database configuration (read from config or use defaults)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-anomaly_detection}"
DB_USER="${DB_USER:-anomaly_user}"
DB_PASSWORD="${DB_PASSWORD:-}"

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

confirm() {
    local prompt="$1"
    local default="${2:-n}"
    
    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n]"
    else
        prompt="$prompt [y/N]"
    fi
    
    read -p "$prompt " response
    response=${response:-$default}
    
    case "$response" in
        [Yy]* ) return 0 ;;
        [Nn]* ) return 1 ;;
        * ) return 1 ;;
    esac
}

################################################################################
# Cleanup Functions
################################################################################

cleanup_directories() {
    log "Cleaning up directories..."
    
    local dirs_to_clean=(
        "data/processed"
        "data/training"
        "data/validation"
        "data/test"
        "storage/models"
        "storage/anomalies"
        "storage/processed"
        "storage/state"
        "storage/backups"
        "logs"
        "reports"
    )
    
    for dir in "${dirs_to_clean[@]}"; do
        if [ -d "$PROJECT_ROOT/$dir" ]; then
            if confirm "Remove $dir?" "n"; then
                rm -rf "$PROJECT_ROOT/$dir"
                success "Removed $dir"
            else
                warn "Skipped $dir"
            fi
        fi
    done
}

cleanup_database() {
    log "Cleaning up database..."
    
    # Check if PostgreSQL is available
    if ! command -v psql &> /dev/null; then
        warn "PostgreSQL client (psql) not found, skipping database cleanup"
        return 0
    fi
    
    # Determine postgres superuser (try common options)
    local PG_SUPERUSER="postgres"
    if ! psql -U postgres -d postgres -c "SELECT 1" &> /dev/null; then
        # Try current user
        PG_SUPERUSER=$(whoami)
        if ! psql -U "$PG_SUPERUSER" -d postgres -c "SELECT 1" &> /dev/null; then
            warn "Cannot connect to PostgreSQL as superuser, trying as $DB_USER"
            PG_SUPERUSER="$DB_USER"
        fi
    fi
    
    log "Using PostgreSQL superuser: $PG_SUPERUSER"
    
    # Check if database exists
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" -d postgres -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        if confirm "Drop and recreate database $DB_NAME?" "n"; then
            log "Dropping database $DB_NAME..."
            
            # Terminate existing connections
            psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" -d postgres << EOF 2>/dev/null || true
SELECT pg_terminate_backend(pg_stat_activity.pid) 
FROM pg_stat_activity 
WHERE pg_stat_activity.datname = '$DB_NAME' 
  AND pid <> pg_backend_pid();
EOF
            
            # Small delay to ensure connections are closed
            sleep 1
            
            # Drop database using superuser
            if psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null; then
                success "Database dropped"
            else
                error "Failed to drop database. Trying with dropdb command..."
                dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" "$DB_NAME" 2>/dev/null || {
                    error "Failed to drop database with both methods"
                    warn "Try manually: sudo -u postgres psql -c 'DROP DATABASE $DB_NAME;'"
                    return 1
                }
                success "Database dropped"
            fi
        else
            if confirm "Clear all tables instead?" "n"; then
                clear_database_tables
            else
                warn "Skipped database cleanup"
            fi
        fi
    else
        log "Database $DB_NAME does not exist"
    fi
}

clear_database_tables() {
    log "Clearing database tables..."
    
    if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" &> /dev/null; then
        error "Cannot connect to database $DB_NAME as $DB_USER"
        return 1
    fi
    
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
-- Clear data from all tables
TRUNCATE TABLE anomalies CASCADE;
TRUNCATE TABLE jobs CASCADE;
TRUNCATE TABLE processed_data CASCADE;
TRUNCATE TABLE agent_activities CASCADE;
TRUNCATE TABLE agent_messages CASCADE;

SELECT 'All tables cleared successfully' as status;
EOF
    
    if [ $? -eq 0 ]; then
        success "Database tables cleared"
    else
        error "Failed to clear database tables"
        return 1
    fi
}

cleanup_cache() {
    log "Cleaning up cache files..."
    
    # Python cache
    find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true
    
    # Temporary files
    find "$PROJECT_ROOT" -type f -name "*.tmp" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.log.tmp" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name ".DS_Store" -delete 2>/dev/null || true
    
    success "Cache files cleaned"
}

cleanup_logs() {
    log "Cleaning up old log files..."
    
    if [ -d "$PROJECT_ROOT/logs" ]; then
        if confirm "Remove all log files?" "n"; then
            rm -rf "$PROJECT_ROOT/logs"
            success "Log files removed"
        else
            # Keep only recent logs
            if confirm "Remove logs older than 7 days?" "y"; then
                find "$PROJECT_ROOT/logs" -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true
                success "Old log files removed"
            fi
        fi
    fi
}

stop_services() {
    log "Stopping running services..."
    
    # Stop API service
    if pgrep -f "api_services.py" > /dev/null; then
        if confirm "Stop API service?" "y"; then
            pkill -f "api_services.py" || true
            sleep 2
            success "API service stopped"
        fi
    fi
    
    # Stop any pipeline processes
    if pgrep -f "pipeline.sh" > /dev/null; then
        if confirm "Stop pipeline processes?" "y"; then
            pkill -f "pipeline.sh" || true
            sleep 1
            success "Pipeline processes stopped"
        fi
    fi
}

################################################################################
# Main Function
################################################################################

main() {
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║        ANOMALY DETECTION SYSTEM CLEANUP                ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    
    cd "$PROJECT_ROOT"
    
    warn "This will clean up your anomaly detection system"
    warn "This action may be destructive!"
    echo ""
    
    if ! confirm "Continue with cleanup?" "n"; then
        log "Cleanup cancelled"
        exit 0
    fi
    
    echo ""
    
    # Execute cleanup steps
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
    
    success "Cleanup completed!"
    echo ""
    echo "Next steps:"
    echo "  1. Run build_db.sh to recreate database and directories"
    echo "  2. Start API service"
    echo "  3. Run training pipeline"
}

################################################################################
# Argument Parsing
################################################################################

show_help() {
    cat << EOF
Usage: $0 [options]

Options:
  --all           Clean everything without prompting
  --dirs          Clean only directories
  --db            Clean only database
  --cache         Clean only cache files
  --logs          Clean only log files
  --help          Show this help message

Environment Variables:
  DB_HOST         Database host (default: localhost)
  DB_PORT         Database port (default: 5432)
  DB_NAME         Database name (default: anomaly_detection)
  DB_USER         Database user (default: anomaly_user)

Examples:
  $0                    # Interactive cleanup
  $0 --all              # Clean everything
  $0 --dirs --cache     # Clean directories and cache only

EOF
}

# Default: interactive mode
CLEAN_ALL=false
CLEAN_DIRS=false
CLEAN_DB=false
CLEAN_CACHE=false
CLEAN_LOGS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            CLEAN_ALL=true
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
        --help)
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

# If specific flags set, run only those
if [ "$CLEAN_DIRS" = true ] || [ "$CLEAN_DB" = true ] || [ "$CLEAN_CACHE" = true ] || [ "$CLEAN_LOGS" = true ]; then
    [ "$CLEAN_DIRS" = true ] && cleanup_directories
    [ "$CLEAN_DB" = true ] && cleanup_database
    [ "$CLEAN_CACHE" = true ] && cleanup_cache
    [ "$CLEAN_LOGS" = true ] && cleanup_logs
else
    # Run main interactive cleanup
    main
fi