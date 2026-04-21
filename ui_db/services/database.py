"""
Database connector for the Anomaly Detection Dashboard services.
Provides connection pool and query functions for PostgreSQL database.
"""

import os
import sys
import yaml
import psycopg2
import psycopg2.pool
import pandas as pd
from contextlib import contextmanager
import logging
import datetime
import json

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

# Get database configuration
config = load_config()

if not config:
    logger.warning("Using default database configuration")
    DB_CONFIG = {
        "host": "localhost",
        "port": 5432,
        "database": "anomaly_detection",
        "user": "anomaly_user",
        "password": "St@rW@rs!"
    }
else:
    db_section = config.get('database', {})
    DB_CONFIG = db_section.get('connection', {
        "host": "localhost",
        "port": 5432,
        "database": "anomaly_detection",
        "user": "anomaly_user",
        "password": "St@rW@rs!"
    })
    logger.info(f"Loaded database configuration from config.yaml")

# Connection pool - initialize as None and create when needed
connection_pool = None

def initialize_connection_pool():
    """Initialize the database connection pool."""
    global connection_pool
    
    if connection_pool is not None:
        # Close any existing connections in the pool
        if not connection_pool.closed:
            connection_pool.closeall()
    
    try:
        # Create a new connection pool
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        logger.info("Database connection pool created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database connection pool: {e}")
        connection_pool = None
        return False

@contextmanager
def get_connection():
    """Get a connection from the pool and ensure it's returned."""
    global connection_pool
    
    # Initialize the pool if it doesn't exist
    if connection_pool is None:
        success = initialize_connection_pool()
        if not success:
            raise Exception("Failed to initialize database connection pool")
    
    connection = None
    try:
        connection = connection_pool.getconn()
        yield connection
    finally:
        if connection:
            connection_pool.putconn(connection)

@contextmanager
def get_cursor(commit=False):
    """Get a cursor from a connection from the pool."""
    with get_connection() as connection:
        cursor = connection.cursor()
        try:
            yield cursor
            if commit:
                connection.commit()
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            cursor.close()

def execute_query(query, params=None, commit=False):
    """Execute a SQL query and return the results.
    
    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the query. Defaults to None.
        commit (bool, optional): Whether to commit the transaction. Defaults to False.
        
    Returns:
        list: Query results or None if error occurs
    """
    try:
        with get_cursor(commit=commit) as cursor:
            cursor.execute(query, params)
            
            # Check if cursor.description is None (happens with INSERT, UPDATE, etc.)
            if cursor.description is None:
                return []
                
            # Fetch and return results
            results = cursor.fetchall()
            return results
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        return False

def query_to_dataframe(query, params=None):
    """Execute a query and return the results as a pandas DataFrame.
    
    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the query. Defaults to None.
        
    Returns:
        pd.DataFrame: Results as a pandas DataFrame
    """
    try:
        with get_cursor() as cursor:
            cursor.execute(query, params)
            
            # Check if cursor.description is None (happens with statements that don't return rows)
            if cursor.description is None:
                return pd.DataFrame()
                
            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            
        # Create DataFrame with column names and data
        df = pd.DataFrame(results, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        logger.error(f"Query: {query}")
        return pd.DataFrame()

def setup_database_schema():
    """Create or update the database schema with all required tables."""
    try:
        with get_cursor(commit=True) as cursor:
            # Enable UUID extension
            cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
            
            # Create models table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    type VARCHAR(100) NOT NULL,
                    status VARCHAR(50) DEFAULT 'not_trained',
                    config JSONB DEFAULT '{}',
                    performance JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Create processed_data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_data (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    collector VARCHAR(255) NOT NULL,
                    data JSONB NOT NULL,
                    features JSONB,
                    batch_id VARCHAR(255),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            
            # Create anomalies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS anomalies (
                    id VARCHAR(255) PRIMARY KEY,
                    model_id INTEGER REFERENCES models(id),
                    model VARCHAR(255) NOT NULL,
                    score FLOAT NOT NULL,
                    threshold FLOAT DEFAULT 0.5,
                    timestamp TIMESTAMP NOT NULL,
                    detection_time TIMESTAMP DEFAULT NOW(),
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
                )
            """)
            
            # Create model_states table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_states (
                    model_name VARCHAR(255) PRIMARY KEY,
                    model_type VARCHAR(255) NOT NULL,
                    state JSONB NOT NULL,
                    version INTEGER DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            
            # Create anomaly_analysis table
            cursor.execute("""
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
                )
            """)
            
            # Create agent_messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id SERIAL PRIMARY KEY,
                    anomaly_id VARCHAR(255) REFERENCES anomalies(id) ON DELETE SET NULL,
                    agent_id VARCHAR(100),
                    agent VARCHAR(100),
                    message TEXT,
                    content TEXT,
                    message_type VARCHAR(50) DEFAULT 'info',
                    timestamp TIMESTAMP DEFAULT NOW(),
                    job_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW(),
                    agent_name VARCHAR(255)
                )
            """)
            
            # Create agent_activities table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_activities (
                    id SERIAL PRIMARY KEY,
                    anomaly_id VARCHAR(255) REFERENCES anomalies(id) ON DELETE SET NULL,
                    agent_id VARCHAR(100),
                    agent VARCHAR(100),
                    activity_type VARCHAR(100),
                    action VARCHAR(100),
                    description TEXT,
                    status VARCHAR(50),
                    timestamp TIMESTAMP DEFAULT NOW(),
                    details JSONB DEFAULT '{}',
                    job_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW(),
                    agent_name VARCHAR(255)
                )
            """)
            
            # Create system_status table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_status (
                    key VARCHAR(255) PRIMARY KEY,
                    value JSONB,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Create jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(255),
                    job_type VARCHAR(100),
                    status VARCHAR(50) DEFAULT 'pending',
                    progress FLOAT DEFAULT 0,
                    result JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Create background_jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS background_jobs (
                    id SERIAL PRIMARY KEY,
                    job_type VARCHAR(100),
                    status VARCHAR(50) DEFAULT 'pending',
                    progress FLOAT DEFAULT 0,
                    result JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Create processors table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processors (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    type VARCHAR(100) NOT NULL,
                    status VARCHAR(50) DEFAULT 'inactive',
                    config JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Create collectors table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collectors (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    type VARCHAR(100) NOT NULL,
                    status VARCHAR(50) DEFAULT 'inactive',
                    config JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Create necessary indices
            indices = [
                "CREATE INDEX IF NOT EXISTS idx_models_name ON models(name)",
                "CREATE INDEX IF NOT EXISTS idx_models_type ON models(type)",
                "CREATE INDEX IF NOT EXISTS idx_models_status ON models(status)",
                
                "CREATE INDEX IF NOT EXISTS idx_anomalies_model_id ON anomalies(model_id)",
                "CREATE INDEX IF NOT EXISTS idx_anomalies_model ON anomalies(model)",
                "CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_anomalies_detection_time ON anomalies(detection_time)",
                "CREATE INDEX IF NOT EXISTS idx_anomalies_score ON anomalies(score)",
                "CREATE INDEX IF NOT EXISTS idx_anomalies_status ON anomalies(status)",
                "CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity)",
                
                "CREATE INDEX IF NOT EXISTS idx_agent_messages_anomaly_id ON agent_messages(anomaly_id)",
                "CREATE INDEX IF NOT EXISTS idx_agent_messages_agent_id ON agent_messages(agent_id)",
                "CREATE INDEX IF NOT EXISTS idx_agent_messages_job_id ON agent_messages(job_id)",
                
                "CREATE INDEX IF NOT EXISTS idx_agent_activities_anomaly_id ON agent_activities(anomaly_id)",
                "CREATE INDEX IF NOT EXISTS idx_agent_activities_agent_id ON agent_activities(agent_id)",
                "CREATE INDEX IF NOT EXISTS idx_agent_activities_job_id ON agent_activities(job_id)",
                
                "CREATE INDEX IF NOT EXISTS idx_processed_data_timestamp ON processed_data(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_processed_data_collector ON processed_data(collector)",
                "CREATE INDEX IF NOT EXISTS idx_processed_data_batch_id ON processed_data(batch_id)"
            ]
            
            for index in indices:
                try:
                    cursor.execute(index)
                except Exception as e:
                    logger.warning(f"Error creating index: {e}")
            
            logger.info("Database schema setup completed successfully")
        
        return True
    except Exception as e:
        logger.error(f"Error setting up database schema: {e}")
        return False
    
def update_schema_with_missing_columns():
    """Check for missing columns in existing tables and add them if needed."""
    try:
        # Check and update the tables
        with get_cursor(commit=True) as cursor:
            # Check and add detection_time column if it doesn't exist
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'anomalies' AND column_name = 'detection_time') THEN
                        ALTER TABLE anomalies ADD COLUMN detection_time TIMESTAMP DEFAULT NOW();
                        -- Update existing rows to set detection_time equal to timestamp
                        UPDATE anomalies SET detection_time = timestamp WHERE detection_time IS NULL;
                    END IF;
                END $$;
            """)
            
            # Check and add data column if it doesn't exist
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'anomalies' AND column_name = 'data') THEN
                        ALTER TABLE anomalies ADD COLUMN data JSONB DEFAULT '{}';
                    END IF;
                END $$;
            """)
            
            # Check and add severity column if it doesn't exist
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'anomalies' AND column_name = 'severity') THEN
                        ALTER TABLE anomalies ADD COLUMN severity VARCHAR(50);
                        -- Try to extract severity from analysis field
                        UPDATE anomalies 
                        SET severity = analysis->>'severity' 
                        WHERE severity IS NULL AND analysis->>'severity' IS NOT NULL;
                    END IF;
                END $$;
            """)
            
            # Check and add job_id column to agent_messages
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'agent_messages' AND column_name = 'job_id') THEN
                        ALTER TABLE agent_messages ADD COLUMN job_id VARCHAR(255);
                    END IF;
                END $$;
            """)
            
            # Check and add agent_name column to agent_messages
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'agent_messages' AND column_name = 'agent_name') THEN
                        ALTER TABLE agent_messages ADD COLUMN agent_name VARCHAR(255);
                    END IF;
                END $$;
            """)
            
            # Check and add job_id column to agent_activities
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'agent_activities' AND column_name = 'job_id') THEN
                        ALTER TABLE agent_activities ADD COLUMN job_id VARCHAR(255);
                    END IF;
                END $$;
            """)
            
            # Check and add agent_name column to agent_activities
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'agent_activities' AND column_name = 'agent_name') THEN
                        ALTER TABLE agent_activities ADD COLUMN agent_name VARCHAR(255);
                    END IF;
                END $$;
            """)
            
            # Fix agent_messages table by ensuring both message and content columns exist
            cursor.execute("""
                DO $$ 
                BEGIN
                    -- Add message column if it doesn't exist
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'agent_messages' AND column_name = 'message') THEN
                        ALTER TABLE agent_messages ADD COLUMN message TEXT;
                    END IF;
                    
                    -- Add content column if it doesn't exist
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'agent_messages' AND column_name = 'content') THEN
                        ALTER TABLE agent_messages ADD COLUMN content TEXT;
                    END IF;
                    
                    -- Copy data between columns if one is NULL
                    UPDATE agent_messages SET message = content WHERE message IS NULL AND content IS NOT NULL;
                    UPDATE agent_messages SET content = message WHERE content IS NULL AND message IS NOT NULL;
                END $$;
            """)
        
        logger.info("Database schema update check completed")
        return True
    except Exception as e:
        logger.error(f"Error updating database schema: {e}")
        return False

def get_anomaly_by_id(anomaly_id):
    """Get a specific anomaly by ID.
    
    Args:
        anomaly_id (str): ID of the anomaly to retrieve
        
    Returns:
        dict: Anomaly object or None
    """
    try:
        # Updated query to match the actual database schema
        query = """
            SELECT a.id, a.model_id, a.model, a.score, a.timestamp, a.detection_time,
                   a.location, a.src_ip, a.dst_ip, a.details, a.features, a.analysis,
                   a.threshold, a.status, a.data, a.severity, a.created_at, a.updated_at
            FROM anomalies a
            WHERE a.id = %s
        """
        
        df = query_to_dataframe(query, (anomaly_id,))
        
        if df.empty:
            return None
            
        row = df.iloc[0]
        anomaly = row.to_dict()
        
        # Format timestamp fields
        timestamp_fields = ['timestamp', 'detection_time', 'created_at', 'updated_at']
        for field in timestamp_fields:
            if field in anomaly and anomaly[field] is not None:
                if isinstance(anomaly[field], datetime.datetime):
                    anomaly[field] = anomaly[field].isoformat()
        
        # Parse JSON fields with safe handling
        json_fields = ['details', 'features', 'analysis', 'data']
        for field in json_fields:
            if field in anomaly and anomaly[field] is not None:
                if isinstance(anomaly[field], str):
                    try:
                        anomaly[field] = json.loads(anomaly[field])
                    except json.JSONDecodeError:
                        # If can't parse, initialize as empty dict
                        anomaly[field] = {}
                elif anomaly[field] is None or not isinstance(anomaly[field], (dict, list)):
                    # Initialize as empty dict if None or invalid type
                    anomaly[field] = {}
        
        return anomaly
    except Exception as e:
        logger.error(f"Error fetching anomaly by ID: {e}")
        return None
        
def get_anomaly_analysis(anomaly_id):
    """Get analysis results for an anomaly.
    
    Args:
        anomaly_id (str): ID of the anomaly
        
    Returns:
        dict: Analysis results or None
    """
    try:
        query = """
            SELECT id, anomaly_id, model, score, timestamp, 
                   analysis_content, remediation_content, reflection_content,
                   created_at, updated_at
            FROM anomaly_analysis
            WHERE anomaly_id = %s
        """
        
        df = query_to_dataframe(query, (anomaly_id,))
        
        if df.empty:
            return None
            
        row = df.iloc[0]
        
        # Convert to dictionary
        analysis = row.to_dict()
        
        # Format timestamp fields
        timestamp_fields = ['timestamp', 'created_at', 'updated_at']
        for field in timestamp_fields:
            if field in analysis and analysis[field] is not None:
                if isinstance(analysis[field], datetime.datetime):
                    analysis[field] = analysis[field].isoformat()
        
        # Handle JSON fields
        json_fields = ['analysis_content', 'remediation_content', 'reflection_content']
        for field in json_fields:
            if field in analysis and analysis[field] is not None:
                if isinstance(analysis[field], str):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except json.JSONDecodeError:
                        # If can't parse, keep as is
                        pass
        
        return analysis
    except Exception as e:
        logger.error(f"Error fetching anomaly analysis: {e}")
        return None

def get_agent_messages(anomaly_id):
    """Get agent messages for an anomaly.
    
    Args:
        anomaly_id (str): ID of the analyzed anomaly
        
    Returns:
        list: Agent messages
    """
    try:
        # Updated query to handle both message and content columns
        query = """
            SELECT id, agent_id, agent, 
                   COALESCE(message, content) as content, 
                   message_type, anomaly_id, timestamp, created_at, job_id, agent_name
            FROM agent_messages
            WHERE anomaly_id = %s
            ORDER BY timestamp
        """
        
        df = query_to_dataframe(query, (anomaly_id,))
        
        if df.empty:
            return []
        
        # Convert to list of dictionaries
        messages = []
        for _, row in df.iterrows():
            message = row.to_dict()
            
            # Use agent_id if available, otherwise use agent
            if not message.get('agent_id') and message.get('agent'):
                message['agent_id'] = message['agent']
            
            # Format timestamp fields
            timestamp_fields = ['timestamp', 'created_at']
            for field in timestamp_fields:
                if field in message and message[field] is not None:
                    if isinstance(message[field], datetime.datetime):
                        message[field] = message[field].isoformat()
            
            messages.append(message)
        
        return messages
    except Exception as e:
        logger.error(f"Error fetching agent messages: {e}")
        return []
    
def get_agent_activities(anomaly_id=None):
    """Get agent activities, optionally filtered by anomaly ID.
    
    Args:
        anomaly_id (str, optional): ID of the anomaly. Defaults to None.
        
    Returns:
        list: Agent activities
    """
    try:
        if anomaly_id:
            query = """
                SELECT id, agent_id, agent, activity_type, action, 
                       description, status, anomaly_id, timestamp, details, created_at, job_id, agent_name
                FROM agent_activities
                WHERE anomaly_id = %s
                ORDER BY timestamp
            """
            params = (anomaly_id,)
        else:
            query = """
                SELECT id, agent_id, agent, activity_type, action, 
                       description, status, anomaly_id, timestamp, details, created_at, job_id, agent_name
                FROM agent_activities
                ORDER BY timestamp DESC
                LIMIT 100
            """
            params = None
        
        df = query_to_dataframe(query, params)
        
        if df.empty:
            return []
        
        # Convert to list of dictionaries
        activities = []
        for _, row in df.iterrows():
            activity = row.to_dict()
            
            # Use agent_id if available, otherwise use agent
            if not activity.get('agent_id') and activity.get('agent'):
                activity['agent_id'] = activity['agent']
            
            # Use activity_type if available, otherwise use action
            if not activity.get('activity_type') and activity.get('action'):
                activity['activity_type'] = activity['action']
            
            # Format timestamp fields
            timestamp_fields = ['timestamp', 'created_at']
            for field in timestamp_fields:
                if field in activity and activity[field] is not None:
                    if isinstance(activity[field], datetime.datetime):
                        activity[field] = activity[field].isoformat()
            
            # Parse JSON fields
            if 'details' in activity and activity['details'] is not None:
                if isinstance(activity['details'], str):
                    try:
                        activity['details'] = json.loads(activity['details'])
                    except json.JSONDecodeError:
                        # If can't parse, keep as is
                        pass
            
            activities.append(activity)
        
        return activities
    except Exception as e:
        logger.error(f"Error fetching agent activities: {e}")
        return []

def get_time_series_data(days=30):
    """Get time series data for anomalies over time.
    
    Args:
        days (int, optional): Number of days to include. Defaults to 30.
        
    Returns:
        pd.DataFrame: Time series data
    """
    try:
        query = """
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as anomaly_count,
                COUNT(CASE WHEN severity = 'High' OR analysis->>'severity' = 'High' THEN 1 END) as high_severity,
                COUNT(CASE WHEN severity = 'Medium' OR analysis->>'severity' = 'Medium' THEN 1 END) as medium_severity,
                COUNT(CASE WHEN severity = 'Low' OR analysis->>'severity' = 'Low' THEN 1 END) as low_severity,
                AVG(score) as avg_score
            FROM 
                anomalies
            WHERE 
                timestamp >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY 
                DATE(timestamp)
            ORDER BY 
                date
        """
        
        df = query_to_dataframe(query, (days,))
        
        # Convert dates to strings
        if not df.empty and 'date' in df.columns:
            df['date'] = df['date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, datetime.date) else x)
        
        return df
    except Exception as e:
        logger.error(f"Error fetching time series data: {e}")
        return pd.DataFrame()

def update_anomaly_status(anomaly_id, status):
    """Update the status of an anomaly.
    
    Args:
        anomaly_id (str): ID of the anomaly
        status (str): New status value
        
    Returns:
        bool: Success flag
    """
    try:
        query = """
            UPDATE anomalies
            SET status = %s, updated_at = NOW()
            WHERE id = %s
        """
        
        return execute_query(query, (status, anomaly_id), commit=True)
    except Exception as e:
        logger.error(f"Error updating anomaly status: {e}")
        return False

def add_anomaly_analysis(anomaly_id, analysis_data):
    """Add analysis results for an anomaly.
    
    Args:
        anomaly_id (str): ID of the anomaly
        analysis_data (dict): Analysis data including severity, content, etc.
        
    Returns:
        bool: Success flag
    """
    try:
        # Check if analysis already exists
        check_query = """
            SELECT id FROM anomaly_analysis WHERE anomaly_id = %s
        """
        check_df = query_to_dataframe(check_query, (anomaly_id,))
        
        if not check_df.empty:
            # Update existing analysis
            update_query = """
                UPDATE anomaly_analysis
                SET 
                    model = %s,
                    score = %s,
                    analysis_content = %s,
                    remediation_content = %s,
                    reflection_content = %s,
                    updated_at = NOW()
                WHERE anomaly_id = %s
            """
            
            # Ensure JSON fields are properly serialized
            analysis_content = (json.dumps(analysis_data.get('analysis', {})) 
                               if not isinstance(analysis_data.get('analysis', {}), str) 
                               else analysis_data.get('analysis', '{}'))
            
            remediation_content = (json.dumps(analysis_data.get('remediation', {})) 
                                  if not isinstance(analysis_data.get('remediation', {}), str) 
                                  else analysis_data.get('remediation', '{}'))
            
            reflection_content = (json.dumps(analysis_data.get('reflection', {})) 
                                 if not isinstance(analysis_data.get('reflection', {}), str) 
                                 else analysis_data.get('reflection', '{}'))
            
            params = (
                analysis_data.get('model', 'unknown'),
                float(analysis_data.get('score', 0.0)),
                analysis_content,
                remediation_content,
                reflection_content,
                anomaly_id
            )
            
            return execute_query(update_query, params, commit=True)
        else:
            # Insert new analysis
            insert_query = """
                INSERT INTO anomaly_analysis (
                    anomaly_id, model, score, timestamp, 
                    analysis_content, remediation_content, reflection_content,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, NOW(), %s, %s, %s, NOW(), NOW())
            """
            
            # Ensure JSON fields are properly serialized
            analysis_content = (json.dumps(analysis_data.get('analysis', {})) 
                               if not isinstance(analysis_data.get('analysis', {}), str) 
                               else analysis_data.get('analysis', '{}'))
            
            remediation_content = (json.dumps(analysis_data.get('remediation', {})) 
                                  if not isinstance(analysis_data.get('remediation', {}), str) 
                                  else analysis_data.get('remediation', '{}'))
            
            reflection_content = (json.dumps(analysis_data.get('reflection', {})) 
                                 if not isinstance(analysis_data.get('reflection', {}), str) 
                                 else analysis_data.get('reflection', '{}'))
            
            params = (
                anomaly_id,
                analysis_data.get('model', 'unknown'),
                float(analysis_data.get('score', 0.0)),
                analysis_content,
                remediation_content,
                reflection_content
            )
            
            return execute_query(insert_query, params, commit=True)
    except Exception as e:
        logger.error(f"Error adding anomaly analysis: {e}")
        return False

def add_agent_message(anomaly_id, agent_id, message, message_type="info"):
    """Add a message from an agent.
    
    Args:
        anomaly_id (str): ID of the related anomaly
        agent_id (str): ID of the agent
        message (str): Message content
        message_type (str): Type of message (info, warning, error, etc.)
        
    Returns:
        bool: Success flag
    """
    try:
        # Insert with both message and content columns
        query = """
            INSERT INTO agent_messages 
            (anomaly_id, agent_id, agent, message, content, message_type, timestamp, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        
        params = (anomaly_id, agent_id, agent_id, message, message, message_type)
        
        result = execute_query(query, params, commit=True)
        return result is not None
    except Exception as e:
        logger.error(f"Error adding agent message: {e}")
        return False
    
def add_agent_activity(agent_id, activity_type, description, anomaly_id=None, details=None):
    """Add an agent activity.
    
    Args:
        agent_id (str): ID of the agent
        activity_type (str): Type of activity
        description (str): Description of the activity
        anomaly_id (str, optional): ID of the related anomaly
        details (dict, optional): Additional details. Defaults to None.
        
    Returns:
        bool: Success flag
    """
    try:
        # Determine status from details if available, or from description
        status = "completed"
        if details and isinstance(details, dict):
            status = details.get('status', 'completed')
        elif 'started' in description.lower():
            status = 'started'
        elif 'completed' in description.lower():
            status = 'completed'
        elif 'failed' in description.lower():
            status = 'failed'
        
        # Insert with proper column names
        query = """
            INSERT INTO agent_activities 
            (agent_id, agent, activity_type, action, description, status, anomaly_id, timestamp, details, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
        """
        
        # Convert details to JSON string
        if details:
            import json
            details_json = json.dumps(details)
        else:
            details_json = None
        
        params = (
            agent_id,
            agent_id,  # Also store in agent column for backward compatibility
            activity_type,
            activity_type,  # Also store in action column for backward compatibility
            description,
            status,
            anomaly_id,
            details_json
        )
        
        result = execute_query(query, params, commit=True)
        return result is not None
    except Exception as e:
        logger.error(f"Error adding agent activity: {e}")
        return False
    
def test_connection():
    """Test the database connection.
    
    Returns:
        tuple: (bool, str) - Success flag and message
    """
    try:
        # Reset the connection pool to ensure fresh connections
        initialize_connection_pool()
        
        with get_cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            
            # Try to setup the schema
            setup_database_schema()
            
            # Update schema with missing columns
            update_schema_with_missing_columns()
            
        return True, f"Connected to {version}"
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False, f"Connection failed: {str(e)}"

# Initialize connection pool when module is imported
initialize_connection_pool()
# Initial schema setup
if connection_pool is not None:
    setup_database_schema()
    update_schema_with_missing_columns()