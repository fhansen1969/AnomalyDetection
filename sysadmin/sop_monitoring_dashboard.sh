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