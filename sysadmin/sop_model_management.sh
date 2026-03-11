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