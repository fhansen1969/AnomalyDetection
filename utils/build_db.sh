#!/usr/bin/env bash
################################################################################
# Database Build Script - Complete Schema with Remote PostgreSQL Support
# - Reads configuration from config/config.yaml
# - Password-aware for remote connections (no prompts)
# - Creates comprehensive schema matching UI requirements
# - Cross-platform compatible (macOS + Linux)
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${1:-config/config.yaml}"

# Database configuration (will be loaded from config.yaml or use defaults)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-anomaly_detection}"
DB_USER="${DB_USER:-anomaly_user}"
DB_PASSWORD="${DB_PASSWORD:-St@rW@rs1}"

################################################################################
# Helper Functions
################################################################################

log() {
    printf "${BLUE}[INFO]${NC} %s\n" "$1"
}

success() {
    printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"
}

warn() {
    printf "${YELLOW}[WARN]${NC} %s\n" "$1"
}

error() {
    printf "${RED}[ERROR]${NC} %s\n" "$1"
}

die() {
    error "$1"
    exit 1
}

debug() {
    if [ "${DEBUG:-false}" = "true" ]; then
        printf "${CYAN}[DEBUG]${NC} %s\n" "$1"
    fi
}

################################################################################
# Configuration Parsing
################################################################################

parse_config_file() {
    local config_file="$1"
    
    if [ ! -f "$config_file" ]; then
        warn "Config file not found: $config_file"
        warn "Using environment variables or defaults"
        return 0
    fi
    
    log "Loading configuration from: $config_file"
    
    # Extract database configuration using grep and sed (works on macOS)
    # Strip comments (everything after #) and trim whitespace
    local temp_host=$(grep -A10 "^storage:" "$config_file" | grep -A10 "postgresql:" | grep "host:" | head -1 | sed 's/.*host: *//' | sed 's/#.*//' | tr -d '"' | tr -d "'" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    local temp_port=$(grep -A10 "^storage:" "$config_file" | grep -A10 "postgresql:" | grep "port:" | head -1 | sed 's/.*port: *//' | sed 's/#.*//' | tr -d '"' | tr -d "'" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    local temp_db=$(grep -A10 "^storage:" "$config_file" | grep -A10 "postgresql:" | grep "database:" | head -1 | sed 's/.*database: *//' | sed 's/#.*//' | tr -d '"' | tr -d "'" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    local temp_user=$(grep -A10 "^storage:" "$config_file" | grep -A10 "postgresql:" | grep "user:" | head -1 | sed 's/.*user: *//' | sed 's/#.*//' | tr -d '"' | tr -d "'" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    local temp_pass=$(grep -A10 "^storage:" "$config_file" | grep -A10 "postgresql:" | grep "password:" | head -1 | sed 's/.*password: *//' | sed 's/#.*//' | tr -d '"' | tr -d "'" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    
    # Update if found in config
    [ -n "$temp_host" ] && DB_HOST="$temp_host"
    [ -n "$temp_port" ] && DB_PORT="$temp_port"
    [ -n "$temp_db" ] && DB_NAME="$temp_db"
    [ -n "$temp_user" ] && DB_USER="$temp_user"
    [ -n "$temp_pass" ] && DB_PASSWORD="$temp_pass"
    
    debug "Extracted config values:"
    debug "  DB_HOST='$DB_HOST'"
    debug "  DB_PORT='$DB_PORT'"
    debug "  DB_NAME='$DB_NAME'"
    debug "  DB_USER='$DB_USER'"
    debug "  DB_PASSWORD='${DB_PASSWORD:0:3}***' (first 3 chars)"
    
    success "Configuration loaded"
}

################################################################################
# Directory Structure
################################################################################

create_directories() {
    log "Creating directory structure..."
    
    local directories=(
        # Data directories
        "data/training"
        "data/validation"
        "data/test"
        "data/raw"
        "data/input"
        "data/processed/training"
        "data/processed/validation"
        "data/processed/test"
        "data/processed/detection"
        
        # Storage directories
        "storage/models"
        "storage/models/training"
        "storage/models/validation"
        "storage/models/test"
        "storage/models/validated"
        "storage/anomalies"
        "storage/processed"
        "storage/state"
        "storage/backups/full"
        "storage/backups/schema"
        "storage/backups/incremental"
        "storage/alerts"
        "storage/correlations"
        
        # Log directories
        "logs/master_pipeline"
        "logs/training_pipeline"
        "logs/validation_pipeline"
        "logs/test_pipeline"
        "logs/detection_pipeline"
        "logs/api"
        
        # Report directories
        "reports/training"
        "reports/validation"
        "reports/test"
        "reports/detection"
        
        # Configuration backup
        "config/backups"
        
        # Results
        "results"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$PROJECT_ROOT/$dir"
    done
    
    success "Directory structure created (${#directories[@]} directories)"
}

################################################################################
# PostgreSQL Detection
################################################################################

check_postgres() {
    log "Checking PostgreSQL availability..."
    
    if ! command -v psql &> /dev/null; then
        die "PostgreSQL client (psql) not found. Please install PostgreSQL."
    fi
    
    # Get PostgreSQL client version
    local pg_version=$(psql --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
    log "PostgreSQL client version: $pg_version"
    
    # Try to find a working superuser (WITH PASSWORD for all attempts)
    local PG_SUPERUSER=""
    
    # Try postgres user first
    if PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -d postgres -c "SELECT 1" &> /dev/null; then
        PG_SUPERUSER="postgres"
    # Try current user
    elif PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$(whoami)" -d postgres -c "SELECT 1" &> /dev/null; then
        PG_SUPERUSER="$(whoami)"
    # Try without specifying user (use default)
    elif PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -d postgres -c "SELECT 1" &> /dev/null; then
        PG_SUPERUSER=""
    else
        die "Cannot connect to PostgreSQL at $DB_HOST:$DB_PORT (check credentials)"
    fi
    
    # Export for use in other functions
    export PG_SUPERUSER
    
    if [ -n "$PG_SUPERUSER" ]; then
        log "Using PostgreSQL superuser: $PG_SUPERUSER"
    else
        log "Using default PostgreSQL authentication"
    fi
    
    success "PostgreSQL is available"
}

################################################################################
# Database Creation
################################################################################

create_database() {
    log "Creating database and user..."
    
    # Use detected superuser or empty string for default
    local PSQL_USER_FLAG=""
    if [ -n "$PG_SUPERUSER" ]; then
        PSQL_USER_FLAG="-U $PG_SUPERUSER"
    fi
    
    # Check if database exists (WITH PASSWORD)
    if PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" $PSQL_USER_FLAG -d postgres -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        warn "Database $DB_NAME already exists"
        read -p "Drop and recreate? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Dropping existing database..."
            
            # Terminate connections (WITH PASSWORD)
            PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" $PSQL_USER_FLAG -d postgres << EOF 2>/dev/null || true
SELECT pg_terminate_backend(pg_stat_activity.pid) 
FROM pg_stat_activity 
WHERE pg_stat_activity.datname = '$DB_NAME' 
  AND pid <> pg_backend_pid();
EOF
            
            sleep 1
            
            # Drop database (WITH PASSWORD)
            if [ -n "$PG_SUPERUSER" ]; then
                PGPASSWORD="${DB_PASSWORD}" dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" "$DB_NAME" 2>/dev/null || \
                PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" $PSQL_USER_FLAG -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
            else
                PGPASSWORD="${DB_PASSWORD}" dropdb -h "$DB_HOST" -p "$DB_PORT" "$DB_NAME" 2>/dev/null || \
                PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
            fi
            
            success "Dropped existing database"
        else
            log "Using existing database"
            return 0
        fi
    fi
    
    # Create user if doesn't exist (WITH PASSWORD)
    PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" $PSQL_USER_FLAG -d postgres << EOF 2>/dev/null || true
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
        RAISE NOTICE 'Created user: $DB_USER';
    ELSE
        RAISE NOTICE 'User already exists: $DB_USER';
    END IF;
END
\$\$;
EOF
    
    # Create database (WITH PASSWORD)
    if [ -n "$PG_SUPERUSER" ]; then
        PGPASSWORD="${DB_PASSWORD}" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" -O "$DB_USER" "$DB_NAME" 2>/dev/null || \
        PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" $PSQL_USER_FLAG -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
    else
        PGPASSWORD="${DB_PASSWORD}" createdb -h "$DB_HOST" -p "$DB_PORT" -O "$DB_USER" "$DB_NAME" 2>/dev/null || \
        PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
    fi
    
    # Grant privileges (WITH PASSWORD)
    PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" $PSQL_USER_FLAG -d "$DB_NAME" << EOF
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
GRANT ALL ON SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
EOF
    
    success "Database created"
}

################################################################################
# Table Creation
################################################################################

create_tables() {
    log "Creating database tables..."
    
    # WITH PASSWORD
    PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<'EOF'

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables if recreating
-- (Uncomment if you want to force recreation)
-- DROP TABLE IF EXISTS agent_messages CASCADE;
-- DROP TABLE IF EXISTS agent_activities CASCADE;
-- DROP TABLE IF EXISTS anomaly_analysis CASCADE;
-- DROP TABLE IF EXISTS anomalies CASCADE;
-- DROP TABLE IF EXISTS models CASCADE;
-- DROP TABLE IF EXISTS system_status CASCADE;
-- DROP TABLE IF EXISTS jobs CASCADE;
-- DROP TABLE IF EXISTS processed_data CASCADE;
-- DROP TABLE IF EXISTS model_states CASCADE;
-- DROP TABLE IF EXISTS processors CASCADE;
-- DROP TABLE IF EXISTS collectors CASCADE;
-- DROP TABLE IF EXISTS background_jobs CASCADE;
-- DROP TABLE IF EXISTS vector_embeddings CASCADE;

-- ============================================================================
-- MODELS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'not_trained',
    config JSONB DEFAULT '{}',
    performance JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}',
    training_time VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_models_name ON models(name);
CREATE INDEX IF NOT EXISTS idx_models_status ON models(status);
CREATE INDEX IF NOT EXISTS idx_models_type ON models(type);

-- ============================================================================
-- ANOMALIES TABLE (COMPREHENSIVE SCHEMA)
-- ============================================================================
CREATE TABLE IF NOT EXISTS anomalies (
    id VARCHAR(255) PRIMARY KEY,
    anomaly_id VARCHAR(255) UNIQUE,
    model_id INTEGER REFERENCES models(id),
    model VARCHAR(255),
    model_name VARCHAR(255),
    score FLOAT NOT NULL,
    anomaly_score FLOAT,
    threshold FLOAT DEFAULT 0.5,
    timestamp TIMESTAMP NOT NULL,
    detection_time TIMESTAMP NOT NULL,
    location VARCHAR(255),
    src_ip VARCHAR(50),
    dst_ip VARCHAR(50),
    type VARCHAR(255),
    details JSONB DEFAULT '{}',
    features JSONB DEFAULT '[]',
    analysis JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'detected',
    severity VARCHAR(50),
    data JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_anomalies_model ON anomalies(model);
CREATE INDEX IF NOT EXISTS idx_anomalies_model_name ON anomalies(model_name);
CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_detection_time ON anomalies(detection_time DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_status ON anomalies(status);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity);
CREATE INDEX IF NOT EXISTS idx_anomalies_score ON anomalies(score DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_anomaly_id ON anomalies(anomaly_id);

-- ============================================================================
-- ANOMALY ANALYSIS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS anomaly_analysis (
    id SERIAL PRIMARY KEY,
    anomaly_id VARCHAR(255) REFERENCES anomalies(id) ON DELETE CASCADE,
    model VARCHAR(255),
    score FLOAT,
    timestamp TIMESTAMP DEFAULT NOW(),
    analysis_content JSONB DEFAULT '{}',
    remediation_content JSONB DEFAULT '{}',
    reflection_content JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_analysis_anomaly_id ON anomaly_analysis(anomaly_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_analysis_timestamp ON anomaly_analysis(timestamp DESC);

-- ============================================================================
-- AGENT MESSAGES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_messages (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE,
    anomaly_id VARCHAR(255) REFERENCES anomalies(id) ON DELETE SET NULL,
    agent_id VARCHAR(100),
    agent VARCHAR(100),
    agent_name VARCHAR(255),
    message TEXT,
    content TEXT,
    role VARCHAR(50),
    message_type VARCHAR(50) DEFAULT 'info',
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB,
    job_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_anomaly_id ON agent_messages(anomaly_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_agent ON agent_messages(agent);
CREATE INDEX IF NOT EXISTS idx_agent_messages_timestamp ON agent_messages(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_messages_job_id ON agent_messages(job_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_message_id ON agent_messages(message_id);

-- ============================================================================
-- AGENT ACTIVITIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_activities (
    id SERIAL PRIMARY KEY,
    activity_id VARCHAR(255) UNIQUE,
    anomaly_id VARCHAR(255) REFERENCES anomalies(id) ON DELETE SET NULL,
    agent_id VARCHAR(100),
    agent VARCHAR(100),
    agent_name VARCHAR(255),
    activity_type VARCHAR(100),
    action VARCHAR(255),
    description TEXT,
    status VARCHAR(50),
    timestamp TIMESTAMP NOT NULL,
    details JSONB DEFAULT '{}',
    data JSONB,
    job_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_activities_anomaly_id ON agent_activities(anomaly_id);
CREATE INDEX IF NOT EXISTS idx_agent_activities_agent ON agent_activities(agent);
CREATE INDEX IF NOT EXISTS idx_agent_activities_timestamp ON agent_activities(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_activities_job_id ON agent_activities(job_id);
CREATE INDEX IF NOT EXISTS idx_agent_activities_activity_id ON agent_activities(activity_id);

-- ============================================================================
-- SYSTEM STATUS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS system_status (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_status_key ON system_status(key);

-- ============================================================================
-- JOBS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    job_type VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending',
    progress FLOAT DEFAULT 0,
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    result JSONB,
    results JSONB,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_updated_at ON jobs(updated_at DESC);

-- ============================================================================
-- PROCESSED DATA TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS processed_data (
    id SERIAL PRIMARY KEY,
    data_id VARCHAR(255) UNIQUE NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    source VARCHAR(255),
    collector VARCHAR(255),
    raw_data JSONB,
    processed_data JSONB,
    data JSONB NOT NULL,
    features JSONB,
    batch_id VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processed_data_timestamp ON processed_data(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_processed_data_source ON processed_data(source);
CREATE INDEX IF NOT EXISTS idx_processed_data_collector ON processed_data(collector);
CREATE INDEX IF NOT EXISTS idx_processed_data_batch_id ON processed_data(batch_id);
CREATE INDEX IF NOT EXISTS idx_processed_data_data_id ON processed_data(data_id);
CREATE INDEX IF NOT EXISTS idx_processed_data_created ON processed_data(created_at);

-- ============================================================================
-- MODEL STATES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_states (
    model_name VARCHAR(255) PRIMARY KEY,
    model_type VARCHAR(255) NOT NULL,
    state JSONB NOT NULL,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_states_model_name ON model_states(model_name);
CREATE INDEX IF NOT EXISTS idx_model_states_model_type ON model_states(model_type);

-- ============================================================================
-- PROCESSORS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS processors (
    id SERIAL PRIMARY KEY,
    processor_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'inactive',
    config JSONB DEFAULT '{}',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processors_processor_id ON processors(processor_id);
CREATE INDEX IF NOT EXISTS idx_processors_status ON processors(status);
CREATE INDEX IF NOT EXISTS idx_processors_type ON processors(type);

-- ============================================================================
-- COLLECTORS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS collectors (
    id SERIAL PRIMARY KEY,
    collector_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'inactive',
    config JSONB DEFAULT '{}',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_collectors_collector_id ON collectors(collector_id);
CREATE INDEX IF NOT EXISTS idx_collectors_status ON collectors(status);

-- ============================================================================
-- BACKGROUND JOBS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS background_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    job_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    parameters JSONB DEFAULT '{}',
    result JSONB,
    progress FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_background_jobs_job_id ON background_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_background_jobs_status ON background_jobs(status);
CREATE INDEX IF NOT EXISTS idx_background_jobs_job_type ON background_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_background_jobs_created_at ON background_jobs(created_at DESC);

-- ============================================================================
-- VECTOR EMBEDDINGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS vector_embeddings (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(255) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    embedding_vector FLOAT[] NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vector_embeddings_entity_id ON vector_embeddings(entity_id);
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_entity_type ON vector_embeddings(entity_type);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS update_anomalies_updated_at ON anomalies;
CREATE TRIGGER update_anomalies_updated_at 
    BEFORE UPDATE ON anomalies 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_jobs_updated_at ON jobs;
CREATE TRIGGER update_jobs_updated_at 
    BEFORE UPDATE ON jobs 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_models_updated_at ON models;
CREATE TRIGGER update_models_updated_at 
    BEFORE UPDATE ON models 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Recent anomalies view
CREATE OR REPLACE VIEW recent_anomalies AS
SELECT 
    id,
    anomaly_id,
    timestamp,
    model,
    model_name,
    score,
    severity,
    status,
    created_at
FROM anomalies
ORDER BY timestamp DESC
LIMIT 100;

-- Job statistics view
CREATE OR REPLACE VIEW job_statistics AS
SELECT 
    status,
    COUNT(*) as count,
    AVG(progress) as avg_progress,
    MIN(created_at) as first_job,
    MAX(created_at) as last_job
FROM jobs
GROUP BY status;

-- Model summary view
CREATE OR REPLACE VIEW model_summary AS
SELECT 
    name,
    type,
    status,
    COALESCE(metrics->>'accuracy', '0')::FLOAT as accuracy,
    COALESCE(metrics->>'f1_score', '0')::FLOAT as f1_score,
    updated_at
FROM models
ORDER BY name;

SELECT 'All tables created successfully!' as status;
EOF
    
    if [ $? -eq 0 ]; then
        success "Database tables created"
    else
        die "Failed to create database tables"
    fi
}

################################################################################
# Populate Essential Data
################################################################################

populate_essential_data() {
    log "Populating essential configuration data..."
    
    PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<'EOF'

-- Insert model configurations
INSERT INTO models (name, type, status, config, performance, metrics) VALUES
('isolation_forest_model', 'IsolationForestModel', 'not_trained', 
    '{"contamination": 0.05, "n_estimators": 100, "random_state": 42}'::jsonb,
    '{}'::jsonb, '{}'::jsonb),
('statistical_model', 'StatisticalModel', 'not_trained',
    '{"window_size": 10, "threshold_multiplier": 3.0}'::jsonb,
    '{}'::jsonb, '{}'::jsonb),
('autoencoder_model', 'AutoencoderModel', 'not_trained',
    '{"hidden_dims": [128, 64, 32, 64, 128], "activation": "relu", "dropout_rate": 0.2, "learning_rate": 0.001, "epochs": 50, "batch_size": 32}'::jsonb,
    '{}'::jsonb, '{}'::jsonb),
('gan_model', 'GANAnomalyDetector', 'not_trained',
    '{"latent_dim": 100, "epochs": 100, "batch_size": 32, "learning_rate": 0.0002, "beta_1": 0.5, "dropout_rate": 0.3, "random_state": 42, "detection_strategy": "reconstruction"}'::jsonb,
    '{}'::jsonb, '{}'::jsonb),
('one_class_svm_model', 'OneClassSVMModel', 'not_trained',
    '{"kernel": "rbf", "nu": 0.01, "gamma": "scale"}'::jsonb,
    '{}'::jsonb, '{}'::jsonb),
('ensemble_model', 'EnsembleModel', 'not_trained',
    '{"weights": {"isolation_forest": 0.6, "statistical": 0.4, "autoencoder": 0.5, "gan": 0.3, "one_class_svm": 0.5}, "models_to_use": ["isolation_forest", "statistical", "autoencoder", "one_class_svm"], "threshold": 0.5}'::jsonb,
    '{}'::jsonb, '{}'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- Insert processor configurations
INSERT INTO processors (processor_id, name, type, status, config, description) VALUES
('processor-1', 'generic_normalizer', 'normalizer', 'active', 
    '{"type": "json", "flatten_nested": true}'::jsonb,
    'Generic JSON Data Normalizer'),
('processor-2', 'system_metrics_extractor', 'feature_extractor', 'active',
    '{"feature_fields": [], "numerical_fields": [], "categorical_fields": [], "boolean_fields": [], "text_fields": []}'::jsonb,
    'System Metrics Feature Extractor'),
('processor-3', 'data_validator', 'validator', 'active',
    '{"required_fields": ["timestamp"], "data_types": {"timestamp": "string"}}'::jsonb,
    'Data Validation Processor'),
('processor-4', 'timestamp_normalizer', 'normalizer', 'active',
    '{"timestamp_field": "timestamp", "output_format": "iso8601"}'::jsonb,
    'Timestamp Normalization Processor'),
('processor-5', 'outlier_filter', 'filter', 'inactive',
    '{"threshold": 3.0, "method": "zscore"}'::jsonb,
    'Statistical Outlier Filter')
ON CONFLICT (processor_id) DO NOTHING;

-- Insert collector configurations
INSERT INTO collectors (collector_id, name, status, config, description) VALUES
('collector-1', 'api_collector', 'active', 
    '{"endpoint": "/api/collect", "auth_type": "bearer", "batch_size": 100}'::jsonb,
    'API Data Collector'),
('collector-2', 'file_collector', 'active',
    '{"paths": ["data/input/", "data/input/*.json"], "watch_interval_seconds": 60, "batch_size": 100, "file_pattern": "*.json", "recursive": true}'::jsonb,
    'File Data Collector'),
('collector-3', 'stream_collector', 'active',
    '{"protocol": "kafka", "topics": ["anomaly-stream"], "consumer_group": "anomaly_detection"}'::jsonb,
    'Stream Data Collector'),
('collector-4', 'backup_collector', 'inactive',
    '{"source": "archive", "compression": "gzip"}'::jsonb,
    'Backup Collector')
ON CONFLICT (collector_id) DO NOTHING;

-- Insert system status
INSERT INTO system_status (key, value) VALUES
('status', '{
    "initialized": true,
    "api_available": true,
    "uptime": "0d 0h 0m",
    "hostname": "anomaly-detector-01",
    "platform": "Linux",
    "platform_version": "5.15.0-91-generic",
    "last_update": "2025-11-13 00:00:00",
    "system_load": {
        "cpu": 15.2,
        "memory": 42.8,
        "disk": 28.5,
        "network": 12.3
    },
    "storage": {
        "initialized": true,
        "type": "PostgreSQL",
        "usage": 28.5,
        "total_space": "500GB",
        "used_space": "142.5GB"
    },
    "jobs": {
        "total": 0,
        "running": 0,
        "completed": 0,
        "failed": 0
    },
    "models": {
        "count": 6,
        "trained": 0,
        "names": ["isolation_forest_model", "one_class_svm_model", "autoencoder_model", "statistical_model", "ensemble_model", "gan_model"],
        "accuracy": 0.0
    },
    "processors": {
        "count": 5,
        "active": 4,
        "names": ["processor-1", "processor-2", "processor-3", "processor-4", "processor-5"]
    },
    "collectors": {
        "count": 4,
        "active": 3,
        "names": ["collector-1", "collector-2", "collector-3", "collector-4"]
    }
}'::jsonb)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

SELECT 'Essential configuration data populated successfully!' as status;
EOF
    
    if [ $? -eq 0 ]; then
        success "Essential configuration data populated"
    else
        warn "Some data may already exist (this is normal)"
    fi
}

################################################################################
# Verification
################################################################################

verify_installation() {
    log "Verifying installation..."
    
    # Check tables exist (WITH PASSWORD)
    local table_count
    table_count=$(PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
    
    log "Tables created: $table_count"
    
    # Verify critical columns exist
    local critical_checks=0
    local passed_checks=0
    
    # Check anomalies.model_name
    ((critical_checks++))
    if PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT 1 FROM information_schema.columns WHERE table_name='anomalies' AND column_name='model_name'" | grep -q 1; then
        success "✓ anomalies.model_name column exists"
        ((passed_checks++))
    else
        error "✗ anomalies.model_name column missing"
    fi
    
    # Check anomalies.severity
    ((critical_checks++))
    if PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT 1 FROM information_schema.columns WHERE table_name='anomalies' AND column_name='severity'" | grep -q 1; then
        success "✓ anomalies.severity column exists"
        ((passed_checks++))
    else
        error "✗ anomalies.severity column missing"
    fi
    
    # Check anomalies.status
    ((critical_checks++))
    if PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT 1 FROM information_schema.columns WHERE table_name='anomalies' AND column_name='status'" | grep -q 1; then
        success "✓ anomalies.status column exists"
        ((passed_checks++))
    else
        error "✗ anomalies.status column missing"
    fi
    
    # Check jobs.job_id (CRITICAL!)
    ((critical_checks++))
    if PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='job_id'" | grep -q 1; then
        success "✓✓✓ jobs.job_id column exists (CRITICAL)"
        ((passed_checks++))
    else
        error "✗✗✗ jobs.job_id column missing (CRITICAL - will cause errors)"
    fi
    
    if [ $passed_checks -eq $critical_checks ]; then
        success "Installation verified ($passed_checks/$critical_checks checks passed)"
        return 0
    else
        error "Installation verification failed ($passed_checks/$critical_checks checks passed)"
        return 1
    fi
}

################################################################################
# Display Summary
################################################################################

display_summary() {
    log "Database Summary:"
    echo ""
    
    PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT 
        CASE 
            WHEN sort_order = 1 THEN '==================================='
            WHEN sort_order = 3 THEN 'Models: ' || count::text
            WHEN sort_order = 4 THEN '  Trained: ' || count::text
            WHEN sort_order = 5 THEN '  Not trained: ' || count::text
            WHEN sort_order = 6 THEN 'Processors: ' || count::text
            WHEN sort_order = 7 THEN '  Active: ' || count::text
            WHEN sort_order = 8 THEN 'Collectors: ' || count::text
            WHEN sort_order = 9 THEN '  Active: ' || count::text
            WHEN sort_order = 10 THEN 'Jobs: ' || count::text
            ELSE ''
        END as summary
    FROM (
        SELECT 1 as sort_order, '' as label, 0 as count
        UNION ALL SELECT 3, 'models', COUNT(*) FROM models
        UNION ALL SELECT 4, 'trained', COUNT(*) FROM models WHERE status = 'trained'
        UNION ALL SELECT 5, 'not_trained', COUNT(*) FROM models WHERE status = 'not_trained'
        UNION ALL SELECT 6, 'processors', COUNT(*) FROM processors
        UNION ALL SELECT 7, 'active_proc', COUNT(*) FROM processors WHERE status = 'active'
        UNION ALL SELECT 8, 'collectors', COUNT(*) FROM collectors
        UNION ALL SELECT 9, 'active_coll', COUNT(*) FROM collectors WHERE status = 'active'
        UNION ALL SELECT 10, 'jobs', COUNT(*) FROM jobs
    ) sub
    ORDER BY sort_order
    " 2>/dev/null || echo "Could not retrieve summary"
}

create_env_file() {
    log "Creating .env file..."
    
    local env_file="$PROJECT_ROOT/.env"
    
    if [ -f "$env_file" ]; then
        warn ".env file already exists"
        return 0
    fi
    
    cat > "$env_file" << EOF
# Database Configuration
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Config Path
CONFIG_PATH=config/config.yaml
EOF
    
    success ".env file created"
}

################################################################################
# Main Function
################################################################################

main() {
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║   ANOMALY DETECTION DATABASE BUILD - COMPREHENSIVE    ║"
    echo "║   Password-aware • Complete Schema • Config Support   ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    
    cd "$PROJECT_ROOT"
    
    # Parse configuration
    parse_config_file "$CONFIG_FILE"
    
    log "Configuration:"
    log "  Database: $DB_NAME"
    log "  Host: $DB_HOST:$DB_PORT"
    log "  User: $DB_USER"
    log "  Config: $CONFIG_FILE"
    
    if [ "$DB_PASSWORD" = "St@rW@rs1" ] || [ "$DB_PASSWORD" = "St@rW@rs!" ]; then
        warn "Using default password - change for production!"
    fi
    
    echo ""
    
    # Execute build steps
    check_postgres
    echo ""
    
    create_directories
    echo ""
    
    create_database
    echo ""
    
    create_tables
    echo ""
    
    populate_essential_data
    echo ""
    
    verify_installation || warn "Verification had issues"
    echo ""
    
    create_env_file
    echo ""
    
    display_summary
    echo ""
    
    success "Build completed successfully!"
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║  Database and Directory Structure Ready                ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    echo "Next steps:"
    echo "  1. Start API: python api_services.py --config config/config.yaml"
    echo "  2. Initialize system: curl -X POST http://localhost:8000/init"
    echo "  3. Access UI: streamlit run app.py"
    echo ""
    echo "Database connection:"
    echo "  postgresql://$DB_USER:****@$DB_HOST:$DB_PORT/$DB_NAME"
    echo ""
}

################################################################################
# Argument Parsing
################################################################################

show_help() {
    cat << EOF
Usage: $0 [config_file] [options]

Arguments:
  config_file           Path to config.yaml (default: config/config.yaml)

Options:
  --skip-db            Skip database creation (directories only)
  --skip-dirs          Skip directory creation (database only)
  --skip-data          Skip populating essential data
  --help               Show this help message

Environment Variables:
  DB_HOST              Database host (default: localhost)
  DB_PORT              Database port (default: 5432)
  DB_NAME              Database name (default: anomaly_detection)
  DB_USER              Database user (default: anomaly_user)
  DB_PASSWORD          Database password (default: St@rW@rs1)

Examples:
  $0                              # Use config/config.yaml
  $0 config/production.yaml       # Use custom config
  
  # Remote database
  DB_HOST=db.example.com DB_PASSWORD=secret $0
  
  # Skip data population
  $0 --skip-data

EOF
}

# Parse arguments
SKIP_DB=false
SKIP_DIRS=false
SKIP_DATA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-db)
            SKIP_DB=true
            shift
            ;;
        --skip-dirs)
            SKIP_DIRS=true
            shift
            ;;
        --skip-data)
            SKIP_DATA=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            if [[ -f "$1" ]]; then
                CONFIG_FILE="$1"
            fi
            shift
            ;;
    esac
done

# Run main or partial builds
if [ "$SKIP_DB" = true ]; then
    parse_config_file "$CONFIG_FILE"
    create_directories
    success "Directories created (database skipped)"
elif [ "$SKIP_DIRS" = true ]; then
    parse_config_file "$CONFIG_FILE"
    check_postgres
    create_database
    create_tables
    [ "$SKIP_DATA" != "true" ] && populate_essential_data
    verify_installation
    success "Database created (directories skipped)"
else
    main
fi