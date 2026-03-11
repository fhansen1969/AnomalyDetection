#!/bin/bash
# Start the API server

cd "$(dirname "$0")"

echo "Starting Anomaly Detection API Server..."
echo "Config: config/config.yaml"
echo "Host: 127.0.0.1"
echo "Port: 8000"
echo ""

python3 api_services.py \
    --config config/config.yaml \
    --host 127.0.0.1 \
    --port 8000 \
    --auto-init \
    --verbose


