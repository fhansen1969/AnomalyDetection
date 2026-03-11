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