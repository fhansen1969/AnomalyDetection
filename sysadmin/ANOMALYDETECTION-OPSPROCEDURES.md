# Anomaly Detection System - Comprehensive Operational Guide

## Table of Contents

1. [System Overview](#system-overview)
   - [Architecture Components](#architecture-components)
2. [Service Management SOPs](#service-management-sops)
   - [1. System Startup SOP](#1-system-startup-sop)
   - [2. System Shutdown SOP](#2-system-shutdown-sop)
   - [3. API Service Restart SOP](#3-api-service-restart-sop)
   - [4. Database Recovery SOP](#4-database-recovery-sop)
   - [5. Emergency Debug SOP](#5-emergency-debug-sop)
   - [6. Model Management SOP](#6-model-management-sop)
   - [7. Log Management SOP](#7-log-management-sop)
   - [8. Alert Test SOP](#8-alert-test-sop)
   - [9. Performance Check SOP](#9-performance-check-sop)
   - [10. Monitoring Dashboard SOP](#10-monitoring-dashboard-sop)
3. [Pipeline Scripts](#pipeline-scripts)
   - [Test Pipeline](#test-pipeline-testpipelinesh)
   - [Validation Pipeline](#validation-pipeline-validationpipelinesh)
   - [Detection Pipeline](#detection-pipeline-detect_anomaliespipelinesh)
   - [Cleanup Pipeline](#cleanup-pipeline-cleanuppipelinesh)
4. [Quick Reference Commands](#quick-reference-commands)
   - [Service Control](#service-control)
   - [Health Checks](#health-checks)
   - [Model Operations](#model-operations)
   - [Agent Operations](#agent-operations)
   - [Troubleshooting](#troubleshooting)
   - [Database Operations](#database-operations)
5. [On-Call Runbook](#on-call-runbook)
   - [Incident Response Flow](#incident-response-flow)
   - [Common Issues and Solutions](#common-issues-and-solutions)
6. [Maintenance Windows](#maintenance-windows)
   - [Daily Tasks](#daily-tasks-5-minutes)
   - [Weekly Tasks](#weekly-tasks-30-minutes)
   - [Monthly Tasks](#monthly-tasks-2-hours)
   - [Quarterly Tasks](#quarterly-tasks-4-hours)
7. [System Architecture Details](#system-architecture-details)
   - [Data Flow](#data-flow)
   - [Security Considerations](#security-considerations)
   - [Performance Optimization](#performance-optimization)
   - [Monitoring Best Practices](#monitoring-best-practices)

---

## System Overview

The Anomaly Detection System is a sophisticated ML-based platform designed to detect unusual patterns in data streams. It combines multiple machine learning models (Isolation Forest, One-Class SVM, Autoencoders, GANs, Statistical methods) with an AI agent system powered by Large Language Models for intelligent analysis. The system provides real-time anomaly detection, automated analysis, and actionable remediation recommendations.

### Architecture Components

1. **API Service** (`api_services.py`): FastAPI-based REST API server that orchestrates all system operations
2. **PostgreSQL Database**: Stores anomalies, model states, analysis results, and system metadata
3. **Ollama LLM Service**: Runs local LLMs (Mistral) for agent-based anomaly analysis
4. **ML Models**: Six different anomaly detection algorithms that can work individually or in ensemble
5. **AI Agents**: Specialized agents for security analysis, remediation, threat intelligence, and code generation
6. **Data Collectors**: Modular collectors for various data sources (files, Kafka, SQL, REST APIs)
7. **WebSocket Support**: Real-time updates and alerts for connected clients

---

## Service Management SOPs

### 1. System Startup SOP

**Purpose**: Start all services in correct order  
**When**: After reboot, maintenance, or full shutdown

The startup process ensures all dependencies are available before starting dependent services. PostgreSQL must be running before the API service, and Ollama must be available for agent functionality.

```bash
#!/bin/bash
# sop_system_startup.sh

echo "Starting Anomaly Detection System - $(date)"

# Step 1: Pre-flight checks
# Verify critical configuration files exist before attempting startup
echo "[1/6] Running pre-flight checks..."
if [ ! -f config/config.yaml ]; then
    echo "ERROR: config/config.yaml not found!"
    exit 1
fi

# Step 2: Start PostgreSQL
# The database must be running first as it stores all system state
echo "[2/6] Starting PostgreSQL..."
if systemctl is-active --quiet postgresql; then
    echo "  PostgreSQL already running"
else
    sudo systemctl start postgresql
    sleep 5
    # Verify database connectivity with actual credentials
    if ! PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection -c "SELECT 1;" >/dev/null 2>&1; then
        echo "  ERROR: PostgreSQL started but cannot connect!"
        echo "  Check: sudo journalctl -u postgresql"
        exit 1
    fi
fi
echo "  ✓ PostgreSQL OK"

# Step 3: Start Ollama
# Ollama provides the LLM backend for intelligent agent analysis
echo "[3/6] Starting Ollama..."
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "  Ollama already running"
else
    # Kill any zombie processes from previous runs
    pkill -f "ollama serve" 2>/dev/null
    sleep 2
    # Start fresh with dedicated log file
    nohup ollama serve > logs/ollama_$(date +%Y%m%d).log 2>&1 &
    echo $! > ollama.pid
    echo "  Waiting for Ollama to start..."
    for i in {1..20}; do
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
fi

# Verify Mistral model is available for agent operations
if ! ollama list | grep -q mistral; then
    echo "  WARNING: Mistral model not found, agents won't work!"
    echo "  Run: ollama pull mistral"
else
    echo "  ✓ Ollama OK (Mistral model available)"
fi

# Step 4: Clear old API processes
# Ensure no stale processes are holding the port
echo "[4/6] Clearing old API processes..."
pkill -f api_services.py 2>/dev/null
sleep 2
# Double check port availability
if lsof -i :8000 >/dev/null 2>&1; then
    echo "  Force killing process on port 8000..."
    lsof -t -i :8000 | xargs kill -9 2>/dev/null
    sleep 1
fi
echo "  ✓ Port 8000 cleared"

# Step 5: Start API Service
# The main service that handles all anomaly detection operations
echo "[5/6] Starting API Service..."
LOG_FILE="logs/api_services_$(date +%Y%m%d_%H%M%S).log"
nohup python api_services.py \
    --config config/config.yaml \
    --host 0.0.0.0 \
    --port 8000 \
    --auto-init \
    > "$LOG_FILE" 2>&1 &

API_PID=$!
echo $API_PID > api_service.pid
echo "  PID: $API_PID"
echo "  Log: $LOG_FILE"

# Wait for API to be ready with health endpoint check
echo "  Waiting for API to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo "  ✓ API Service OK"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ERROR: API failed to start!"
        echo "  Check log: tail -f $LOG_FILE"
        exit 1
    fi
    sleep 1
done

# Step 6: Load models
# Ensure previously trained models are loaded into memory
echo "[6/6] Loading models..."
MODEL_COUNT=$(curl -s http://localhost:8000/models | jq '. | length' 2>/dev/null || echo "0")
if [ "$MODEL_COUNT" -eq "0" ]; then
    python api_client.py load-models
    echo "  ✓ Models loaded from storage"
else
    echo "  ✓ $MODEL_COUNT models already loaded"
fi

echo
echo "=== STARTUP COMPLETE ==="
echo "API Service: http://localhost:8000"
echo "WebSocket: ws://localhost:8000/ws"
echo "Logs: tail -f $LOG_FILE"
2. System Shutdown SOP
Purpose: Gracefully shut down all services
When: Before maintenance, upgrades
A graceful shutdown ensures no data loss and clean termination of all running jobs. The system checks for active jobs before proceeding with shutdown.
#!/bin/bash
# sop_system_shutdown.sh

echo "Shutting down Anomaly Detection System - $(date)"

# Step 1: Check for active jobs
# Prevent data loss by warning about running jobs
echo "[1/4] Checking active jobs..."
ACTIVE_JOBS=$(curl -s http://localhost:8000/jobs?status=running | jq '. | length' 2>/dev/null || echo "0")
if [ "$ACTIVE_JOBS" -gt "0" ]; then
    echo "  WARNING: $ACTIVE_JOBS jobs still running!"
    echo "  Continue? (y/n)"
    read -n 1 answer
    echo
    if [ "$answer" != "y" ]; then
        exit 1
    fi
fi

# Step 2: Stop API Service
# Gracefully terminate the main service using saved PID
echo "[2/4] Stopping API Service..."
if [ -f api_service.pid ]; then
    PID=$(cat api_service.pid)
    kill $PID 2>/dev/null
    rm api_service.pid
    echo "  Stopped PID $PID"
else
    pkill -f api_services.py
fi
sleep 2

# Verify stopped with force kill if necessary
if pgrep -f api_services.py >/dev/null; then
    echo "  Force stopping API..."
    pkill -9 -f api_services.py
fi
echo "  ✓ API Service stopped"

# Step 3: Stop Ollama
# Terminate the LLM service
echo "[3/4] Stopping Ollama..."
if [ -f ollama.pid ]; then
    kill $(cat ollama.pid) 2>/dev/null
    rm ollama.pid
else
    pkill -f "ollama serve"
fi
echo "  ✓ Ollama stopped"

# Step 4: PostgreSQL (optional)
# Database typically left running for other services
echo "[4/4] PostgreSQL..."
echo "  Leave PostgreSQL running (recommended)"
echo "  To stop: sudo systemctl stop postgresql"

echo
echo "=== SHUTDOWN COMPLETE ==="
3. API Service Restart SOP
Purpose: Restart just the API service
When: After config changes, API hanging
This procedure allows restarting the API service without affecting the database or Ollama services. It's useful for applying configuration changes or recovering from API-specific issues.
#!/bin/bash
# sop_restart_api.sh

echo "Restarting API Service - $(date)"

# Step 1: Save current PID
# Track the current process for clean termination
OLD_PID=""
if [ -f api_service.pid ]; then
    OLD_PID=$(cat api_service.pid)
    echo "Current PID: $OLD_PID"
fi

# Step 2: Stop gracefully
# Give the service time to finish current operations
echo "Stopping API Service..."
if [ -n "$OLD_PID" ]; then
    kill $OLD_PID 2>/dev/null
    sleep 2
fi

# Force stop if needed
if pgrep -f api_services.py >/dev/null; then
    echo "Force stopping..."
    pkill -9 -f api_services.py
    sleep 1
fi

# Step 3: Clear port
# Ensure port 8000 is completely free
if lsof -i :8000 >/dev/null 2>&1; then
    echo "Clearing port 8000..."
    lsof -t -i :8000 | xargs kill -9
    sleep 1
fi

# Step 4: Start fresh
# Launch with new log file for easy troubleshooting
LOG_FILE="logs/api_services_$(date +%Y%m%d_%H%M%S).log"
echo "Starting API Service..."
nohup python api_services.py \
    --config config/config.yaml \
    --host 0.0.0.0 \
    --port 8000 \
    --auto-init \
    > "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo $NEW_PID > api_service.pid

# Step 5: Verify
# Confirm the service is responding to health checks
echo "Waiting for API..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo "✓ API Service restarted successfully"
        echo "  New PID: $NEW_PID"
        echo "  Log: $LOG_FILE"
        exit 0
    fi
    sleep 1
done

echo "ERROR: API failed to restart!"
echo "Check log: tail -f $LOG_FILE"
exit 1
4. Database Recovery SOP
Purpose: Recover from database issues
When: Connection errors, corrupted data
Database recovery is critical when the system cannot connect to PostgreSQL or when permissions are misconfigured. This procedure systematically fixes common database issues.
#!/bin/bash
# sop_database_recovery.sh

echo "Database Recovery Procedure - $(date)"

# Step 1: Stop API Service
# Prevent connection conflicts during recovery
echo "[1/6] Stopping API Service..."
pkill -f api_services.py
sleep 2

# Step 2: Check PostgreSQL status
# Ensure the database service itself is running
echo "[2/6] Checking PostgreSQL..."
if ! systemctl is-active --quiet postgresql; then
    echo "  PostgreSQL is not running, starting..."
    sudo systemctl start postgresql
    sleep 5
fi

# Step 3: Test connection
# Verify we can connect as the PostgreSQL superuser
echo "[3/6] Testing connection..."
if ! sudo -u postgres psql -c "SELECT 1;" >/dev/null 2>&1; then
    echo "  ERROR: Cannot connect as postgres user"
    echo "  Checking PostgreSQL logs..."
    sudo journalctl -u postgresql -n 50
    exit 1
fi

# Step 4: Fix user/permissions
# Recreate user and reset permissions if needed
echo "[4/6] Fixing user permissions..."
sudo -u postgres psql << EOF
-- Ensure user exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'anomaly_user') THEN
        CREATE USER anomaly_user WITH PASSWORD 'XXXXX';
    END IF;
END\$\$;

-- Reset password
ALTER USER anomaly_user WITH PASSWORD 'XXXXX';

-- Ensure database exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'anomaly_detection') THEN
        CREATE DATABASE anomaly_detection OWNER anomaly_user;
    END IF;
END\$\$;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE anomaly_detection TO anomaly_user;
EOF

# Step 5: Test user connection
# Confirm the application user can connect
echo "[5/6] Testing user connection..."
if PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection -c "SELECT 1;" >/dev/null 2>&1; then
    echo "  ✓ Database connection OK"
else
    echo "  ERROR: Still cannot connect!"
    echo "  Check pg_hba.conf:"
    sudo grep -v "^#" /etc/postgresql/*/main/pg_hba.conf | grep -v "^$"
    exit 1
fi

# Step 6: Verify tables
# Check if schema exists and needs rebuilding
echo "[6/6] Verifying tables..."
TABLE_COUNT=$(PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" | xargs)
echo "  Found $TABLE_COUNT tables"

if [ "$TABLE_COUNT" -lt "10" ]; then
    echo "  WARNING: Missing tables, run build_db.sh"
fi

echo
echo "Database recovery complete. Start API with: ./sop_system_startup.sh"
5. Emergency Debug SOP
Purpose: Diagnose why services won't start
When: Services failing to start
This comprehensive diagnostic script checks all system dependencies, configurations, and common failure points. It provides actionable information for troubleshooting startup failures.
#!/bin/bash
# sop_emergency_debug.sh

echo "=== EMERGENCY DEBUG - $(date) ==="

# Kill everything first
# Clean slate for debugging
echo "Killing all services..."
pkill -f api_services.py
pkill -f "ollama serve"
sleep 2

# Check ports
# Identify any port conflicts
echo -e "\n=== PORT CHECK ==="
for port in 5432 8000 11434; do
    echo -n "Port $port: "
    if lsof -i :$port >/dev/null 2>&1; then
        echo "IN USE by:"
        lsof -i :$port | grep LISTEN
    else
        echo "FREE"
    fi
done

# Check disk space
# Ensure adequate space for operations
echo -e "\n=== DISK SPACE ==="
df -h | grep -E "/$|/var|/storage"

# Check Python
# Verify Python environment and dependencies
echo -e "\n=== PYTHON CHECK ==="
python --version
echo "Critical packages:"
for pkg in fastapi uvicorn psycopg2 pyyaml; do
    if python -c "import $pkg" 2>/dev/null; then
        echo "  ✓ $pkg"
    else
        echo "  ✗ $pkg MISSING"
    fi
done

# Check config
# Validate configuration file syntax and content
echo -e "\n=== CONFIG CHECK ==="
if [ -f config/config.yaml ]; then
    echo "config.yaml exists"
    python -c "
import yaml
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)
print(f'  Database: {config.get(\"database\", {}).get(\"type\")}')
print(f'  Models enabled: {config.get(\"models\", {}).get(\"enabled\", [])}')
" 2>&1
else
    echo "ERROR: config/config.yaml NOT FOUND!"
fi

# Test database
# Attempt database connection with diagnostics
echo -e "\n=== DATABASE TEST ==="
if systemctl is-active --quiet postgresql; then
    echo "PostgreSQL is running"
    if PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection -c "SELECT version();" 2>&1 | head -1; then
        echo "✓ Can connect to database"
    else
        echo "✗ CANNOT connect to database"
        echo "Try: ./sop_database_recovery.sh"
    fi
else
    echo "PostgreSQL is NOT running!"
    echo "Start with: sudo systemctl start postgresql"
fi

# Check logs
# Display recent errors for quick diagnosis
echo -e "\n=== RECENT ERRORS ==="
echo "API Service errors:"
grep -i error logs/api_services_*.log 2>/dev/null | tail -5 | sed 's/^/  /'

echo -e "\nOllama errors:"
grep -i error logs/ollama*.log 2>/dev/null | tail -5 | sed 's/^/  /'

# Recommendations
# Provide clear next steps based on findings
echo -e "\n=== RECOMMENDATIONS ==="
echo "1. Run: ./sop_database_recovery.sh"
echo "2. Run: pip install -r requirements.txt"
echo "3. Run: ./sop_system_startup.sh"
6. Model Management SOP
Purpose: Load, verify, and manage ML models
When: After training, monthly verification
Model management ensures all trained models are properly loaded and functional. This is critical after system restarts or when adding new models.
#!/bin/bash
# sop_model_management.sh

echo "Model Management Procedure - $(date)"

# Check API is running
# Models are managed through the API service
if ! curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "ERROR: API Service not running!"
    exit 1
fi

# Step 1: List current models
# Show what's currently loaded in memory
echo "[1/4] Current models in memory:"
curl -s http://localhost:8000/models | jq -r '.[] | "\(.name) - \(.status) (type: \(.type))"'

# Step 2: Check model files
# Verify model files exist on disk
echo -e "\n[2/4] Model files on disk:"
if [ -d storage/models ]; then
    ls -lh storage/models/*.pkl storage/models/*.joblib 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
else
    echo "  No models directory!"
fi

# Step 3: Load models from storage
# Load any saved models not currently in memory
echo -e "\n[3/4] Loading models from storage..."
python api_client.py load-models

# Step 4: Verify loaded models
# Test each model with sample data to ensure functionality
echo -e "\n[4/4] Verifying models:"
MODELS=$(curl -s http://localhost:8000/models | jq -r '.[].name')
for model in $MODELS; do
    echo -n "  Testing $model... "
    # Create test data
    echo '[{"value": 50, "cpu": 80, "memory": 70}]' > /tmp/test_data.json
    
    # Test detection
    if python api_client.py detect-anomalies $model /tmp/test_data.json >/dev/null 2>&1; then
        echo "✓ OK"
    else
        echo "✗ FAILED"
    fi
done
rm -f /tmp/test_data.json

echo -e "\nModel management complete."
7. Log Management SOP
Purpose: Manage and rotate logs
When: Weekly, or when disk space low
Log management prevents disk space issues and maintains system performance by archiving old logs and rotating large files.
#!/bin/bash
# sop_log_management.sh

echo "Log Management Procedure - $(date)"

LOG_DIR="logs"
ARCHIVE_DIR="logs/archive"
DAYS_TO_KEEP=7

# Step 1: Check log sizes
# Identify large log files that need attention
echo "[1/4] Current log sizes:"
du -sh $LOG_DIR/*.log 2>/dev/null | sort -h

# Step 2: Archive old logs
# Compress and move logs older than retention period
echo -e "\n[2/4] Archiving logs older than $DAYS_TO_KEEP days..."
mkdir -p $ARCHIVE_DIR

find $LOG_DIR -name "*.log" -mtime +$DAYS_TO_KEEP -type f | while read logfile; do
    filename=$(basename "$logfile")
    echo "  Archiving $filename..."
    gzip -c "$logfile" > "$ARCHIVE_DIR/${filename}.gz"
    rm "$logfile"
done

# Step 3: Rotate current logs if too large (>100MB)
# Prevent individual logs from growing too large
echo -e "\n[3/4] Checking current log sizes..."
find $LOG_DIR -name "*.log" -size +100M -type f | while read logfile; do
    echo "  Rotating large log: $logfile"
    mv "$logfile" "${logfile}.old"
    
    # If it's the API log, get PID and send HUP signal
    if [[ "$logfile" == *"api_services"* ]] && [ -f api_service.pid ]; then
        kill -HUP $(cat api_service.pid) 2>/dev/null
    fi
done

# Step 4: Clean up old archives (>30 days)
# Remove very old archives to prevent accumulation
echo -e "\n[4/4] Cleaning old archives..."
find $ARCHIVE_DIR -name "*.gz" -mtime +30 -delete

echo -e "\nLog management complete."
echo "Disk usage: $(du -sh $LOG_DIR | cut -f1)"
8. Alert Test SOP
Purpose: Verify alert system is working
When: Weekly, after config changes
Regular alert testing ensures the notification system will work when real anomalies are detected. This tests both the configuration and the delivery mechanisms.
#!/bin/bash
# sop_alert_test.sh

echo "Alert System Test - $(date)"

# Step 1: Check alert configuration
# Display current alert settings for verification
echo "[1/3] Current alert configuration:"
curl -s http://localhost:8000/config | jq '.alerts'

# Step 2: Send test alert
# Trigger a manual test alert through the API
echo -e "\n[2/3] Sending test alert..."
python api_client.py test-alert --type email

# Step 3: Create test anomaly above threshold
# Generate a synthetic high-severity anomaly
echo -e "\n[3/3] Creating high-severity test anomaly..."
cat > /tmp/test_anomaly.json << EOF
[{
    "cpu": 99,
    "memory": 95,
    "network": 50000,
    "errors": 1000,
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}]
EOF

# Detect with low threshold to ensure anomaly is found
JOB_ID=$(python api_client.py detect-anomalies isolation_forest_model /tmp/test_anomaly.json --threshold 0.1 | jq -r '.job_id')

if [ -n "$JOB_ID" ]; then
    echo "  Detection job: $JOB_ID"
    sleep 5
    
    # Check if anomaly was detected and alert triggered
    ANOMALIES=$(python api_client.py list-anomalies --min-score 0.8 --limit 1)
    if [ -n "$ANOMALIES" ]; then
        echo "  ✓ High-severity anomaly detected"
        echo "  Check if alert was triggered"
    else
        echo "  ✗ No high-severity anomaly detected"
    fi
fi

rm -f /tmp/test_anomaly.json
echo -e "\nAlert test complete."
9. Performance Check SOP
Purpose: Monitor system performance
When: Daily or when slowness reported
Performance monitoring helps identify bottlenecks and resource constraints before they impact operations. This checks response times, resource usage, and database performance.
#!/bin/bash
# sop_performance_check.sh

echo "Performance Check - $(date)"

# Step 1: API response time
# Measure average response time for health endpoint
echo "[1/5] API Response Time:"
total=0
count=10
for i in $(seq 1 $count); do
    start=$(date +%s%N)
    curl -s http://localhost:8000/health >/dev/null
    end=$(date +%s%N)
    elapsed=$((($end - $start) / 1000000))
    total=$(($total + $elapsed))
    echo -n "."
done
echo
avg=$(($total / $count))
echo "  Average: ${avg}ms"
if [ $avg -gt 100 ]; then
    echo "  WARNING: Response time high (>100ms)"
fi

# Step 2: Database query performance
# Test basic query response times
echo -e "\n[2/5] Database Performance:"
PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection << EOF
\timing on
SELECT COUNT(*) FROM anomalies;
SELECT COUNT(*) FROM processed_data;
EOF

# Step 3: Memory usage
# Check memory consumption by service
echo -e "\n[3/5] Memory Usage:"
ps aux | grep -E "api_services|postgres|ollama" | grep -v grep | \
    awk '{sum+=$6; print $11 ": " int($6/1024) "MB"} END {print "Total: " int(sum/1024) "MB"}'

# Step 4: CPU usage
# Monitor CPU utilization
echo -e "\n[4/5] CPU Usage:"
top -b -n 1 | grep -E "api_services|postgres|ollama" | grep -v grep | \
    awk '{print $12 ": " $9 "%"}'

# Step 5: Connection count
# Check database connection pool usage
echo -e "\n[5/5] Database Connections:"
PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection -t -c "
SELECT COUNT(*) as connections FROM pg_stat_activity;"

echo -e "\nPerformance check complete."
10. Monitoring Dashboard SOP
Purpose: Set up continuous monitoring
When: For 24/7 operations
This creates a live dashboard in the terminal for real-time system monitoring. It's useful for operations teams to maintain situational awareness.
#!/bin/bash
# sop_monitoring_dashboard.sh

# This runs in a terminal window for live monitoring
while true; do
    clear
    echo "=== ANOMALY DETECTION SYSTEM MONITOR ==="
    echo "Time: $(date)"
    echo "========================================"
    
    # Service Status
    # Real-time health check of all services
    echo -e "\nSERVICE STATUS:"
    echo -n "PostgreSQL:  "
    systemctl is-active postgresql >/dev/null && echo "✓ RUNNING" || echo "✗ DOWN"
    
    echo -n "API Service: "
    curl -s http://localhost:8000/health >/dev/null && echo "✓ RUNNING" || echo "✗ DOWN"
    
    echo -n "Ollama:      "
    curl -s http://localhost:11434/api/tags >/dev/null && echo "✓ RUNNING" || echo "✗ DOWN"
    
    # Recent Activity
    # Show current workload
    echo -e "\nRECENT ACTIVITY:"
    echo "Active Jobs: $(curl -s http://localhost:8000/jobs?status=running 2>/dev/null | jq '. | length' || echo "N/A")"
    echo "Models Loaded: $(curl -s http://localhost:8000/models 2>/dev/null | jq '. | length' || echo "N/A")"
    
    # Recent Anomalies
    # Display latest detected anomalies
    echo -e "\nRECENT ANOMALIES (last hour):"
    ONE_HOUR_AGO=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)
    curl -s http://localhost:8000/anomalies?limit=5 2>/dev/null | \
        jq -r '.[] | select(.created_at > "'$ONE_HOUR_AGO'") | 
        "\(.severity) - Score: \(.score) - \(.model)"' | head -5
    
    # System Resources
    # Monitor resource utilization
    echo -e "\nSYSTEM RESOURCES:"
    echo "CPU Load: $(uptime | awk -F'load average:' '{print $2}')"
    echo "Memory: $(free -h | awk '/^Mem:/ {print $3 " / " $2}')"
    echo "Disk (/): $(df -h / | awk 'NR==2 {print $3 " / " $2 " (" $5 ")"}')"
    
    # Errors
    # Show recent errors for quick response
    echo -e "\nRECENT ERRORS:"
    grep -i error logs/api_services_*.log 2>/dev/null | tail -3 | cut -c1-80
    
    echo -e "\n[Refreshing every 30 seconds - Ctrl+C to exit]"
    sleep 30
done

Pipeline Scripts
Test Pipeline (test_pipeline.sh)
The test pipeline is designed for model development and experimentation. It handles the complete workflow from data ingestion through model training and evaluation. This pipeline is essential for developing new models or improving existing ones.
Key stages:

Data Collection: Validates and ingests test data files
Preprocessing: Normalizes data and handles missing values
Feature Engineering: Extracts relevant features for anomaly detection
Data Splitting: Creates 60/20/20 train/validation/test splits
Model Training: Trains all configured models on the training set
Evaluation: Tests model performance on the test set
Export: Saves trained models for validation

Validation Pipeline (validation_pipeline.sh)
The validation pipeline rigorously tests trained models against holdout datasets to ensure they meet production standards. This prevents poorly performing models from being deployed.
Key features:

Tests models on completely unseen validation data
Calculates comprehensive metrics (precision, recall, F1)
Compares performance against baseline methods
Issues validation certificates for approved models
Generates detailed reports for decision making

Detection Pipeline (detect_anomalies_pipeline.sh)
The production detection pipeline processes real-world data through validated models to identify anomalies. It supports both batch and real-time processing modes.
Key capabilities:

Batch Mode: Processes files from the input directory
Real-time Mode: Continuously monitors data streams
Agent Analysis: Leverages AI agents for intelligent anomaly assessment
Alert Generation: Sends notifications for high-severity anomalies
Continuous Monitoring: Runs indefinitely with automatic data pickup

Cleanup Pipeline (cleanup_pipeline.sh)
The comprehensive cleanup pipeline resets the entire system to a clean state. It's invaluable for development, testing, and recovering from corrupted states.
Operations performed:

File System Cleanup: Removes all generated data, models, and logs
Database Cleanup: Truncates all tables while preserving schema
Database Build: Recreates tables and relationships if needed
Directory Verification: Ensures all required directories exist
Sample Data: Optionally populates test data for development


Quick Reference Commands
Service Control
# Start everything
./sop_system_startup.sh

# Stop everything
./sop_system_shutdown.sh

# Restart API only
./sop_restart_api.sh

# Emergency debug
./sop_emergency_debug.sh
Health Checks
# Quick check
curl http://localhost:8000/health

# Full system status
python api_client.py system-status

# Performance check
./sop_performance_check.sh
Model Operations
# List models
python api_client.py list-models

# Train a model
python api_client.py train-model isolation_forest_model data/train.json

# Load saved models
python api_client.py load-models

# Test detection
python api_client.py detect-anomalies isolation_forest_model data/test.json
Agent Operations
# Check agent status
python api_client.py agents-status

# Analyze anomalies with agents
python api_client.py analyze-with-agents anomalies.json

# Get agent workflow
python api_client.py agent-workflow

# Detailed analysis with dialogue
python api_client.py analyze-detailed anomalies.json --show-dialogue
Troubleshooting
# Check what's using a port
lsof -i :8000

# Kill process on port
lsof -t -i :8000 | xargs kill -9

# View API logs
tail -f logs/api_services_*.log

# Check for errors
grep -i error logs/*.log | tail -20

# Database connection test
PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection -c "SELECT 1;"
Database Operations
# Connect to database
PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection

# Quick query
PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection -c "SELECT COUNT(*) FROM anomalies;"

# Check table sizes
PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

On-Call Runbook
Incident Response Flow
If you get paged:

Initial Assessment (2 minutes)
# Run comprehensive health check
./sop_emergency_debug.sh

Service Recovery (5 minutes)

If API is down: ./sop_restart_api.sh
If database issues: ./sop_database_recovery.sh
If Ollama issues: pkill ollama && ollama serve
If nothing works: Full restart with ./sop_system_startup.sh


Verification (2 minutes)
# Verify all services are operational
curl http://localhost:8000/health
python api_client.py system-status

Monitoring (ongoing)
# Start live monitoring in a separate terminal
./sop_monitoring_dashboard.sh

Root Cause Analysis

Check recent changes: git log --oneline -10
Review error logs: grep -i error logs/*.log | tail -50
Check system resources: htop or top
Database issues: Check PostgreSQL logs



Common Issues and Solutions
API Won't Start

Port conflict: lsof -i :8000 and kill the process
Missing dependencies: pip install -r requirements.txt
Config issues: Validate with python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"

Database Connection Errors

PostgreSQL down: sudo systemctl start postgresql
Authentication failed: Run ./sop_database_recovery.sh
Too many connections: Restart API service

High Memory Usage

Check for memory leaks: Monitor with htop
Restart services if needed
Adjust model batch sizes in config

Slow Performance

Run performance check: ./sop_performance_check.sh
Check database indexes
Review active jobs: python api_client.py list-jobs --status running


Maintenance Windows
Daily Tasks (5 minutes)

Run performance check: ./sop_performance_check.sh
Review monitoring dashboard for anomalies
Check disk space: df -h

Weekly Tasks (30 minutes)

Rotate logs: ./sop_log_management.sh
Test alerts: ./sop_alert_test.sh
Review and archive completed jobs
Update Ollama models if needed: ollama pull mistral

Monthly Tasks (2 hours)

Model verification: ./sop_model_management.sh
Full system backup
Review and update documentation
Performance baseline update
Security updates: sudo apt update && sudo apt upgrade

Quarterly Tasks (4 hours)

Full system test including failover
Review and update runbooks
Capacity planning review
Model retraining if needed


System Architecture Details
Data Flow

Data Ingestion

Collectors gather data from various sources
Data is validated and stored in PostgreSQL
Real-time data triggers immediate processing


Processing Pipeline

Normalizers standardize data formats
Feature extractors prepare data for models
Processed data is cached for efficiency


Anomaly Detection

Multiple models analyze data in parallel
Ensemble methods combine predictions
Scores and thresholds determine anomalies


Agent Analysis

High-severity anomalies trigger agent analysis
Multiple specialized agents collaborate
Consensus mechanisms ensure quality


Alert & Response

Alerts sent based on severity thresholds
WebSocket broadcasts for real-time updates
All results stored for audit trail



Security Considerations

Authentication: Currently relies on network security; add API keys for production
Database: Uses password authentication; consider certificate-based auth
LLM Security: Ollama runs locally to prevent data leakage
Input Validation: All API inputs are validated with Pydantic
Error Handling: Errors logged without exposing sensitive data

Performance Optimization

Database Indexes: Critical fields are indexed for query performance
Batch Processing: Data processed in configurable batch sizes
Connection Pooling: Database connections are pooled and reused
Async Operations: API uses async/await for concurrent operations
Model Caching: Trained models kept in memory for fast inference

Monitoring Best Practices

Set up external monitoring (Prometheus, Grafana)
Configure log aggregation (ELK stack)
Implement custom metrics for business KPIs
Create automated health checks
Set up PagerDuty integration for critical alerts

