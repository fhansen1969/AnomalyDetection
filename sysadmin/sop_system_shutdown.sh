#!/bin/bash
# sop_system_shutdown.sh
# Anomaly Detection System Shutdown Script
# Now reads configuration from config.yaml for proper service management

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Shutting down Anomaly Detection System - $(date)${NC}"

# Function to parse YAML and extract configuration
parse_yaml() {
    local yaml_file="config/config.yaml"
    
    # Check if config file exists
    if [ ! -f "$yaml_file" ]; then
        echo -e "${YELLOW}WARNING: config/config.yaml not found, using defaults${NC}"
        API_PORT=8000
        DB_TYPE="postgresql"
        SAVE_STATE=true
        return
    fi
    
    # Extract database type
    DB_TYPE=$(grep -A2 "^database:" "$yaml_file" | grep "type:" | sed 's/.*type: *//' | tr -d '"' | tr -d "'")
    DB_TYPE=${DB_TYPE:-postgresql}
    
    # Extract API port (if customized)
    API_PORT=8000  # Default, could be extracted from config if added
    
    # Check if state should be saved on shutdown
    SAVE_STATE=$(grep -A5 "^system:" "$yaml_file" | grep "save_state_on_shutdown:" | sed 's/.*save_state_on_shutdown: *//' | tr -d '"' | tr -d "'")
    SAVE_STATE=${SAVE_STATE:-true}
    
    echo -e "${GREEN}Loaded shutdown configuration from config.yaml${NC}"
}

# Function to save system state
save_system_state() {
    echo -e "\n${YELLOW}Saving system state...${NC}"
    
    # Create state directory
    STATE_DIR="storage/state/shutdown_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$STATE_DIR"
    
    # Save current jobs
    curl -s http://localhost:$API_PORT/jobs > "$STATE_DIR/jobs.json" 2>/dev/null || echo "{}" > "$STATE_DIR/jobs.json"
    
    # Save models info
    curl -s http://localhost:$API_PORT/models > "$STATE_DIR/models.json" 2>/dev/null || echo "{}" > "$STATE_DIR/models.json"
    
    # Save system status
    curl -s http://localhost:$API_PORT/status > "$STATE_DIR/status.json" 2>/dev/null || echo "{}" > "$STATE_DIR/status.json"
    
    echo -e "  ${GREEN}✓ State saved to $STATE_DIR${NC}"
}

# Function to gracefully stop a service
stop_service() {
    local service_name=$1
    local pid_file=$2
    local process_pattern=$3
    local timeout=${4:-10}
    
    echo -e "\n${YELLOW}Stopping $service_name...${NC}"
    
    # Try PID file first
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if kill -0 $PID 2>/dev/null; then
            echo -e "  ${BLUE}Sending SIGTERM to PID $PID${NC}"
            kill -TERM $PID 2>/dev/null
            
            # Wait for graceful shutdown
            for i in $(seq 1 $timeout); do
                if ! kill -0 $PID 2>/dev/null; then
                    rm -f "$pid_file"
                    echo -e "  ${GREEN}✓ $service_name stopped gracefully${NC}"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill if still running
            echo -e "  ${YELLOW}Graceful shutdown timeout, forcing...${NC}"
            kill -9 $PID 2>/dev/null
            rm -f "$pid_file"
        else
            echo -e "  ${YELLOW}PID $PID not found, cleaning up pid file${NC}"
            rm -f "$pid_file"
        fi
    fi
    
    # Kill by process pattern
    if pgrep -f "$process_pattern" >/dev/null; then
        echo -e "  ${BLUE}Stopping processes matching: $process_pattern${NC}"
        pkill -TERM -f "$process_pattern"
        sleep 2
        
        # Force kill if still running
        if pgrep -f "$process_pattern" >/dev/null; then
            echo -e "  ${YELLOW}Force stopping remaining processes${NC}"
            pkill -9 -f "$process_pattern"
        fi
    fi
    
    echo -e "  ${GREEN}✓ $service_name stopped${NC}"
}

# Load configuration
parse_yaml

# Step 1: Check for active jobs
echo -e "\n${YELLOW}[1/5] Checking active jobs...${NC}"
ACTIVE_JOBS=$(curl -s http://localhost:$API_PORT/jobs?status=running 2>/dev/null | jq '. | length' 2>/dev/null || echo "0")
ACTIVE_AGENTS=$(curl -s http://localhost:$API_PORT/agents/status 2>/dev/null | jq '.active_count' 2>/dev/null || echo "0")

if [ "$ACTIVE_JOBS" -gt "0" ] || [ "$ACTIVE_AGENTS" -gt "0" ]; then
    echo -e "  ${YELLOW}WARNING: Active operations detected!${NC}"
    [ "$ACTIVE_JOBS" -gt "0" ] && echo -e "  ${YELLOW}- $ACTIVE_JOBS jobs still running${NC}"
    [ "$ACTIVE_AGENTS" -gt "0" ] && echo -e "  ${YELLOW}- $ACTIVE_AGENTS agents still active${NC}"
    echo -ne "  ${YELLOW}Continue with shutdown? (y/n): ${NC}"
    read -n 1 answer
    echo
    if [ "$answer" != "y" ]; then
        echo -e "  ${RED}Shutdown cancelled${NC}"
        exit 1
    fi
    echo -e "  ${BLUE}Proceeding with shutdown...${NC}"
fi

# Step 2: Save system state (if configured)
if [ "$SAVE_STATE" = "true" ]; then
    echo -e "\n${YELLOW}[2/5] Saving system state...${NC}"
    save_system_state
else
    echo -e "\n${YELLOW}[2/5] Skipping state save (disabled in config)${NC}"
fi

# Step 3: Stop API Service
echo -e "\n${YELLOW}[3/5] Stopping API Service...${NC}"

# Send shutdown signal to API if available
echo -e "  ${BLUE}Requesting graceful API shutdown...${NC}"
curl -X POST http://localhost:$API_PORT/shutdown 2>/dev/null || true
sleep 2

# Stop the service
stop_service "API Service" "api_service.pid" "api_services.py" 15

# Verify port is free
if lsof -i :$API_PORT >/dev/null 2>&1; then
    echo -e "  ${YELLOW}WARNING: Port $API_PORT still in use${NC}"
    lsof -i :$API_PORT
fi

# Step 4: Stop Ollama
echo -e "\n${YELLOW}[4/5] Stopping Ollama...${NC}"
stop_service "Ollama" "ollama.pid" "ollama serve" 10

# Step 5: PostgreSQL (optional)
echo -e "\n${YELLOW}[5/5] Database ($DB_TYPE)...${NC}"
if [ "$DB_TYPE" = "postgresql" ]; then
    # Check if PostgreSQL has active connections from our app
    ACTIVE_CONNECTIONS=$(sudo -u postgres psql -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'anomaly_detection' AND state = 'active';" 2>/dev/null || echo "0")
    ACTIVE_CONNECTIONS=$(echo $ACTIVE_CONNECTIONS | tr -d ' ')
    
    if [ "$ACTIVE_CONNECTIONS" -gt "0" ]; then
        echo -e "  ${YELLOW}Active database connections: $ACTIVE_CONNECTIONS${NC}"
    fi
    
    echo -e "  ${BLUE}PostgreSQL left running (recommended)${NC}"
    echo -e "  ${BLUE}To stop manually: sudo systemctl stop postgresql${NC}"
else
    echo -e "  ${BLUE}Using $DB_TYPE storage (no action needed)${NC}"
fi

# Cleanup temporary files
echo -e "\n${YELLOW}Cleaning up temporary files...${NC}"
rm -f api_service.pid ollama.pid 2>/dev/null
echo -e "  ${GREEN}✓ Cleaned up PID files${NC}"

# Final status check
echo -e "\n${YELLOW}Verifying shutdown...${NC}"
ERRORS=0

if pgrep -f "api_services.py" >/dev/null; then
    echo -e "  ${RED}✗ API Service still running${NC}"
    ((ERRORS++))
else
    echo -e "  ${GREEN}✓ API Service stopped${NC}"
fi

if pgrep -f "ollama serve" >/dev/null; then
    echo -e "  ${RED}✗ Ollama still running${NC}"
    ((ERRORS++))
else
    echo -e "  ${GREEN}✓ Ollama stopped${NC}"
fi

# Summary
echo
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}=== SHUTDOWN COMPLETE ===${NC}"
    echo -e "${BLUE}All services stopped successfully${NC}"
else
    echo -e "${YELLOW}=== SHUTDOWN COMPLETED WITH WARNINGS ===${NC}"
    echo -e "${YELLOW}$ERRORS service(s) may still be running${NC}"
    echo -e "${YELLOW}Check with: ps aux | grep -E 'api_services|ollama'${NC}"
fi

# Show restart command
echo
echo -e "${BLUE}To restart the system:${NC}"
echo -e "  ./sop_system_startup.sh"

# Log shutdown
echo "$(date): System shutdown completed" >> logs/shutdown.log