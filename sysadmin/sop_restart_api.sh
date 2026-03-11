#!/bin/bash
# sop_restart_api.sh

echo "Restarting API Service - $(date)"

# Step 1: Save current PID
# Track the current process for clean termination
OLD_PID=""
if [ -f api_service.pid ]; then
    OLD_PID=$(cat api_service.pid)
    # Validate PID: must be numeric and belong to api_services.py
    if [[ "$OLD_PID" =~ ^[0-9]+$ ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        pid_cmd=$(ps -p "$OLD_PID" -o args= 2>/dev/null)
        if echo "$pid_cmd" | grep -q "api_services"; then
            echo "Current PID: $OLD_PID (verified: api_services)"
        else
            echo "WARNING: PID $OLD_PID is not api_services (found: $pid_cmd). Ignoring stale PID file."
            OLD_PID=""
        fi
    else
        echo "WARNING: PID $OLD_PID is not running. Ignoring stale PID file."
        OLD_PID=""
    fi
fi

# Step 2: Stop gracefully
# Give the service time to finish current operations
echo "Stopping API Service..."
if [ -n "$OLD_PID" ]; then
    kill "$OLD_PID" 2>/dev/null
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