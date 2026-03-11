#!/bin/bash

# System Status Script for Anomaly Detection System
# This script displays the current status of files, directories, and database tables
# Reads configuration from config.yaml
# Shows comprehensive system state information

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() { echo -e "${GREEN}$1${NC}"; }
print_warning() { echo -e "${YELLOW}$1${NC}"; }
print_error() { echo -e "${RED}$1${NC}"; }
print_info() { echo -e "${BLUE}$1${NC}"; }
print_header() { echo -e "${CYAN}$1${NC}"; }
print_subheader() { echo -e "${MAGENTA}$1${NC}"; }

# Function to parse YAML and extract database config
parse_yaml() {
    local yaml_file="config/config.yaml"
    
    # Check if config file exists
    if [ ! -f "$yaml_file" ]; then
        print_error "✗ config.yaml not found at $yaml_file"
        print_info "Please run this script from the project root directory"
        exit 1
    fi
    
    # Extract database configuration using grep and sed
    HOST=$(grep -A10 "^database:" "$yaml_file" | grep "host:" | sed 's/.*host: *//' | tr -d '"' | tr -d "'")
    PORT=$(grep -A10 "^database:" "$yaml_file" | grep "port:" | sed 's/.*port: *//' | tr -d '"' | tr -d "'")
    DATABASE=$(grep -A10 "^database:" "$yaml_file" | grep "database:" | grep -v "^database:" | sed 's/.*database: *//' | tr -d '"' | tr -d "'")
    USER=$(grep -A10 "^database:" "$yaml_file" | grep "user:" | sed 's/.*user: *//' | tr -d '"' | tr -d "'")
    PASSWORD=$(grep -A10 "^database:" "$yaml_file" | grep "password:" | sed 's/.*password: *//' | tr -d '"' | tr -d "'")
    
    # Extract storage type
    STORAGE_TYPE=$(grep -A2 "^database:" "$yaml_file" | grep "type:" | sed 's/.*type: *//' | tr -d '"' | tr -d "'")
    
    # Extract output directory
    OUTPUT_DIR=$(grep -A2 "^system:" "$yaml_file" | grep "output_dir:" | sed 's/.*output_dir: *//' | tr -d '"' | tr -d "'")
    
    # Set defaults if not found
    HOST=${HOST:-localhost}
    PORT=${PORT:-5432}
    DATABASE=${DATABASE:-anomaly_detection}
    USER=${USER:-anomaly_user}
    PASSWORD=${PASSWORD:-}
    STORAGE_TYPE=${STORAGE_TYPE:-postgresql}
    OUTPUT_DIR=${OUTPUT_DIR:-results}
}

# Function to get directory size
get_dir_size() {
    local dir=$1
    if [ -d "$dir" ]; then
        du -sh "$dir" 2>/dev/null | cut -f1
    else
        echo "0"
    fi
}

# Function to count items in directory
count_items() {
    local dir=$1
    if [ -d "$dir" ]; then
        find "$dir" -mindepth 1 2>/dev/null | wc -l | tr -d ' '
    else
        echo "0"
    fi
}

# Function to count files of specific type
count_files_by_type() {
    local dir=$1
    local pattern=$2
    if [ -d "$dir" ]; then
        find "$dir" -name "$pattern" -type f 2>/dev/null | wc -l | tr -d ' '
    else
        echo "0"
    fi
}

# Function to display system info
show_system_info() {
    print_header "╔════════════════════════════════════════════════════════════════════╗"
    print_header "║                    SYSTEM INFORMATION                              ║"
    print_header "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Hostname: $(hostname)"
    echo "User: $(whoami)"
    echo "Working Directory: $(pwd)"
    echo ""
    
    echo "Configuration:"
    echo "  • Storage Type: $STORAGE_TYPE"
    echo "  • Output Directory: $OUTPUT_DIR"
    if [ "$STORAGE_TYPE" = "postgresql" ]; then
        echo "  • Database: $DATABASE"
        echo "  • Database Host: $HOST:$PORT"
        echo "  • Database User: $USER"
    fi
    echo ""
}

# Function to show file system status
show_filesystem_status() {
    print_header "╔════════════════════════════════════════════════════════════════════╗"
    print_header "║                    FILE SYSTEM STATUS                              ║"
    print_header "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Storage directories
    print_subheader "Storage Directories:"
    echo ""
    
    local dirs=("storage/anomalies" "storage/models" "storage/processed" "storage/state")
    
    for dir in "${dirs[@]}"; do
        if [ -d "$dir" ]; then
            local total_items=$(count_items "$dir")
            local total_size=$(get_dir_size "$dir")
            local files=$(find "$dir" -type f 2>/dev/null | wc -l | tr -d ' ')
            local subdirs=$(find "$dir" -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
            
            printf "  %-25s: %5s items (%3s files, %3s dirs) | Size: %s\n" \
                "$dir" "$total_items" "$files" "$subdirs" "$total_size"
        else
            printf "  %-25s: %s\n" "$dir" "$(print_warning 'MISSING')"
        fi
    done
    
    echo ""
    
    # Model files breakdown
    if [ -d "storage/models" ]; then
        print_subheader "Model Files Breakdown:"
        echo ""
        
        local pkl_count=$(count_files_by_type "storage/models" "*.pkl")
        local joblib_count=$(count_files_by_type "storage/models" "*.joblib")
        local h5_count=$(count_files_by_type "storage/models" "*.h5")
        local pt_count=$(count_files_by_type "storage/models" "*.pt")
        local pth_count=$(count_files_by_type "storage/models" "*.pth")
        local json_count=$(count_files_by_type "storage/models" "*.json")
        
        printf "  %-20s: %s\n" "Pickle (.pkl)" "$pkl_count"
        printf "  %-20s: %s\n" "Joblib (.joblib)" "$joblib_count"
        printf "  %-20s: %s\n" "Keras/TF (.h5)" "$h5_count"
        printf "  %-20s: %s\n" "PyTorch (.pt)" "$pt_count"
        printf "  %-20s: %s\n" "PyTorch (.pth)" "$pth_count"
        printf "  %-20s: %s\n" "Metadata (.json)" "$json_count"
        echo ""
    fi
    
    # Other directories
    print_subheader "Other Directories:"
    echo ""
    
    local other_dirs=("$OUTPUT_DIR" "data/input" "logs" "tmp" "backups")
    
    for dir in "${other_dirs[@]}"; do
        if [ -d "$dir" ]; then
            local total_items=$(count_items "$dir")
            local total_size=$(get_dir_size "$dir")
            local files=$(find "$dir" -type f 2>/dev/null | wc -l | tr -d ' ')
            
            printf "  %-25s: %5s items (%3s files) | Size: %s\n" \
                "$dir" "$total_items" "$files" "$total_size"
        else
            printf "  %-25s: %s\n" "$dir" "$(print_info 'not present')"
        fi
    done
    
    echo ""
    
    # Cache files
    print_subheader "Python Cache:"
    echo ""
    
    local pycache_dirs=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
    local pyc_files=$(find . -name "*.pyc" 2>/dev/null | wc -l | tr -d ' ')
    local pyo_files=$(find . -name "*.pyo" 2>/dev/null | wc -l | tr -d ' ')
    
    printf "  %-25s: %s\n" "__pycache__ directories" "$pycache_dirs"
    printf "  %-25s: %s\n" ".pyc files" "$pyc_files"
    printf "  %-25s: %s\n" ".pyo files" "$pyo_files"
    
    echo ""
}

# Function to show database status
show_database_status() {
    if [ "$STORAGE_TYPE" != "postgresql" ]; then
        print_warning "Storage type is not PostgreSQL, skipping database status"
        return
    fi
    
    print_header "╔════════════════════════════════════════════════════════════════════╗"
    print_header "║                    DATABASE STATUS                                 ║"
    print_header "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Test database connection
    export PGPASSWORD="$PASSWORD"
    
    if ! psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -c "SELECT 1;" &> /dev/null; then
        print_error "✗ Cannot connect to database"
        print_info "Host: $HOST:$PORT, Database: $DATABASE, User: $USER"
        echo ""
        return 1
    fi
    
    print_success "✓ Database connection successful"
    echo ""
    
    # Get table row counts
    print_subheader "Table Row Counts:"
    echo ""
    
    psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t << 'EOF'
SELECT 
    RPAD(table_name, 30) || ': ' || 
    LPAD(row_count::text, 10) || ' rows' as status
FROM (
    SELECT 'anomalies' as table_name, COUNT(*) as row_count, 1 as sort_order FROM anomalies
    UNION ALL
    SELECT 'agent_messages', COUNT(*), 2 FROM agent_messages
    UNION ALL
    SELECT 'agent_activities', COUNT(*), 3 FROM agent_activities
    UNION ALL
    SELECT 'anomaly_analysis', COUNT(*), 4 FROM anomaly_analysis
    UNION ALL
    SELECT 'jobs', COUNT(*), 5 FROM jobs
    UNION ALL
    SELECT 'background_jobs', COUNT(*), 6 FROM background_jobs
    UNION ALL
    SELECT 'processed_data', COUNT(*), 7 FROM processed_data
    UNION ALL
    SELECT 'models', COUNT(*), 8 FROM models
    UNION ALL
    SELECT 'model_states', COUNT(*), 9 FROM model_states
    UNION ALL
    SELECT 'processors', COUNT(*), 10 FROM processors
    UNION ALL
    SELECT 'collectors', COUNT(*), 11 FROM collectors
    UNION ALL
    SELECT 'vector_embeddings', COUNT(*), 12 FROM vector_embeddings
    UNION ALL
    SELECT 'system_status', COUNT(*), 13 FROM system_status
) AS counts
ORDER BY sort_order;
EOF

    echo ""
    
    # Model status
    print_subheader "Model Status:"
    echo ""
    
    psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t << 'EOF'
SELECT 
    RPAD(name, 30) || ': ' || RPAD(status, 15) || ' [' || type || ']' as model_info
FROM models
ORDER BY name;
EOF

    echo ""
    
    # Processor status
    print_subheader "Processor Status:"
    echo ""
    
    psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t << 'EOF'
SELECT 
    RPAD(name, 30) || ': ' || status as processor_info
FROM processors
ORDER BY name;
EOF

    echo ""
    
    # Collector status
    print_subheader "Collector Status:"
    echo ""
    
    psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t << 'EOF'
SELECT 
    RPAD(name, 30) || ': ' || status as collector_info
FROM collectors
ORDER BY name;
EOF

    echo ""
    
    # Database size
    print_subheader "Database Size Information:"
    echo ""
    
    psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" << EOF
SELECT 
    pg_size_pretty(pg_database_size('$DATABASE')) as "Database Size";

SELECT 
    schemaname as "Schema",
    tablename as "Table",
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as "Total Size",
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as "Table Size",
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as "Indexes Size"
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
EOF

    echo ""
}

# Function to show summary statistics
show_summary() {
    print_header "╔════════════════════════════════════════════════════════════════════╗"
    print_header "║                    SUMMARY STATISTICS                              ║"
    print_header "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # File system totals
    local total_anomaly_files=$(count_items "storage/anomalies")
    local total_model_files=$(count_items "storage/models")
    local total_processed_files=$(count_items "storage/processed")
    local total_state_files=$(count_items "storage/state")
    local total_output_files=$(count_items "$OUTPUT_DIR")
    local total_log_files=$(count_items "logs")
    
    local total_storage_items=$((total_anomaly_files + total_model_files + total_processed_files + total_state_files))
    
    echo "File System:"
    printf "  %-35s: %s\n" "Total storage items" "$total_storage_items"
    printf "  %-35s: %s\n" "Total output files" "$total_output_files"
    printf "  %-35s: %s\n" "Total log files" "$total_log_files"
    
    # Total storage size
    local storage_size=$(get_dir_size "storage")
    printf "  %-35s: %s\n" "Total storage directory size" "$storage_size"
    echo ""
    
    # Database totals (if available)
    if [ "$STORAGE_TYPE" = "postgresql" ]; then
        export PGPASSWORD="$PASSWORD"
        
        if psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -c "SELECT 1;" &> /dev/null 2>&1; then
            echo "Database:"
            
            local total_anomalies=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT COUNT(*) FROM anomalies;" 2>/dev/null | tr -d ' ')
            local total_jobs=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT COUNT(*) FROM jobs;" 2>/dev/null | tr -d ' ')
            local total_messages=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT COUNT(*) FROM agent_messages;" 2>/dev/null | tr -d ' ')
            local total_models=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT COUNT(*) FROM models;" 2>/dev/null | tr -d ' ')
            local trained_models=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT COUNT(*) FROM models WHERE status = 'trained';" 2>/dev/null | tr -d ' ')
            local active_processors=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT COUNT(*) FROM processors WHERE status = 'active';" 2>/dev/null | tr -d ' ')
            local active_collectors=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT COUNT(*) FROM collectors WHERE status = 'active';" 2>/dev/null | tr -d ' ')
            
            printf "  %-35s: %s\n" "Total anomalies" "$total_anomalies"
            printf "  %-35s: %s\n" "Total jobs" "$total_jobs"
            printf "  %-35s: %s\n" "Total agent messages" "$total_messages"
            printf "  %-35s: %s / %s\n" "Models (trained/total)" "$trained_models" "$total_models"
            printf "  %-35s: %s\n" "Active processors" "$active_processors"
            printf "  %-35s: %s\n" "Active collectors" "$active_collectors"
            echo ""
        fi
    fi
}

# Function to show health status
show_health_status() {
    print_header "╔════════════════════════════════════════════════════════════════════╗"
    print_header "║                    HEALTH STATUS                                   ║"
    print_header "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    local issues=0
    
    # Check config file
    if [ -f "config/config.yaml" ]; then
        print_success "✓ config.yaml exists"
    else
        print_error "✗ config.yaml missing"
        ((issues++))
    fi
    
    # Check critical directories
    local critical_dirs=("storage" "storage/models" "storage/anomalies")
    for dir in "${critical_dirs[@]}"; do
        if [ -d "$dir" ]; then
            print_success "✓ $dir exists"
        else
            print_error "✗ $dir missing"
            ((issues++))
        fi
    done
    
    # Check database connection
    if [ "$STORAGE_TYPE" = "postgresql" ]; then
        export PGPASSWORD="$PASSWORD"
        if psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -c "SELECT 1;" &> /dev/null 2>&1; then
            print_success "✓ Database connection OK"
        else
            print_error "✗ Database connection failed"
            ((issues++))
        fi
    fi
    
    # Check for trained models
    if [ -d "storage/models" ]; then
        local model_files=$(find storage/models -name "*.pkl" -o -name "*.joblib" -o -name "*.h5" 2>/dev/null | wc -l)
        if [ $model_files -gt 0 ]; then
            print_success "✓ Found $model_files trained model file(s)"
        else
            print_warning "⚠ No trained model files found"
        fi
    fi
    
    echo ""
    
    if [ $issues -eq 0 ]; then
        print_success "═══════════════════════════════════════════════════════════════════"
        print_success "   System appears healthy - no critical issues detected"
        print_success "═══════════════════════════════════════════════════════════════════"
    else
        print_warning "═══════════════════════════════════════════════════════════════════"
        print_warning "   $issues critical issue(s) detected - review above"
        print_warning "═══════════════════════════════════════════════════════════════════"
    fi
    
    echo ""
}

# Main execution
clear
echo ""
print_header "╔════════════════════════════════════════════════════════════════════╗"
print_header "║        Anomaly Detection System - Status Report                   ║"
print_header "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Parse configuration
parse_yaml

# Show all status sections
show_system_info
show_filesystem_status
show_database_status
show_summary
show_health_status

# Footer
print_info "Status report generated: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""