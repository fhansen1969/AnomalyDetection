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
    if PGPASSWORD="St@rW@rs!" psql -h localhost -U anomaly_user -d anomaly_detection -c "SELECT version();" 2>&1 | head -1; then
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