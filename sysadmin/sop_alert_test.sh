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