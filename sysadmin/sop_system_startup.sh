#!/bin/bash
# sop_system_startup.sh
# Anomaly Detection System Startup Script
# Now reads all configuration from config.yaml

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Anomaly Detection System - $(date)${NC}"

# Function to parse YAML and extract configuration
parse_yaml() {
    local yaml_file="config/config.yaml"
    
    # Check if config file exists
    if [ ! -f "$yaml_file" ]; then
        echo -e "${RED}ERROR: config/config.yaml not found!${NC}"
        exit 1
    fi
    
    # Extract database configuration
    DB_HOST=$(grep -A10 "^database:" "$yaml_file" | grep "host:" | sed 's/.*host: *//' | tr -d '"' | tr -d "'")
    DB_PORT=$(grep -A10 "^database:" "$yaml_file" | grep "port:" | sed 's/.*port: *//' | tr -d '"' | tr -d "'")
    DB_NAME=$(grep -A10 "^database:" "$yaml_file" | grep "database:" | grep -v "^database:" | sed 's/.*database: *//' | tr -d '"' | tr -d "'")
    DB_USER=$(grep -A10 "^database:" "$yaml_file" | grep "user:" | sed 's/.*user: *//' | tr -d '"' | tr -d "'")
    DB_PASS=$(grep -A10 "^database:" "$yaml_file" | grep "password:" | sed 's/.*password: *//' | tr -d '"' | tr -d "'")
    DB_TYPE=$(grep -A2 "^database:" "$yaml_file" | grep "type:" | sed 's/.*type: *//' | tr -d '"' | tr -d "'")
    
    # Extract Ollama configuration
    OLLAMA_URL=$(grep -A10 "agents:" "$yaml_file" | grep -A10 "llm:" | grep "base_url:" | sed 's/.*base_url: *//' | tr -d '"' | tr -d "'")
    OLLAMA_MODEL=$(grep -A10 "agents:" "$yaml_file" | grep -A10 "llm:" | grep "model:" | sed 's/.*model: *//' | tr -d '"' | tr -d "'")
    
    # Extract system configuration
    LOG_LEVEL=$(grep -A5 "^system:" "$yaml_file" | grep "log_level:" | sed 's/.*log_level: *//' | tr -d '"' | tr -d "'")
    OUTPUT_DIR=$(grep -A5 "^system:" "$yaml_file" | grep "output_dir:" | sed 's/.*output_dir: *//' | tr -d '"' | tr -d "'")
    
    # Set defaults if not found
    DB_HOST=${DB_HOST:-localhost}
    DB_PORT=${DB_PORT:-5432}
    DB_NAME=${DB_NAME:-anomaly_detection}
    DB_USER=${DB_USER:-anomaly_user}
    DB_PASS=${DB_PASS:-St@rW@rs!}
    DB_TYPE=${DB_TYPE:-postgresql}
    OLLAMA_URL=${OLLAMA_URL:-http://localhost:11434}
    OLLAMA_MODEL=${OLLAMA_MODEL:-mistral}
    LOG_LEVEL=${LOG_LEVEL:-INFO}
    OUTPUT_DIR=${OUTPUT_DIR:-results}
    
    # Extract Ollama host and port from URL
    OLLAMA_HOST=$(echo "$OLLAMA_URL" | sed 's|http://||' | sed 's|https://||' | cut -d':' -f1)
    OLLAMA_PORT=$(echo "$OLLAMA_URL" | sed 's|http://||' | sed 's|https://||' | cut -d':' -f2 | cut -d'/' -f1)
    
    echo -e "${GREEN}Loaded configuration from config.yaml${NC}"
    echo -e "  Database: $DB_TYPE on $DB_HOST:$DB_PORT"
    echo -e "  Ollama: $OLLAMA_URL (model: $OLLAMA_MODEL)"
    echo -e "  Log Level: $LOG_LEVEL"
}

# Step 1: Pre-flight checks
echo -e "\n${YELLOW}[1/6] Running pre-flight checks...${NC}"
parse_yaml

# Create necessary directories
mkdir -p logs
mkdir -p "$OUTPUT_DIR"
mkdir -p storage/{anomalies,models,processed,state}
mkdir -p data/input

echo -e "  ${GREEN}✓ Configuration loaded${NC}"
echo -e "  ${GREEN}✓ Directories created${NC}"

# Step 2: Start PostgreSQL (if configured)
if [ "$DB_TYPE" = "postgresql" ]; then
    echo -e "\n${YELLOW}[2/6] Starting PostgreSQL...${NC}"
    if systemctl is-active --quiet postgresql; then
        echo -e "  ${BLUE}PostgreSQL already running${NC}"
    else
        sudo systemctl start postgresql
        sleep 5
    fi
    
    # Verify database connectivity with credentials from config
    if ! PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
        echo -e "  ${RED}ERROR: PostgreSQL started but cannot connect!${NC}"
        echo -e "  ${RED}Connection: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME${NC}"
        echo -e "  ${YELLOW}Check: sudo journalctl -u postgresql${NC}"
        exit 1
    fi
    echo -e "  ${GREEN}✓ PostgreSQL OK${NC}"
else
    echo -e "\n${YELLOW}[2/6] Skipping PostgreSQL (using $DB_TYPE storage)${NC}"
fi

# Step 3: Start Ollama
echo -e "\n${YELLOW}[3/6] Starting Ollama...${NC}"
if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo -e "  ${BLUE}Ollama already running at $OLLAMA_URL${NC}"
else
    # Kill any zombie processes from previous runs
    pkill -f "ollama serve" 2>/dev/null
    sleep 2
    
    # Start fresh with dedicated log file
    OLLAMA_LOG="logs/ollama_$(date +%Y%m%d).log"
    nohup ollama serve > "$OLLAMA_LOG" 2>&1 &
    echo $! > ollama.pid
    echo -e "  ${BLUE}Waiting for Ollama to start...${NC}"
    
    for i in {1..20}; do
        if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
            break
        fi
        if [ $i -eq 20 ]; then
            echo -e "  ${RED}ERROR: Ollama failed to start!${NC}"
            echo -e "  ${YELLOW}Check log: tail -f $OLLAMA_LOG${NC}"
            exit 1
        fi
        sleep 1
    done
fi

# Verify configured model is available
if ! ollama list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
    echo -e "  ${YELLOW}WARNING: $OLLAMA_MODEL model not found, agents won't work!${NC}"
    echo -e "  ${YELLOW}Run: ollama pull $OLLAMA_MODEL${NC}"
else
    echo -e "  ${GREEN}✓ Ollama OK ($OLLAMA_MODEL model available)${NC}"
fi

# Step 4: Clear old API processes
echo -e "\n${YELLOW}[4/6] Clearing old API processes...${NC}"
pkill -f api_services.py 2>/dev/null
sleep 2

# Double check port availability
API_PORT=8000
if lsof -i :$API_PORT >/dev/null 2>&1; then
    echo -e "  ${YELLOW}Force killing process on port $API_PORT...${NC}"
    lsof -t -i :$API_PORT | xargs kill -9 2>/dev/null
    sleep 1
fi
echo -e "  ${GREEN}✓ Port $API_PORT cleared${NC}"

# Step 5: Start API Service
echo -e "\n${YELLOW}[5/6] Starting API Service...${NC}"
LOG_FILE="logs/api_services_$(date +%Y%m%d_%H%M%S).log"

# Set environment variables from config
export LOG_LEVEL="$LOG_LEVEL"
export DB_TYPE="$DB_TYPE"
export DB_HOST="$DB_HOST"
export DB_PORT="$DB_PORT"
export DB_NAME="$DB_NAME"
export DB_USER="$DB_USER"
export DB_PASS="$DB_PASS"

nohup python api_services.py \
    --config config/config.yaml \
    --host 0.0.0.0 \
    --port $API_PORT \
    --auto-init \
    > "$LOG_FILE" 2>&1 &

API_PID=$!
echo $API_PID > api_service.pid
echo -e "  ${BLUE}PID: $API_PID${NC}"
echo -e "  ${BLUE}Log: $LOG_FILE${NC}"

# Wait for API to be ready with health endpoint check
echo -e "  ${BLUE}Waiting for API to start...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:$API_PORT/health >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓ API Service OK${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "  ${RED}ERROR: API failed to start!${NC}"
        echo -e "  ${YELLOW}Check log: tail -f $LOG_FILE${NC}"
        exit 1
    fi
    sleep 1
done

# Step 6: Load models
echo -e "\n${YELLOW}[6/6] Loading models...${NC}"
MODEL_COUNT=$(curl -s http://localhost:$API_PORT/models | jq '. | length' 2>/dev/null || echo "0")
if [ "$MODEL_COUNT" -eq "0" ]; then
    # Load models using the API client
    if [ -f "api_client.py" ]; then
        python api_client.py load-models
        echo -e "  ${GREEN}✓ Models loaded from storage${NC}"
    else
        echo -e "  ${YELLOW}WARNING: api_client.py not found, models not loaded${NC}"
    fi
else
    echo -e "  ${GREEN}✓ $MODEL_COUNT models already loaded${NC}"
fi

# Display startup summary
echo
echo -e "${GREEN}=== STARTUP COMPLETE ===${NC}"
echo -e "${BLUE}Configuration Summary:${NC}"
echo -e "  Config File: config/config.yaml"
echo -e "  Database: $DB_TYPE"
if [ "$DB_TYPE" = "postgresql" ]; then
    echo -e "  Database URL: $DB_HOST:$DB_PORT/$DB_NAME"
fi
echo -e "  Ollama URL: $OLLAMA_URL"
echo -e "  Ollama Model: $OLLAMA_MODEL"
echo -e "  Log Level: $LOG_LEVEL"
echo
echo -e "${BLUE}Service Endpoints:${NC}"
echo -e "  API Service: http://localhost:$API_PORT"
echo -e "  WebSocket: ws://localhost:$API_PORT/ws"
echo -e "  Health Check: http://localhost:$API_PORT/health"
echo
echo -e "${BLUE}Monitoring:${NC}"
echo -e "  API Logs: tail -f $LOG_FILE"
echo -e "  Ollama Logs: tail -f logs/ollama_$(date +%Y%m%d).log"
echo
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Check system status: curl http://localhost:$API_PORT/status"
echo -e "  2. View models: curl http://localhost:$API_PORT/models"
echo -e "  3. Start UI: cd ui_db && streamlit run app.py"