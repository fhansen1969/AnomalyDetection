"""
Initialize the database with schema and sample data for the Anomaly Detection Dashboard.
"""

import os
import sys
import yaml
import psycopg2
import json
import random
import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path to fix module imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Load configuration from YAML file
def load_config():
    """Load configuration from YAML file."""
    config_path = os.path.join(project_root, '../config', 'config.yaml')
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except Exception as e:
        logger.error(f"Error loading config file: {e}")
        return None

def init_database():
    """Initialize the database with schema and sample data."""
    logger.info("Initializing database...")
    
    # Load configuration
    config = load_config()
    
    if not config:
        logger.error("Could not load configuration. Using default database settings.")
        db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "anomaly_detection",
            "user": "anomaly_user",
            "password": "St@rW@rs!"
        }
    else:
        db_config = config['config']['database']['connection']
        logger.info(f"Loaded database configuration: {db_config}")
    
    # Connect to database
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"]
        )
        
        # Set autocommit to create the database if it doesn't exist
        conn.autocommit = True
        
        cursor = conn.cursor()
        logger.info("Connected to database successfully")
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        logger.info("Please make sure the PostgreSQL server is running and the database exists.")
        return False
    
    try:
        # Read schema SQL
        schema_sql = get_schema_sql()
        
        # Execute schema SQL
        cursor.execute(schema_sql)
        conn.commit()
        logger.info("Schema created successfully")
        
        # Insert sample models
        insert_sample_models(cursor, config)
        
        # Insert sample anomalies
        insert_sample_anomalies(cursor)
        
        # Insert sample jobs
        insert_sample_jobs(cursor)
        
        # Commit all changes
        conn.commit()
        logger.info("Sample data inserted successfully")
        
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing database: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_schema_sql():
    """Get the SQL schema definition."""
    schema_sql = """
    -- Database schema for Anomaly Detection Dashboard
    
    -- Models table
    CREATE TABLE IF NOT EXISTS models (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE,
        type VARCHAR(100) NOT NULL,
        status VARCHAR(50) DEFAULT 'not_trained',
        performance JSONB DEFAULT '{}',
        training_time VARCHAR(50),
        config JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Anomalies table
    CREATE TABLE IF NOT EXISTS anomalies (
        id VARCHAR(20) PRIMARY KEY,
        model_id INTEGER REFERENCES models(id),
        score REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        location VARCHAR(100),
        src_ip VARCHAR(50),
        dst_ip VARCHAR(50),
        analysis JSONB DEFAULT '{}',
        features JSONB DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Analysis results table
    CREATE TABLE IF NOT EXISTS anomaly_analysis (
        id SERIAL PRIMARY KEY,
        anomaly_id VARCHAR(20) REFERENCES anomalies(id),
        model VARCHAR(100),
        score REAL,
        timestamp TIMESTAMP,
        analysis_content JSONB DEFAULT '{}',
        remediation_content JSONB DEFAULT '{}',
        reflection_content JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Agent messages table
    CREATE TABLE IF NOT EXISTS agent_messages (
        id SERIAL PRIMARY KEY,
        anomaly_id VARCHAR(20) REFERENCES anomalies(id),
        agent VARCHAR(50) NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Agent activities table
    CREATE TABLE IF NOT EXISTS agent_activities (
        id SERIAL PRIMARY KEY,
        anomaly_id VARCHAR(20) REFERENCES anomalies(id),
        agent VARCHAR(50) NOT NULL,
        action VARCHAR(50) NOT NULL,
        status VARCHAR(50) NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        details JSONB DEFAULT '{}'
    );
    
    -- Jobs table
    CREATE TABLE IF NOT EXISTS jobs (
        id SERIAL PRIMARY KEY,
        type VARCHAR(50) NOT NULL,
        status VARCHAR(50) DEFAULT 'pending',
        parameters JSONB DEFAULT '{}',
        result JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    );
    
    -- System status table
    CREATE TABLE IF NOT EXISTS system_status (
        key VARCHAR(50) PRIMARY KEY,
        value JSONB NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Insert default system status
    INSERT INTO system_status (key, value) 
    VALUES ('status', 
    '{
        "initialized": true,
        "processors": {
            "count": 3,
            "names": ["normalizer", "feature_extractor", "dimensionality_reducer"],
            "active": 2
        },
        "collectors": {
            "count": 3,
            "names": ["file_collector", "kafka_collector", "api_collector"],
            "active": 3
        },
        "storage": {
            "initialized": true,
            "type": "postgresql",
            "usage": 68,
            "total_space": "500GB",
            "used_space": "340GB"
        },
        "system_load": {
            "cpu": 45,
            "memory": 62,
            "network": 38
        },
        "uptime": "5d 12h 43m"
    }')
    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
    
    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp);
    CREATE INDEX IF NOT EXISTS idx_anomalies_score ON anomalies(score);
    CREATE INDEX IF NOT EXISTS idx_model_status ON models(status);
    CREATE INDEX IF NOT EXISTS idx_agent_activities_timestamp ON agent_activities(timestamp);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    """
    
    return schema_sql

def insert_sample_models(cursor, config):
    """Insert sample model data from config."""
    logger.info("Inserting sample models...")
    
    # Check if config contains model information
    if not config or 'config' not in config or 'models' not in config['config']:
        # Use default models if config doesn't have any
        return insert_default_models(cursor)
    
    # Get models from config
    models_config = config['config']['models']
    enabled_models = models_config.get('enabled', [])
    
    models = []
    for model_type in enabled_models:
        if model_type in models_config:
            model_conf = models_config[model_type]
            
            # Create model entry
            model = {
                "name": f"{model_type}_model",
                "type": f"{model_type.title()}Model",
                "status": "trained" if model_type != "gan" else "not_trained",  # Example: make GAN not trained
                "performance": json.dumps({
                    "accuracy": random.uniform(0.85, 0.95),
                    "precision": random.uniform(0.83, 0.93),
                    "recall": random.uniform(0.85, 0.95),
                    "f1_score": random.uniform(0.84, 0.94)
                }),
                "training_time": f"{random.randint(1, 6)}h {random.randint(0, 59)}m",
                "config": json.dumps(model_conf)
            }
            
            models.append(model)
    
    # Insert models into database
    for model in models:
        cursor.execute("""
            INSERT INTO models (name, type, status, performance, training_time, config)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                type = EXCLUDED.type,
                status = EXCLUDED.status,
                performance = EXCLUDED.performance,
                training_time = EXCLUDED.training_time,
                config = EXCLUDED.config
        """, (
            model["name"],
            model["type"],
            model["status"],
            model["performance"],
            model["training_time"],
            model["config"]
        ))

def insert_default_models(cursor):
    """Insert default models when config is not available."""
    logger.info("Using default model configurations")
    
    models = [
        {
            "name": "isolation_forest_model",
            "type": "IsolationForestModel",
            "status": "trained",
            "performance": json.dumps({
                "accuracy": 0.92,
                "precision": 0.89,
                "recall": 0.94,
                "f1_score": 0.91
            }),
            "training_time": "2h 15m",
            "config": json.dumps({
                "contamination": 0.05,
                "n_estimators": 100,
                "random_state": 42
            })
        },
        {
            "name": "one_class_svm_model",
            "type": "OneClassSVMModel",
            "status": "trained",
            "performance": json.dumps({
                "accuracy": 0.87,
                "precision": 0.85,
                "recall": 0.88,
                "f1_score": 0.86
            }),
            "training_time": "3h 45m",
            "config": json.dumps({
                "kernel": "rbf",
                "nu": 0.01,
                "gamma": "scale"
            })
        },
        {
            "name": "ensemble_model",
            "type": "EnsembleModel",
            "status": "trained",
            "performance": json.dumps({
                "accuracy": 0.95,
                "precision": 0.93,
                "recall": 0.96,
                "f1_score": 0.94
            }),
            "training_time": "4h 30m",
            "config": json.dumps({
                "weights": {
                    "isolation_forest_model": 0.7,
                    "one_class_svm_model": 0.3
                }
            })
        },
        {
            "name": "autoencoder_model",
            "type": "AutoencoderModel",
            "status": "trained",
            "performance": json.dumps({
                "accuracy": 0.90,
                "precision": 0.88,
                "recall": 0.91,
                "f1_score": 0.89
            }),
            "training_time": "5h 20m",
            "config": json.dumps({
                "hidden_layers": [64, 32, 16, 32, 64],
                "activation": "relu",
                "epochs": 100
            })
        },
        {
            "name": "gan_model",
            "type": "GANModel",
            "status": "not_trained",
            "performance": json.dumps({
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0
            }),
            "training_time": "N/A",
            "config": json.dumps({
                "latent_dim": 100,
                "hidden_layers": [128, 256, 512],
                "activation": "leaky_relu"
            })
        }
    ]
    
    for model in models:
        cursor.execute("""
            INSERT INTO models (name, type, status, performance, training_time, config)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                type = EXCLUDED.type,
                status = EXCLUDED.status,
                performance = EXCLUDED.performance,
                training_time = EXCLUDED.training_time,
                config = EXCLUDED.config
        """, (
            model["name"],
            model["type"],
            model["status"],
            model["performance"],
            model["training_time"],
            model["config"]
        ))

def insert_sample_anomalies(cursor):
    """Insert sample anomaly data."""
    logger.info("Inserting sample anomalies...")
    
    # Get model IDs
    cursor.execute("SELECT id, name FROM models")
    models = {name: model_id for model_id, name in cursor.fetchall()}
    
    # Generate anomalies
    anomalies = []
    for i in range(200):
        model_name = random.choice(list(models.keys()))
        model_id = models[model_name]
        score = random.uniform(0.5, 0.95)
        
        # Determine severity based on score
        if score > 0.8:
            severity = "High"
        elif score > 0.6:
            severity = "Medium"
        else:
            severity = "Low"
        
        # Create timestamp within last 30 days
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        timestamp = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
        
        # Generate location data
        location = random.choice(["us-east", "us-west", "eu-central", "ap-south", "sa-east"])
        
        # Generate source and destination IPs
        src_ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
        dst_ip = f"10.0.{random.randint(1, 254)}.{random.randint(1, 254)}"
        
        # Generate features that contributed to anomaly
        features = []
        for _ in range(random.randint(1, 3)):
            feature = random.choice([
                "unusual_login_time", "high_data_transfer", "rare_destination",
                "suspicious_process", "unusual_network_activity", "unauthorized_access_attempt",
                "configuration_change", "privilege_escalation", "data_exfiltration",
                "unusual_protocol", "malformed_packet", "unusual_login_location"
            ])
            if feature not in features:
                features.append(feature)
        
        analysis = {
            "severity": severity,
            "content": f"Anomaly detected with score {score:.3f}",
            "features": features
        }
        
        anomalies.append({
            "id": f"ANOM-{i+1000}",
            "model_id": model_id,
            "score": score,
            "timestamp": timestamp,
            "location": location,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "analysis": json.dumps(analysis),
            "features": json.dumps(features)
        })
    
    # Insert anomalies
    for anomaly in anomalies:
        cursor.execute("""
            INSERT INTO anomalies (id, model_id, score, timestamp, location, src_ip, dst_ip, analysis, features)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                model_id = EXCLUDED.model_id,
                score = EXCLUDED.score,
                timestamp = EXCLUDED.timestamp,
                location = EXCLUDED.location,
                src_ip = EXCLUDED.src_ip,
                dst_ip = EXCLUDED.dst_ip,
                analysis = EXCLUDED.analysis,
                features = EXCLUDED.features
        """, (
            anomaly["id"],
            anomaly["model_id"],
            anomaly["score"],
            anomaly["timestamp"],
            anomaly["location"],
            anomaly["src_ip"],
            anomaly["dst_ip"],
            anomaly["analysis"],
            anomaly["features"]
        ))
        
        # For a few anomalies, create analysis results and agent messages
        if random.random() < 0.1:  # 10% of anomalies have analysis
            create_sample_analysis(cursor, anomaly)

def create_sample_analysis(cursor, anomaly):
    """Create sample analysis and agent messages for an anomaly."""
    anomaly_id = anomaly["id"]
    score = anomaly["score"]
    timestamp = anomaly["timestamp"]
    
    # Determine severity based on score
    if score > 0.8:
        severity = "Critical"
    elif score > 0.6:
        severity = "High"
    elif score > 0.4:
        severity = "Medium"
    else:
        severity = "Low"
    
    # Create analysis
    analysis_content = json.dumps({
        "severity": severity,
        "content": f"Anomaly detected with score {score:.3f} from model. This appears to be a potential security breach involving unauthorized access."
    })
    
    remediation_content = json.dumps({
        "content": f"Recommended actions for {severity.lower()} severity anomaly:\n1. Isolate the affected system immediately\n2. Block traffic from source IP\n3. Reset credentials for all accounts accessed\n4. Enable enhanced monitoring on the affected systems\n5. Review firewall rules and update access controls"
    })
    
    reflection_content = json.dumps({
        "content": f"This anomaly matches patterns seen in recent targeted attacks. The anomaly was detected with {score:.0%} confidence, which is {'very high' if score > 0.8 else 'moderate' if score > 0.6 else 'low'}."
    })
    
    # Insert analysis
    cursor.execute("""
        INSERT INTO anomaly_analysis (anomaly_id, model, score, timestamp, analysis_content, remediation_content, reflection_content)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        anomaly_id,
        "model",
        score,
        timestamp,
        analysis_content,
        remediation_content,
        reflection_content
    ))
    
    # Create agent messages
    agents = ["security_analyst", "remediation_expert", "reflection_expert", 
              "security_critic", "code_generator", "data_collector"]
    
    base_timestamp = timestamp + datetime.timedelta(minutes=random.randint(5, 30))
    
    for i, agent in enumerate(agents):
        message_timestamp = base_timestamp + datetime.timedelta(minutes=i*3)
        
        cursor.execute("""
            INSERT INTO agent_messages (anomaly_id, agent, content, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (
            anomaly_id,
            agent,
            f"Analyzing anomaly {anomaly_id} detected with score {score:.3f}",
            message_timestamp
        ))
        
        # Add agent activities
        cursor.execute("""
            INSERT INTO agent_activities (anomaly_id, agent, action, status, timestamp, details)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            anomaly_id,
            agent,
            "analyze",
            "completed",
            message_timestamp,
            json.dumps({"step": i+1, "total_steps": len(agents)})
        ))

def insert_sample_jobs(cursor):
    """Insert sample job data."""
    logger.info("Inserting sample jobs...")
    
    # Create job types
    job_types = ["model_training", "anomaly_detection", "system_maintenance", "data_collection"]
    job_statuses = ["running", "completed", "failed", "pending"]
    
    # Generate jobs
    for i in range(25):
        job_type = random.choice(job_types)
        job_status = random.choice(job_statuses)
        
        # Create timestamps
        created_at = datetime.datetime.now() - datetime.timedelta(
            days=random.randint(0, 10),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        
        updated_at = created_at + datetime.timedelta(
            minutes=random.randint(1, 60)
        )
        
        completed_at = updated_at if job_status in ["completed", "failed"] else None
        
        # Create parameters and results
        parameters = {}
        results = {}
        
        if job_type == "model_training":
            parameters = {
                "model_name": random.choice(["isolation_forest_model", "one_class_svm_model", "ensemble_model", "autoencoder_model"]),
                "dataset": random.choice(["production_data", "test_data", "synthetic_data"]),
                "parameters": {
                    "epochs": random.randint(50, 200),
                    "batch_size": random.choice([16, 32, 64, 128])
                }
            }
            
            if job_status == "completed":
                results = {
                    "accuracy": round(random.uniform(0.8, 0.98), 3),
                    "training_time": f"{random.randint(1, 6)}h {random.randint(0, 59)}m",
                    "model_saved": True
                }
            elif job_status == "failed":
                results = {
                    "error": "Out of memory error during training",
                    "error_code": 137
                }
        
        cursor.execute("""
            INSERT INTO jobs (type, status, parameters, result, created_at, updated_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            job_type,
            job_status,
            json.dumps(parameters),
            json.dumps(results),
            created_at,
            updated_at,
            completed_at
        ))

if __name__ == "__main__":
    result = init_database()
    if result:
        logger.info("Database initialization completed successfully!")
    else:
        logger.error("Database initialization failed.")
