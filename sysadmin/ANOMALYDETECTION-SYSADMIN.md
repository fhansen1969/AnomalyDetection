# Anomaly Detection System - Complete System Administrator Guide

## Table of Contents

1. [System Overview](#system-overview)
2. [Critical System Components](#critical-system-components)
3. [Service Management](#service-management)
4. [System Health Monitoring](#system-health-monitoring)
5. [Debugging and Troubleshooting](#debugging-and-troubleshooting)
6. [Database Management](#database-management)
7. [API Services](#api-services)
8. [Agent System](#agent-system)
9. [Testing and Validation](#testing-and-validation)
10. [Configuration](#configuration)
11. [Operational Runbooks](#operational-runbooks)

## System Overview

The Anomaly Detection System is a comprehensive machine learning platform that uses multiple models and AI agents to detect, analyze, and remediate anomalies in real-time. The system consists of three main components that must work together:

- **PostgreSQL Database** - Stores all anomalies, model states, agent activities, and system metadata
- **API Service** - FastAPI-based REST API that exposes all system functionality
- **Ollama** - AI service that powers the agent-based analysis system

## Critical System Components

### Core Services That MUST Be Running

Before any operations can be performed, these three services must be active and healthy:

1. **PostgreSQL Database (Port 5432)**
   - Stores all system data including anomalies, model states, and agent interactions
   - Required for persistence and historical analysis

2. **API Service (api_services.py - Port 8000)**
   - Provides REST endpoints for all system operations
   - Manages background jobs for training and detection
   - Handles real-time WebSocket connections for alerts

3. **Ollama (Port 11434)**
   - Powers the AI agent system for intelligent anomaly analysis
   - Provides natural language understanding and generation capabilities
   - Required for the enhanced agent-based analysis features

## Service Management

### 1.1 PostgreSQL Database

PostgreSQL is the backbone of the system, storing all operational data. The database uses a comprehensive schema with tables for anomalies, models, agent activities, and system state.

#### Check Status

The following commands verify that PostgreSQL is running and accessible:

```bash
# Is PostgreSQL running?
sudo systemctl status postgresql

# Can we connect?
PGPASSWORD="XXXXX" psql -h localhost -p 5432 -U anomaly_user -d anomaly_detection -c "SELECT 1;"

# Check active connections
PGPASSWORD="XXXXX" psql -h localhost -p 5432 -U anomaly_user -d anomaly_detection -c "SELECT count(*) FROM pg_stat_activity;"
```

#### Start/Stop/Restart

Standard systemctl commands manage the PostgreSQL service:

```bash
# Start
sudo systemctl start postgresql

# Stop
sudo systemctl stop postgresql

# Restart
sudo systemctl restart postgresql

# Enable auto-start on boot
sudo systemctl enable postgresql
```

#### Common Issues

When PostgreSQL connection issues occur, these commands help diagnose and fix common problems:

```bash
# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*.log

# Fix "could not connect" errors
sudo -u postgres psql -c "ALTER USER anomaly_user PASSWORD 'XXXXX';"

# Fix permission issues
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE anomaly_detection TO anomaly_user;"
```

### 1.2 API Service (api_services.py)

The API service is the central hub that coordinates all system operations. It implements a FastAPI application with comprehensive endpoints for model management, anomaly detection, and agent-based analysis.

#### Check if Running

These commands verify the API service status:

```bash
# Is the process running?
ps aux | grep api_services.py | grep -v grep

# Is port 8000 listening?
sudo netstat -tlnp | grep :8000
# or
sudo lsof -i :8000

# Test API endpoint
curl -s http://localhost:8000/ | jq .
```

#### Start API Service (PROPER WAY)

The proper startup script ensures clean initialization with logging and PID tracking:

```bash
#!/bin/bash
# start_api_service.sh

# Kill any existing instances
pkill -f api_services.py

# Wait for port to be free
sleep 2

# Start with proper logging
LOG_FILE="logs/api_services_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

echo "Starting API service..."
nohup python api_services.py \
    --config config/config.yaml \
    --host 0.0.0.0 \
    --port 8000 \
    --auto-init \
    > "$LOG_FILE" 2>&1 &

API_PID=$!
echo "API Service started with PID: $API_PID"
echo $API_PID > api_service.pid

# Wait for service to be ready
echo "Waiting for API to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "API Service is ready!"
        break
    fi
    echo -n "."
    sleep 1
done

# Verify
curl -s http://localhost:8000/ | jq .
```

This script performs several important tasks:
- Kills any existing API service instances to prevent port conflicts
- Creates a timestamped log file for debugging
- Starts the service with proper configuration and auto-initialization
- Saves the process ID for clean shutdown later
- Waits for the service to be fully ready before returning

#### Stop API Service

Clean shutdown is important to prevent orphaned processes:

```bash
#!/bin/bash
# stop_api_service.sh

if [ -f api_service.pid ]; then
    PID=$(cat api_service.pid)
    echo "Stopping API service (PID: $PID)..."
    kill $PID
    rm api_service.pid
else
    echo "No PID file found, using pkill..."
    pkill -f api_services.py
fi

# Verify it's stopped
sleep 2
if ps aux | grep api_services.py | grep -v grep; then
    echo "Warning: API service still running, force killing..."
    pkill -9 -f api_services.py
fi
```

#### Monitor API Logs

Real-time log monitoring helps identify issues quickly:

```bash
# Follow current log
tail -f logs/api_services_*.log

# Check for errors
grep -i error logs/api_services_*.log | tail -20

# Check for warnings
grep -i warning logs/api_services_*.log | tail -20
```

### 1.3 Ollama Service (Required for AI Agents)

Ollama provides the AI capabilities that power the intelligent agent system. Without Ollama, the system can still detect anomalies but cannot provide intelligent analysis or remediation recommendations.

#### Install Ollama (if not installed)

```bash
# Download and install
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve &

# Or use systemd
sudo systemctl start ollama
sudo systemctl enable ollama
```

#### Check Ollama Status

```bash
# Is Ollama running?
ps aux | grep ollama | grep -v grep

# Test API endpoint
curl http://localhost:11434/api/tags

# List available models
ollama list
```

#### Install Required Model

The Mistral model is required for agent operations:

```bash
# Pull the Mistral model (required for agents)
ollama pull mistral

# Verify model is available
ollama list | grep mistral
```

#### Start/Stop Ollama

This management script provides consistent control over the Ollama service:

```bash
#!/bin/bash
# manage_ollama.sh

case "$1" in
    start)
        echo "Starting Ollama..."
        nohup ollama serve > logs/ollama.log 2>&1 &
        echo $! > ollama.pid
        sleep 2
        if curl -s http://localhost:11434/api/tags > /dev/null; then
            echo "Ollama started successfully"
        else
            echo "Failed to start Ollama"
        fi
        ;;
    stop)
        echo "Stopping Ollama..."
        if [ -f ollama.pid ]; then
            kill $(cat ollama.pid)
            rm ollama.pid
        else
            pkill -f "ollama serve"
        fi
        ;;
    status)
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "Ollama is running"
            ollama list
        else
            echo "Ollama is not running"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        ;;
esac
```

## System Health Monitoring

### 2.1 Complete Health Check Script

This comprehensive health check script verifies all system components and provides a quick overview of system status:

```bash
#!/bin/bash
# system_health_check.sh

echo "======================================"
echo "Anomaly Detection System Health Check"
echo "Time: $(date)"
echo "======================================"

# Function to check service
check_service() {
    local service_name=$1
    local check_command=$2
    local port=$3
    
    echo -n "Checking $service_name... "
    
    if eval "$check_command" > /dev/null 2>&1; then
        echo "✓ OK (Port $port)"
        return 0
    else
        echo "✗ FAILED"
        return 1
    fi
}

# Check PostgreSQL
check_service "PostgreSQL" "PGPASSWORD='XXXXX' psql -h localhost -p 5432 -U anomaly_user -d anomaly_detection -c 'SELECT 1;'" "5432"
POSTGRES_OK=$?

# Check API Service
check_service "API Service" "curl -s http://localhost:8000/health" "8000"
API_OK=$?

# Check Ollama
check_service "Ollama" "curl -s http://localhost:11434/api/tags" "11434"
OLLAMA_OK=$?

# Check disk space
echo -e "\nDisk Space:"
df -h | grep -E "Filesystem|/$|/var|/storage" | awk '{printf "%-20s %s %s %s\n", $1, $4, $5, $6}'

# Check memory
echo -e "\nMemory Usage:"
free -h | grep -E "Mem:|Swap:"

# Check API endpoints
if [ $API_OK -eq 0 ]; then
    echo -e "\nAPI Endpoints Test:"
    
    # System status
    echo -n "  System Status: "
    if curl -s http://localhost:8000/system/status > /dev/null; then
        echo "✓"
    else
        echo "✗"
    fi
    
    # Models
    echo -n "  Models: "
    MODEL_COUNT=$(curl -s http://localhost:8000/models | jq '. | length' 2>/dev/null || echo "0")
    echo "$MODEL_COUNT loaded"
    
    # Agent status
    echo -n "  Agents: "
    AGENT_STATUS=$(curl -s http://localhost:8000/agents/status | jq -r '.enabled' 2>/dev/null || echo "false")
    if [ "$AGENT_STATUS" = "true" ]; then
        echo "✓ Enabled"
    else
        echo "✗ Disabled"
    fi
fi

# Check for recent errors
echo -e "\nRecent Errors (last 10):"
grep -i error logs/api_services_*.log 2>/dev/null | tail -10 | sed 's/^/  /'

# Summary
echo -e "\n======================================"
echo "Summary:"
if [ $POSTGRES_OK -eq 0 ] && [ $API_OK -eq 0 ]; then
    echo "Core Services: ✓ All OK"
else
    echo "Core Services: ✗ PROBLEMS DETECTED"
fi

if [ $OLLAMA_OK -eq 0 ]; then
    echo "AI Agents: ✓ Available"
else
    echo "AI Agents: ✗ Not Available (agents will not work)"
fi
```

The health check script provides:
- Service availability status for all core components
- System resource usage (disk space, memory)
- API endpoint validation
- Model and agent status
- Recent error detection
- Clear summary of system health

### 2.2 Continuous Monitoring Script

For production environments, continuous monitoring ensures quick detection of issues:

```bash
#!/bin/bash
# monitor_services.sh

# Run health check every 60 seconds
while true; do
    clear
    ./system_health_check.sh
    
    # Alert if services are down
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "ALERT: API Service is DOWN!" | wall
        # Optional: send email/SMS alert
    fi
    
    sleep 60
done
```

## Debugging and Troubleshooting

### 3.1 API Service Debug Script

When the API service fails to start or behaves unexpectedly, this debug script helps identify the root cause:

```bash
#!/bin/bash
# debug_api_service.sh

echo "=== API Service Debugging ==="

# 1. Check if port is already in use
echo "1. Checking port 8000..."
if lsof -i :8000 > /dev/null 2>&1; then
    echo "   Port 8000 is in use by:"
    lsof -i :8000
    echo "   Kill the process? (y/n)"
    read answer
    if [ "$answer" = "y" ]; then
        lsof -t -i :8000 | xargs kill -9
        echo "   Process killed"
    fi
else
    echo "   Port 8000 is free"
fi

# 2. Check Python dependencies
echo -e "\n2. Checking Python dependencies..."
python -c "
import sys
print(f'Python version: {sys.version}')

required = [
    'fastapi', 'uvicorn', 'pydantic', 'psycopg2',
    'scikit-learn', 'tensorflow', 'torch', 'pyyaml'
]

for module in required:
    try:
        __import__(module)
        print(f'  ✓ {module}')
    except ImportError:
        print(f'  ✗ {module} - MISSING!')
"

# 3. Test configuration file
echo -e "\n3. Testing configuration..."
if [ -f config/config.yaml ]; then
    python -c "
import yaml
try:
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    print('  ✓ Configuration is valid')
    print(f'  Database type: {config.get(\"database\", {}).get(\"type\")}')
except Exception as e:
    print(f'  ✗ Configuration error: {e}')
"
else
    echo "  ✗ config/config.yaml not found!"
fi

# 4. Test database connection
echo -e "\n4. Testing database connection..."
python -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        dbname='anomaly_detection',
        user='anomaly_user',
        password='XXXXX'
    )
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM information_schema.tables')
    count = cursor.fetchone()[0]
    print(f'  ✓ Database connection OK ({count} tables)')
    conn.close()
except Exception as e:
    print(f'  ✗ Database error: {e}')
"

# 5. Try to start API in debug mode
echo -e "\n5. Starting API in debug mode..."
echo "Press Ctrl+C to stop"
python api_services.py --config config/config.yaml --verbose --auto-init
```

This debug script systematically checks:
- Port availability to prevent binding conflicts
- Python dependency installation status
- Configuration file validity
- Database connectivity
- Attempts to start the API in verbose mode for detailed error messages

### 3.2 Database Debug Script

Database issues can prevent the entire system from functioning. This script helps diagnose PostgreSQL problems:

```bash
#!/bin/bash
# debug_database.sh

echo "=== Database Debugging ==="

# 1. PostgreSQL service status
echo "1. PostgreSQL Service:"
sudo systemctl status postgresql --no-pager | head -10

# 2. Check PostgreSQL config
echo -e "\n2. PostgreSQL Configuration:"
sudo -u postgres psql -c "SHOW config_file;"
sudo -u postgres psql -c "SHOW data_directory;"
sudo -u postgres psql -c "SHOW port;"

# 3. Check authentication
echo -e "\n3. Authentication (pg_hba.conf):"
sudo grep -v "^#" /etc/postgresql/*/main/pg_hba.conf | grep -v "^$"

# 4. Test connections
echo -e "\n4. Testing connections:"
echo -n "  Local connection: "
if sudo -u postgres psql -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✓"
else
    echo "✗"
fi

echo -n "  TCP connection: "
if PGPASSWORD="XXXXX" psql -h localhost -p 5432 -U anomaly_user -d anomaly_detection -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✓"
else
    echo "✗"
fi

# 5. Check database tables
echo -e "\n5. Database tables:"
PGPASSWORD="XXXXX" psql -h localhost -p 5432 -U anomaly_user -d anomaly_detection -c "\dt" 2>&1

# 6. Check for locks
echo -e "\n6. Active locks:"
PGPASSWORD="XXXXX" psql -h localhost -p 5432 -U anomaly_user -d anomaly_detection -c "
SELECT pid, usename, application_name, state, query 
FROM pg_stat_activity 
WHERE state != 'idle' AND query NOT LIKE '%pg_stat_activity%';"
```

### 3.3 Ollama Debug Script

The AI agent system depends on Ollama functioning correctly. This script verifies Ollama installation and operation:

```bash
#!/bin/bash
# debug_ollama.sh

echo "=== Ollama Debugging ==="

# 1. Check if Ollama is installed
echo "1. Ollama installation:"
if command -v ollama > /dev/null; then
    echo "  ✓ Ollama is installed"
    ollama --version
else
    echo "  ✗ Ollama is NOT installed"
    echo "  Install with: curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
fi

# 2. Check if Ollama service is running
echo -e "\n2. Ollama service:"
if pgrep -f "ollama serve" > /dev/null; then
    echo "  ✓ Ollama service is running"
    ps aux | grep "ollama serve" | grep -v grep
else
    echo "  ✗ Ollama service is NOT running"
    echo "  Start with: ollama serve &"
fi

# 3. Test Ollama API
echo -e "\n3. Ollama API test:"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  ✓ API is responding"
    echo "  Available models:"
    curl -s http://localhost:11434/api/tags | jq -r '.models[].name' | sed 's/^/    - /'
else
    echo "  ✗ API is NOT responding"
fi

# 4. Check for Mistral model
echo -e "\n4. Mistral model check:"
if ollama list | grep -q mistral; then
    echo "  ✓ Mistral model is available"
else
    echo "  ✗ Mistral model is NOT available"
    echo "  Install with: ollama pull mistral"
fi

# 5. Test model execution
echo -e "\n5. Testing model execution:"
if echo "test" | ollama run mistral "Say 'OK' if you can read this" 2>/dev/null | grep -q "OK"; then
    echo "  ✓ Model execution successful"
else
    echo "  ✗ Model execution failed"
fi
```

### 3.4 Complete System Debug

This master debug script runs all diagnostic checks in sequence:

```bash
#!/bin/bash
# debug_everything.sh

echo "==================================="
echo "Complete System Debug"
echo "==================================="

# Run all debug scripts
./debug_database.sh
echo -e "\n-----------------------------------\n"
./debug_ollama.sh
echo -e "\n-----------------------------------\n"
./debug_api_service.sh
```

### API Services Debug Script (api_services_debug.py)

This Python debug script provides deeper insights into why the API service might fail to start:

```python
"""
This debugging script will help identify why api_services.py isn't staying running.
Save this to a file named debug_api.py and run it instead of api_services.py.
"""

import os
import sys
import logging
import yaml
import importlib
import subprocess
import socket

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("debug_script")

def check_port_available(host, port):
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0

def check_dependencies():
    """Check if required Python packages are installed."""
    required_packages = [
        "fastapi", 
        "uvicorn", 
        "pydantic", 
        "pyyaml", 
        "scikit-learn",  # For isolation forest
        "tensorflow",    # For autoencoder
        "torch"          # For GAN
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package)
            logger.info(f"✅ Package {package} is installed")
        except ImportError:
            logger.error(f"❌ Package {package} is NOT installed")
            missing_packages.append(package)
    
    return missing_packages

def check_ollama():
    """Check if Ollama is running."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            logger.info("✅ Ollama is running")
            models = response.json().get("models", [])
            if any(model.get("name") == "mistral" for model in models):
                logger.info("✅ Mistral model is available in Ollama")
            else:
                logger.warning("⚠️ Mistral model not found in Ollama")
        else:
            logger.error("❌ Ollama is not responding correctly")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Ollama: {str(e)}")

def check_configuration(config_path):
    """Validate the configuration file."""
    try:
        if not os.path.exists(config_path):
            logger.error(f"❌ Configuration file not found: {config_path}")
            return False
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"✅ Configuration file loaded successfully: {config_path}")
        
        # Check database configuration
        if "database" in config:
            db_type = config["database"].get("type")
            logger.info(f"Database type: {db_type}")
            
            if db_type == "postgresql":
                try:
                    import psycopg2
                    logger.info("✅ psycopg2 is installed for PostgreSQL")
                except ImportError:
                    logger.error("❌ psycopg2 is NOT installed (required for PostgreSQL)")
                    return False
        
        return True
    except Exception as e:
        logger.error(f"❌ Error checking configuration: {str(e)}")
        return False

def run_with_tracing():
    """Run api_services.py with tracing to see where it fails."""
    try:
        logger.info("Running api_services.py with tracing...")
        
        # Use a modified version of the command
        cmd = [
            sys.executable, 
            "-m", "trace", 
            "--trace", 
            "api_services.py", 
            "--config", 
            "config/config.yaml", 
            "--host", 
            "127.0.0.1", 
            "--port", 
            "8080"
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for a few seconds
        import time
        time.sleep(5)
        
        # Check if the process is still running
        if process.poll() is None:
            logger.info("✅ Server is still running after 5 seconds")
            process.terminate()
        else:
            stdout, stderr = process.communicate()
            logger.error(f"❌ Server exited with code {process.returncode}")
            logger.info("STDOUT:")
            logger.info(stdout)
            logger.error("STDERR:")
            logger.error(stderr)
    except Exception as e:
        logger.error(f"❌ Error running with tracing: {str(e)}")

def main():
    """Main function."""
    logger.info("Starting diagnostics...")
    
    # Check Python version
    logger.info(f"Python version: {sys.version}")
    
    # Check dependencies
    missing_packages = check_dependencies()
    if missing_packages:
        logger.warning(f"Missing packages: {', '.join(missing_packages)}")
        logger.info("Try installing them with:")
        logger.info(f"pip install {' '.join(missing_packages)}")
    
    # Check if port is available
    host = "127.0.0.1"
    port = 8080
    if check_port_available(host, port):
        logger.info(f"✅ Port {port} is available")
    else:
        logger.error(f"❌ Port {port} is already in use")
    
    # Check Ollama
    check_ollama()
    
    # Check configuration
    config_path = "config/config.yaml"
    check_configuration(config_path)
    
    # Run with tracing
    run_with_tracing()
    
    logger.info("Diagnostics completed")

if __name__ == "__main__":
    main()
```

## Database Management

### Database Build Script (build_db.sh)

This script creates the complete database schema and populates it with sample data for testing:

```bash
#!/bin/bash

# Database Build Script for Anomaly Detection System
# This script sets up the PostgreSQL database and populates it with initial data

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Database configuration
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="anomaly_detection"
DB_USER="anomaly_user"
DB_PASS="XXXXX"

# Function to check if PostgreSQL is running
check_postgres() {
    echo -e "${YELLOW}Checking PostgreSQL service...${NC}"
    if pg_isready -h $DB_HOST -p $DB_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}PostgreSQL is running${NC}"
        return 0
    else
        echo -e "${RED}PostgreSQL is not running${NC}"
        return 1
    fi
}

# Function to create database and user
setup_database() {
    echo -e "${YELLOW}Setting up database...${NC}"
    
    # Create user if it doesn't exist
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null || echo "User already exists"
    
    # Create database if it doesn't exist
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || echo "Database already exists"
    
    # Grant all privileges
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
    
    echo -e "${GREEN}Database setup complete${NC}"
}

# Function to create tables
create_tables() {
    echo -e "${YELLOW}Creating database tables...${NC}"
    
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << EOF
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables to start fresh
DROP TABLE IF EXISTS agent_messages CASCADE;
DROP TABLE IF EXISTS agent_activities CASCADE;
DROP TABLE IF EXISTS anomaly_analysis CASCADE;
DROP TABLE IF EXISTS anomalies CASCADE;
DROP TABLE IF EXISTS models CASCADE;
DROP TABLE IF EXISTS system_status CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS processed_data CASCADE;
DROP TABLE IF EXISTS model_states CASCADE;
DROP TABLE IF EXISTS processors CASCADE;
DROP TABLE IF EXISTS collectors CASCADE;
DROP TABLE IF EXISTS background_jobs CASCADE;
DROP TABLE IF EXISTS vector_embeddings CASCADE;

-- Create models table
CREATE TABLE models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'not_trained',
    config JSONB DEFAULT '{}',
    performance JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create anomalies table
CREATE TABLE anomalies (
    id VARCHAR(255) PRIMARY KEY,
    model_id INTEGER REFERENCES models(id),
    model VARCHAR(255) NOT NULL,
    score FLOAT NOT NULL,
    threshold FLOAT DEFAULT 0.5,
    timestamp TIMESTAMP NOT NULL,
    detection_time TIMESTAMP NOT NULL,
    location VARCHAR(255),
    src_ip VARCHAR(50),
    dst_ip VARCHAR(50),
    details JSONB DEFAULT '{}',
    features JSONB DEFAULT '[]',
    analysis JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'new',
    data JSONB DEFAULT '{}',
    severity VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- [Additional table creation statements...]

-- Create indices for better performance
CREATE INDEX idx_anomalies_timestamp ON anomalies(timestamp);
CREATE INDEX idx_anomalies_model ON anomalies(model);
CREATE INDEX idx_anomalies_score ON anomalies(score);
CREATE INDEX idx_anomalies_status ON anomalies(status);
CREATE INDEX idx_anomalies_severity ON anomalies(severity);
-- [Additional indices...]

EOF

    echo -e "${GREEN}Tables created successfully${NC}"
}

# Function to populate initial data
populate_data() {
    echo -e "${YELLOW}Populating database with initial data...${NC}"
    
    # [SQL statements to insert sample data]
    
    echo -e "${GREEN}Initial data populated successfully${NC}"
}

# Main execution
echo -e "${GREEN}=== Anomaly Detection Database Build Script ===${NC}"

# Check if PostgreSQL is running
if ! check_postgres; then
    echo -e "${RED}Please start PostgreSQL service first${NC}"
    exit 1
fi

# Setup database
setup_database

# Create tables
create_tables

# Populate initial data
populate_data

echo -e "${GREEN}Database build completed successfully!${NC}"
echo -e "${YELLOW}Connection details:${NC}"
echo -e "  Host: $DB_HOST"
echo -e "  Port: $DB_PORT"
echo -e "  Database: $DB_NAME"
echo -e "  User: $DB_USER"
echo -e "  Password: $DB_PASS"
```

The database build script:
- Checks PostgreSQL availability before proceeding
- Creates the database user and database if they don't exist
- Drops and recreates all tables for a clean slate
- Creates comprehensive indices for performance
- Populates sample data for testing
- Provides clear feedback throughout the process

### Database Health Check Script (check_db_health.sh)

This script performs a comprehensive health check of the database schema:

```bash
#!/bin/bash

# Database Health Check Script
# This script checks the database schema for issues

# Variables for database connection
HOST="localhost"
PORT="5432"
DATABASE="anomaly_detection"
USER="anomaly_user"
PASSWORD="XXXXX"

echo "Checking database health..."

# Connect as anomaly_user
export PGPASSWORD="$PASSWORD"

psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" <<EOF
-- Check for required tables
\echo 'Checking for required tables...'
SELECT 
    table_name,
    CASE 
        WHEN table_name IN (
            'anomalies', 'models', 'processed_data', 'model_states',
            'anomaly_analysis', 'agent_messages', 'agent_activities',
            'processors', 'collectors', 'system_status', 'jobs',
            'background_jobs', 'vector_embeddings'
        ) THEN 'Required'
        ELSE 'Extra'
    END as status
FROM information_schema.tables
WHERE table_schema = current_schema()
ORDER BY table_name;

-- Check anomalies table columns
\echo ''
\echo 'Checking anomalies table columns...'
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'anomalies'
ORDER BY ordinal_position;

-- Check for missing required columns in anomalies
\echo ''
\echo 'Checking for missing columns in anomalies table...'
WITH required_columns AS (
    SELECT unnest(ARRAY[
        'id', 'timestamp', 'detection_time', 'model', 'model_id',
        'score', 'threshold', 'location', 'src_ip', 'dst_ip',
        'data', 'original_data', 'details', 'features', 'status',
        'analysis', 'created_at', 'updated_at'
    ]) AS column_name
)
SELECT 
    rc.column_name,
    CASE 
        WHEN c.column_name IS NULL THEN 'MISSING'
        ELSE 'Present'
    END as status
FROM required_columns rc
LEFT JOIN information_schema.columns c
    ON c.table_name = 'anomalies' 
    AND c.column_name = rc.column_name
WHERE c.column_name IS NULL;

-- Check foreign key constraints
\echo ''
\echo 'Checking foreign key constraints...'
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name;

-- Check indices
\echo ''
\echo 'Checking indices on anomalies table...'
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'anomalies'
ORDER BY indexname;

-- Check for orphaned records
\echo ''
\echo 'Checking for orphaned records...'
SELECT 
    'agent_activities' as table_name,
    COUNT(*) as orphaned_count
FROM agent_activities
WHERE anomaly_id NOT IN (SELECT id FROM anomalies)
UNION ALL
SELECT 
    'agent_messages' as table_name,
    COUNT(*) as orphaned_count
FROM agent_messages
WHERE anomaly_id NOT IN (SELECT id FROM anomalies)
UNION ALL
SELECT 
    'anomaly_analysis' as table_name,
    COUNT(*) as orphaned_count
FROM anomaly_analysis
WHERE anomaly_id NOT IN (SELECT id FROM anomalies);

-- Table row counts
\echo ''
\echo 'Table row counts...'
SELECT 
    schemaname,
    tablename,
    n_live_tup as row_count
FROM pg_stat_user_tables
ORDER BY tablename;

\echo ''
\echo 'Database health check completed.'
EOF
```

The health check verifies:
- All required tables exist
- All required columns are present in each table
- Foreign key relationships are properly defined
- Indices exist for performance optimization
- No orphaned records exist in related tables
- Current row counts for capacity planning

### Cleanup Script (cleanup.sh)

This script safely cleans up data while preserving the database structure:

```bash
#!/bin/sh

# Clean up storage directory files
echo "Cleaning up storage files..."

# Create directories if they don't exist
mkdir -p storage/anomalies
mkdir -p storage/models
mkdir -p storage/processed
mkdir -p storage/state

# Clean anomalies directory (keep directory structure)
echo "Cleaning anomalies directory..."
find storage/anomalies -name "*.json" -type f -delete 2>/dev/null || true

# Clean models directory (keep directory structure)
echo "Cleaning models directory..."
find storage/models -name "*.pkl" -type f -delete 2>/dev/null || true
find storage/models -name "*.joblib" -type f -delete 2>/dev/null || true
find storage/models -name "*.json" -type f -delete 2>/dev/null || true
find storage/models -name "*.h5" -type f -delete 2>/dev/null || true
find storage/models -name "*.pt" -type f -delete 2>/dev/null || true
find storage/models -name "*.pth" -type f -delete 2>/dev/null || true

# Clean processed directory (keep directory structure)
echo "Cleaning processed directory..."
find storage/processed -name "*.json" -type f -delete 2>/dev/null || true

# Clean state directory (keep directory structure)
echo "Cleaning state directory..."
find storage/state -name "*.json" -type f -delete 2>/dev/null || true

# Remove collector files if they exist
rm -f storage/file_collector_*_processed.json 2>/dev/null || true

# Clean database tables
echo "Cleaning database tables..."

# Variables for database connection
HOST="localhost"
PORT="5432"
DATABASE="anomaly_detection"
USER="anomaly_user"
PASSWORD="XXXXX"

# Connect as anomaly_user
export PGPASSWORD="$PASSWORD"
psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" <<EOF
-- Set statement timeout to avoid hanging
SET statement_timeout = '10000';  -- 10 seconds

-- Clean tables in the correct order (respecting foreign keys)
DO \$\$
BEGIN
    -- Clean tables that reference anomalies first
    BEGIN
        TRUNCATE TABLE agent_activities CASCADE;
        RAISE NOTICE 'Truncated agent_activities table';
    EXCEPTION 
        WHEN undefined_table THEN
            RAISE NOTICE 'Table agent_activities does not exist, skipping';
        WHEN OTHERS THEN
            RAISE NOTICE 'Error truncating agent_activities: %', SQLERRM;
    END;
    
    -- [Additional TRUNCATE statements...]
    
    -- Keep configuration tables but reset status
    BEGIN
        -- Update processors status to inactive
        UPDATE processors SET status = 'inactive', updated_at = NOW();
        RAISE NOTICE 'Reset processor statuses to inactive';
    EXCEPTION 
        WHEN undefined_table THEN
            RAISE NOTICE 'Table processors does not exist, skipping';
        WHEN OTHERS THEN
            RAISE NOTICE 'Error updating processors: %', SQLERRM;
    END;
    
    -- [Additional cleanup operations...]
    
    RAISE NOTICE 'Database cleanup completed';
END;
\$\$;

-- Verify the cleanup
SELECT 'Table' as type, 'anomalies' as name, COUNT(*) as count FROM anomalies
UNION ALL
SELECT 'Table', 'agent_messages', COUNT(*) FROM agent_messages
-- [Additional verification queries...]
ORDER BY type, name;

EOF

# Check if the database operations were successful
if [ $? -ne 0 ]; then
    echo "Warning: Some database cleanup operations may have failed. Check the messages above."
    echo "This is usually okay if some tables don't exist yet."
else
    echo "Database cleanup completed successfully."
fi

echo ""
echo "Cleanup complete!"
echo ""
echo "Next steps:"
echo "1. If tables don't exist yet, run './build_db.sh' to create them"
echo "2. To populate with sample data, run 'python ui_db/utils/init_db.py'"
echo "3. Start the UI: cd ui_db && streamlit run app.py"
echo ""
echo "The system is now in a clean state."
```

The cleanup script:
- Preserves directory structure while removing data files
- Respects foreign key constraints when truncating database tables
- Keeps configuration tables but resets their status
- Provides clear feedback about what was cleaned
- Handles errors gracefully when tables don't exist

## API Services

### API Service Implementation (api_services.py)

The API service is the heart of the system, providing REST endpoints for all operations. Key features include:

- **FastAPI Framework**: Modern, fast web framework with automatic API documentation
- **Background Jobs**: Asynchronous processing for long-running operations like training and detection
- **WebSocket Support**: Real-time updates for anomaly alerts and agent activities
- **Comprehensive Error Handling**: Graceful handling of missing components or configuration issues
- **Model Management**: Dynamic loading and management of multiple ML models
- **Agent Integration**: Seamless integration with the AI agent system for intelligent analysis

Key endpoints include:
- `/models` - List and manage ML models
- `/detect` - Run anomaly detection
- `/agents/analyze` - Analyze anomalies with AI agents
- `/jobs/{job_id}` - Check background job status
- `/anomalies` - List detected anomalies
- `/ws` - WebSocket connection for real-time updates

### API Client (api_client.py)

The API client provides a command-line interface to interact with the API service. It includes:

- **Comprehensive CLI**: Subcommands for all API operations
- **Job Management**: Wait for and monitor background jobs
- **Data Loading**: Load test data from JSON files
- **WebSocket Client**: Connect to real-time update streams
- **Rich Output**: Formatted display of results

Example usage:
```bash
# Initialize the system
python api_client.py --url http://localhost:8000 init config/config.yaml

# Train a model
python api_client.py train-model isolation_forest_model data/training.json --wait

# Detect anomalies
python api_client.py detect-anomalies isolation_forest_model data/test.json --wait

# Analyze with agents
python api_client.py analyze-with-agents data/anomalies.json --wait
```

## Agent System

### Agent Manager Test Script (agent_manager_test.py)

This script validates the agent manager initialization independently:

```python
#!/usr/bin/env python3
"""
Debug the agent manager initialization.
"""

import yaml
import logging
import sys
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Import the agent manager
from anomaly_detection.agents.agent_manager import AgentManager

# Load configuration
try:
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    print("✅ Config loaded successfully")
except Exception as e:
    print(f"❌ Error loading config: {str(e)}")
    sys.exit(1)

# Print the agent configuration
print("\nAgent configuration:")
print(config.get("agents", {}))

# Initialize agent manager
print("\nInitializing agent manager...")
try:
    agent_manager = AgentManager(config.get("agents", {}), None)
    print("✅ Agent manager initialized")
except Exception as e:
    print(f"❌ Error initializing agent manager: {str(e)}")
    import traceback
    print(traceback.format_exc())
    sys.exit(1)

# Check if graph was created
if hasattr(agent_manager, 'agent_graph') and agent_manager.agent_graph:
    print("✅ Agent graph created successfully")
else:
    print("❌ Agent graph creation failed")
    
    # Check why it failed
    if not hasattr(agent_manager, 'LANGGRAPH_AVAILABLE') or not agent_manager.LANGGRAPH_AVAILABLE:
        print("  - LangGraph is not available. Please install it with: pip install langgraph")
    
    if not hasattr(agent_manager, 'llm_client') or not agent_manager.llm_client:
        print("  - LLM client is not available. Check Ollama setup.")
        
        # Check Ollama status
        try:
            import ollama
            print("\nChecking Ollama status...")
            models = ollama.list()
            print(f"Available models: {[m.get('name') for m in models.get('models', [])]}")
            
            model_name = config.get("agents", {}).get("llm", {}).get("model", "mistral")
            if any(m.get('name') == model_name for m in models.get("models", [])):
                print(f"✅ Model '{model_name}' is available")
            else:
                print(f"❌ Model '{model_name}' is not available. Try running: ollama pull {model_name}")
        except Exception as e:
            print(f"❌ Error checking Ollama: {str(e)}")
            print("  - Make sure Ollama is running with: ollama serve")
```

This test script:
- Loads the configuration independently
- Attempts to initialize the agent manager
- Diagnoses common failure modes (missing dependencies, Ollama not running)
- Provides specific remediation steps

### Test Agents Script (test_agents.py)

This comprehensive test validates the agent system integration:

```python
# test_agents_fixed.py
import yaml
import sys
import os

# Add the parent directory to the path to find anomaly_detection module
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

print(f"Current dir: {current_dir}")
print(f"Parent dir: {parent_dir}")
print(f"sys.path[0]: {sys.path[0]}")

# First, let's see what files exist
agents_dir = os.path.join(parent_dir, 'anomaly_detection', 'agents')
if os.path.exists(agents_dir):
    print(f"\nFiles in {agents_dir}:")
    for file in os.listdir(agents_dir):
        if file.endswith('.py'):
            print(f"  - {file}")
else:
    print(f"\n✗ Agents directory not found at {agents_dir}")

# Try to import the agent manager
try:
    from anomaly_detection.agents.enhanced_agent_manager import EnhancedAgentManager
    print("\n✓ EnhancedAgentManager import successful")
    ENHANCED_AVAILABLE = True
except ImportError as e:
    print(f"\n✗ Failed to import EnhancedAgentManager: {e}")
    ENHANCED_AVAILABLE = False
    
try:
    from anomaly_detection.agents.agent_manager import AgentManager
    print("✓ Standard AgentManager import successful")
    STANDARD_AVAILABLE = True
except ImportError as e:
    print(f"✗ Failed to import AgentManager: {e}")
    STANDARD_AVAILABLE = False

# [Rest of the test script...]
```

## Testing and Validation

### Debug Anomaly Detection Script (debug_anomaly_detection.py)

This script tests the complete anomaly detection workflow:

```python
# debug_anomaly_detection_fixed.py
import requests
import json
import time

# 1. Check current models
print("=== Current Models ===")
response = requests.get("http://localhost:8000/models")
models = response.json()
for model in models:
    print(f"Model: {model['name']}, Status: {model['status']}, Type: {model['type']}")

# 2. Create better test data
print("\n=== Testing Anomaly Detection ===")

# Normal data matching your original training set
normal_data = [
    {"cpu": 25, "memory": 45, "network": 1000, "errors": 1},
    {"cpu": 30, "memory": 48, "network": 1200, "errors": 2},
    {"cpu": 28, "memory": 46, "network": 1100, "errors": 1},
    {"cpu": 32, "memory": 50, "network": 1300, "errors": 2},
    {"cpu": 27, "memory": 44, "network": 1050, "errors": 1},
    {"cpu": 29, "memory": 47, "network": 1150, "errors": 1},
    {"cpu": 31, "memory": 49, "network": 1250, "errors": 2},
    {"cpu": 26, "memory": 43, "network": 1000, "errors": 0},
    {"cpu": 33, "memory": 51, "network": 1350, "errors": 3},
    {"cpu": 30, "memory": 48, "network": 1200, "errors": 1}
]

# Mix of normal and anomalous data
test_data = [
    {"cpu": 30, "memory": 48, "network": 1200, "errors": 1},      # normal
    {"cpu": 95, "memory": 90, "network": 50000, "errors": 100},   # anomaly
    {"cpu": 28, "memory": 46, "network": 1100, "errors": 1},      # normal
    {"cpu": 5, "memory": 5, "network": 0, "errors": 500},         # anomaly
    {"cpu": 31, "memory": 49, "network": 1250, "errors": 2},      # normal
]

# 3. Train model
print("\nTraining isolation_forest_model with normal data...")
train_response = requests.post(
    "http://localhost:8000/models/isolation_forest_model/train",
    json={"items": normal_data}
)
train_job = train_response.json()
print(f"Training job: {train_job['job_id']}")
time.sleep(2)

# 4. Try detection with appropriate threshold
print("\nDetecting anomalies with threshold 0.45...")
detect_response = requests.post(
    "http://localhost:8000/models/isolation_forest_model/detect?threshold=0.45",
    json={"items": test_data}
)
detect_job = detect_response.json()
print(f"Detection job: {detect_job['job_id']}")

# Wait and get results
time.sleep(2)
job_result = requests.get(f"http://localhost:8000/jobs/{detect_job['job_id']}")
result = job_result.json()

print(f"\nJob Status: {result['status']}")
if result['status'] == 'completed':
    print(f"Anomalies detected: {result['result']['anomalies_detected']}")
    if result['result']['anomalies_detected'] > 0:
        print("\nDetected anomalies:")
        for i, anomaly in enumerate(result['result']['sample_anomalies'], 1):
            print(f"\n{i}. Original data: {anomaly['original_data']}")
            print(f"   Score: {anomaly['score']:.3f}, Severity: {anomaly['severity']}")

# [Additional tests...]
```

This test script:
- Verifies models are loaded correctly
- Creates realistic training and test data
- Trains a model and waits for completion
- Tests anomaly detection with appropriate thresholds
- Displays detailed results for validation

## Configuration

### System Configuration (config.yaml)

The configuration file controls all aspects of the system. Key sections include:

1. **Agent Configuration**
   - Enhanced prompts for detailed analysis
   - Collaboration settings for multi-agent workflows
   - Output formatting preferences

2. **Model Configuration**
   - Enabled models and their hyperparameters
   - Ensemble model weights and combinations

3. **Database Configuration**
   - Connection parameters
   - Storage preferences for agent data

4. **Collector Configuration**
   - Data sources and collection intervals
   - Authentication for external APIs

5. **Alert Configuration**
   - Notification channels and thresholds
   - Email and webhook settings

The configuration uses a hierarchical YAML structure that allows fine-grained control over system behavior while providing sensible defaults.

## Operational Runbooks

### Daily Operations Checklist

This script provides a standardized daily health check:

```bash
#!/bin/bash
# daily_ops_checklist.sh

echo "=== Daily Operations Checklist ==="
echo "Date: $(date)"
echo "Operator: $USER"
echo

# Service checks
echo "[ ] PostgreSQL running"
systemctl is-active postgresql

echo "[ ] API Service running"
curl -s http://localhost:8000/health > /dev/null && echo "    ✓ Healthy" || echo "    ✗ Not responding"

echo "[ ] Ollama running"
curl -s http://localhost:11434/api/tags > /dev/null && echo "    ✓ Healthy" || echo "    ✗ Not responding"

# Disk space
echo "[ ] Disk space > 20% free"
df -h / | awk 'NR==2 {print "    " $4 " free (" $5 " used)"}'

# Database size
echo "[ ] Database size check"
PGPASSWORD="XXXXX" psql -h localhost -U anomaly_user -d anomaly_detection -t -c "
SELECT pg_size_pretty(pg_database_size('anomaly_detection'));" | xargs echo "    Size:"

# Recent errors
echo "[ ] Check recent errors"
ERROR_COUNT=$(grep -c ERROR logs/api_services_*.log 2>/dev/null || echo "0")
echo "    $ERROR_COUNT errors in logs"

# Model status
echo "[ ] Verify models loaded"
MODEL_COUNT=$(curl -s http://localhost:8000/models | jq '. | length' 2>/dev/null || echo "0")
echo "    $MODEL_COUNT models loaded"

echo
echo "Checklist complete. Issues requiring attention:"
# Add logic to highlight problems
```

### Service Startup Order

Services must be started in the correct order due to dependencies:

```bash
#!/bin/bash
# startup_all_services.sh

echo "=== Starting All Services ==="

# 1. PostgreSQL (must be first)
echo "1. Starting PostgreSQL..."
if ! systemctl is-active --quiet postgresql; then
    sudo systemctl start postgresql
    sleep 5
fi

# 2. Ollama (needed for agents)
echo "2. Starting Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    ./manage_ollama.sh start
    sleep 3
fi

# 3. API Service (depends on DB and optionally Ollama)
echo "3. Starting API Service..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    ./start_api_service.sh
fi

# 4. Verify everything
echo "4. Verifying all services..."
sleep 5
./system_health_check.sh

# 5. Load models if needed
echo "5. Checking models..."
MODEL_COUNT=$(curl -s http://localhost:8000/models | jq '. | length' 2>/dev/null || echo "0")
if [ "$MODEL_COUNT" -eq "0" ]; then
    echo "No models loaded, loading from storage..."
    python api_client.py load-models
fi
```

### Quick Reference

**Service Ports**
- PostgreSQL: 5432
- API Service: 8000
- Ollama: 11434

**Key Files**
- API PID: `api_service.pid`
- Ollama PID: `ollama.pid`
- Latest API log: `logs/api_services_*.log` (most recent)
- Config: `config/config.yaml`

**Emergency Commands**
```bash
# Kill everything
pkill -f api_services.py; pkill -f "ollama serve"

# Check what's using ports
lsof -i :8000
lsof -i :11434
lsof -i :5432

# Force restart everything
./emergency_recovery.sh

# Quick health check
curl http://localhost:8000/health
```

**Log Locations**
- API logs: `./logs/api_services_*.log`
- Ollama logs: `./logs/ollama.log`
- PostgreSQL logs: `/var/log/postgresql/postgresql-*.log`

**Common Issues**
- Port already in use: Kill the process using `lsof -t -i :PORT | xargs kill -9`
- Database connection refused: Check PostgreSQL is running and pg_hba.conf allows connections
- Ollama not responding: Usually needs a restart with `ollama serve`
- Models not loading: Run `python api_client.py load-models`
- Agent analysis failing: Verify Ollama is running and Mistral model is installed

### Service Recovery Procedures

#### Emergency Service Recovery

When the system is completely down, this script performs a full recovery:

```bash
#!/bin/bash
# emergency_recovery.sh

echo "=== Emergency Service Recovery ==="

# 1. Stop everything
echo "1. Stopping all services..."
pkill -f api_services.py
pkill -f "ollama serve"
sudo systemctl stop postgresql

sleep 3

# 2. Clear any locks/temp files
echo "2. Clearing locks and temp files..."
rm -f api_service.pid ollama.pid
rm -f /tmp/.s.PGSQL.5432*

# 3. Start PostgreSQL
echo "3. Starting PostgreSQL..."
sudo systemctl start postgresql
sleep 5

# 4. Verify database
echo "4. Verifying database..."
PGPASSWORD="XXXXX" psql -h localhost -p 5432 -U anomaly_user -d anomaly_detection -c "SELECT 1;"
if [ $? -ne 0 ]; then
    echo "Database connection failed! Check PostgreSQL logs."
    exit 1
fi

# 5. Start Ollama
echo "5. Starting Ollama..."
nohup ollama serve > logs/ollama.log 2>&1 &
sleep 3

# 6. Start API Service
echo "6. Starting API Service..."
./start_api_service.sh

# 7. Final verification
echo "7. Final system check..."
sleep 5
./system_health_check.sh
```

#### Service Dependencies Check

This script verifies all required dependencies are installed:

```bash
#!/bin/bash
# check_dependencies.sh

echo "=== Checking Service Dependencies ==="

# Python packages
echo "Python packages:"
pip list | grep -E "fastapi|uvicorn|psycopg2|scikit-learn|tensorflow|torch|pyyaml|ollama" | awk '{printf "  %-20s %s\n", $1, $2}'

# System packages
echo -e "\nSystem packages:"
for pkg in postgresql postgresql-contrib python3-pip python3-dev build-essential; do
    if dpkg -l | grep -q "^ii  $pkg"; then
        echo "  ✓ $pkg"
    else
        echo "  ✗ $pkg (run: sudo apt-get install $pkg)"
    fi
done

# Directory structure
echo -e "\nRequired directories:"
for dir in config data logs storage storage/models storage/anomalies; do
    if [ -d "$dir" ]; then
        echo "  ✓ $dir"
    else
        echo "  ✗ $dir (run: mkdir -p $dir)"
    fi
done
```

This comprehensive guide provides system administrators with all the tools and knowledge needed to successfully deploy, operate, and maintain the Anomaly Detection System. Each script and component has been documented with its purpose, usage, and importance to the overall system operation.