import logging
import os
import json
import pickle
import datetime
import time
import numpy as np
import asyncio
import threading
import traceback
import uuid
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

# CRITICAL: Do NOT import psycopg2 at module level!
# It will be imported lazily in methods to prevent mutex deadlock
POSTGRES_AVAILABLE = False


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime and numpy types."""
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        elif isinstance(obj, datetime.timedelta):
            return obj.total_seconds()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.int8, np.int16, np.int32, np.int64,
                              np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        elif isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except:
                return str(obj)
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class ConnectionConfig:
    """Database connection configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "anomaly_detection"
    user: str = "anomaly_user"
    password: str = ""
    min_connections: int = 2
    max_connections: int = 20
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'ConnectionConfig':
        """Create ConnectionConfig from dictionary."""
        return cls(
            host=config.get("host", "localhost"),
            port=config.get("port", 5432),
            database=config.get("database", "anomaly_detection"),
            user=config.get("user", "anomaly_user"),
            password=config.get("password", ""),
            min_connections=config.get("min_connections", 2),
            max_connections=config.get("max_connections", 20)
        )


class StorageManager:
    """
    Thread-safe storage manager with mutex deadlock prevention.
    
    USAGE:
        # Create without initializing
        storage = StorageManager(config)
        
        # Initialize from async context
        await asyncio.to_thread(storage.initialize_connection_pool)
        
        # Use with asyncio.to_thread()
        result = await asyncio.to_thread(storage.save_anomaly, data)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize storage manager (without connecting to database).
        
        CRITICAL: This does NOT initialize the connection pool.
        Call initialize_connection_pool() from async context using asyncio.to_thread()
        """
        self.config = config
        self.type = config.get("type", "postgresql")
        self.logger = logging.getLogger("storage_manager")
        
        # Connection management with thread-safe locks
        self.connection_pool = None
        self.connection_state = ConnectionState.DISCONNECTED
        self._connection_lock = threading.RLock()
        self._pool_lock = threading.RLock()
        self._connection_retries = 3
        self._retry_delay = 1
        
        # Track active connections
        self._active_connections = set()
        self._connection_tracking_lock = threading.Lock()
        
        # File storage paths
        self.storage_path = self._setup_storage_path()
        
        self.logger.info(f"✓ StorageManager created (type={self.type}, connection deferred)")
    
    def get_storage_path(self) -> str:
        """Get the path for file storage."""
        return str(self.storage_path)
    
    def _setup_storage_path(self) -> Path:
        """Set up and return the storage path."""
        base_path = Path(os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "storage"
        )))
        
        directories = ["models", "anomalies", "processed", "state", "backups"]
        for directory in directories:
            (base_path / directory).mkdir(parents=True, exist_ok=True)
        
        return base_path
    
    def initialize_connection_pool(self) -> bool:
        """
        CRITICAL: Initialize the connection pool with lazy psycopg2 import.
        
        This MUST be called from async context using asyncio.to_thread():
            await asyncio.to_thread(storage.initialize_connection_pool)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info("Initializing connection pool with lazy import...")
            self._initialize_storage()
            return self.connection_state == ConnectionState.CONNECTED
        except Exception as e:
            self.logger.error(f"Failed to initialize connection pool: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _initialize_storage(self) -> None:
        """Initialize storage backend."""
        if self.type in ["postgresql", "postgres"]:
            self._initialize_postgresql()
        else:
            self.logger.info(f"Using {self.type} storage backend")
            self.connection_state = ConnectionState.CONNECTED
    
    def _initialize_postgresql(self) -> None:
        """Initialize PostgreSQL with lazy import to prevent mutex deadlock."""
        # CRITICAL: Import psycopg2 HERE, not at module level
        global POSTGRES_AVAILABLE
        try:
            import psycopg2
            import psycopg2.pool
            import psycopg2.extras
            POSTGRES_AVAILABLE = True
            self.logger.info("✓ psycopg2 imported successfully (lazy import)")
        except ImportError:
            self.logger.error("psycopg2 not installed")
            POSTGRES_AVAILABLE = False
            self.connection_state = ConnectionState.ERROR
            return
        
        with self._connection_lock:
            self.connection_state = ConnectionState.CONNECTING
            
            for attempt in range(self._connection_retries):
                try:
                    conn_config = ConnectionConfig.from_dict(self.config)
                    
                    self.logger.info(f"Creating connection pool (attempt {attempt + 1}/{self._connection_retries})...")
                    self.logger.info(f"  Host: {conn_config.host}")
                    self.logger.info(f"  Port: {conn_config.port}")
                    self.logger.info(f"  Database: {conn_config.database}")
                    self.logger.info(f"  Pool size: {conn_config.min_connections}-{conn_config.max_connections}")
                    
                    with self._pool_lock:
                        self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                            minconn=conn_config.min_connections,
                            maxconn=conn_config.max_connections,
                            host=conn_config.host,
                            port=conn_config.port,
                            database=conn_config.database,
                            user=conn_config.user,
                            password=conn_config.password,
                            connect_timeout=10,
                            options='-c statement_timeout=30000'
                        )
                    
                    # Test connection
                    test_conn = self.connection_pool.getconn()
                    test_conn.close()
                    self.connection_pool.putconn(test_conn)
                    
                    self.connection_state = ConnectionState.CONNECTED
                    self.logger.info("✓ PostgreSQL connection pool initialized successfully")
                    return
                    
                except Exception as e:
                    self.logger.error(f"Connection attempt {attempt + 1} failed: {str(e)}")
                    if attempt < self._connection_retries - 1:
                        time.sleep(self._retry_delay * (2 ** attempt))
                    else:
                        self.logger.error("All connection attempts failed")
                        self.connection_state = ConnectionState.ERROR
                        raise
    
    @contextmanager
    def get_connection(self):
        """
        Thread-safe context manager for database connections.
        
        Usage:
            with storage.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM table")
        """
        if self.connection_state != ConnectionState.CONNECTED or not self.connection_pool:
            yield None
            return
        
        conn = None
        try:
            with self._pool_lock:
                conn = self.connection_pool.getconn()
            
            # Track connection
            with self._connection_tracking_lock:
                self._active_connections.add(id(conn))
            
            yield conn
            
        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if conn:
                try:
                    # Untrack connection
                    with self._connection_tracking_lock:
                        self._active_connections.discard(id(conn))
                    
                    # Return to pool
                    with self._pool_lock:
                        if self.connection_pool:
                            self.connection_pool.putconn(conn)
                except Exception as e:
                    self.logger.error(f"Error returning connection to pool: {str(e)}")
    
    def create_tables(self) -> bool:
        """Create database tables if they don't exist."""
        if self.connection_state != ConnectionState.CONNECTED:
            self.logger.warning("Cannot create tables: not connected")
            return False

        if self.type not in ("postgresql", "postgres"):
            return True

        # Import psycopg2 for DictCursor
        try:
            import psycopg2.extras
        except ImportError:
            self.logger.error("psycopg2 not available")
            return False
        
        with self.get_connection() as conn:
            if not conn:
                return False
            
            try:
                cursor = conn.cursor()
                
                # Anomalies table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS anomalies (
                        id SERIAL PRIMARY KEY,
                        anomaly_id VARCHAR(255) UNIQUE NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        model_name VARCHAR(255),
                        score FLOAT,
                        data JSONB,
                        metadata JSONB,
                        severity VARCHAR(50),
                        status VARCHAR(50) DEFAULT 'detected',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Jobs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        id SERIAL PRIMARY KEY,
                        job_id VARCHAR(255) UNIQUE NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        progress FLOAT DEFAULT 0,
                        total_items INTEGER DEFAULT 0,
                        processed_items INTEGER DEFAULT 0,
                        results JSONB,
                        error TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """)
                
                # Processed data table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processed_data (
                        id SERIAL PRIMARY KEY,
                        data_id VARCHAR(255) UNIQUE NOT NULL,
                        source VARCHAR(255),
                        raw_data JSONB,
                        processed_data JSONB,
                        features JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Agent activities table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agent_activities (
                        id SERIAL PRIMARY KEY,
                        activity_id VARCHAR(255) UNIQUE NOT NULL,
                        job_id VARCHAR(255),
                        agent_name VARCHAR(255),
                        action VARCHAR(255),
                        timestamp TIMESTAMP NOT NULL,
                        data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Agent messages table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agent_messages (
                        id SERIAL PRIMARY KEY,
                        message_id VARCHAR(255) UNIQUE NOT NULL,
                        job_id VARCHAR(255),
                        agent_name VARCHAR(255),
                        role VARCHAR(50),
                        content TEXT,
                        timestamp TIMESTAMP NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Migration: Add missing columns to existing tables
                # Check if model_name column exists in anomalies table
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'anomalies' AND column_name = 'model_name'
                """)
                if not cursor.fetchone():
                    self.logger.info("Adding model_name column to anomalies table...")
                    cursor.execute("""
                        ALTER TABLE anomalies 
                        ADD COLUMN model_name VARCHAR(255)
                    """)
                    self.logger.info("✓ Added model_name column")
                
                # Check if status column exists in anomalies table
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'anomalies' AND column_name = 'status'
                """)
                if not cursor.fetchone():
                    self.logger.info("Adding status column to anomalies table...")
                    cursor.execute("""
                        ALTER TABLE anomalies 
                        ADD COLUMN status VARCHAR(50) DEFAULT 'detected'
                    """)
                    self.logger.info("✓ Added status column")
                
                # Check if severity column exists in anomalies table
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'anomalies' AND column_name = 'severity'
                """)
                if not cursor.fetchone():
                    self.logger.info("Adding severity column to anomalies table...")
                    cursor.execute("""
                        ALTER TABLE anomalies 
                        ADD COLUMN severity VARCHAR(50)
                    """)
                    self.logger.info("✓ Added severity column")
                
                # Create indexes (will skip if they already exist)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_model ON anomalies(model_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_activities_job ON agent_activities(job_id)")
                
                conn.commit()
                cursor.close()
                
                self.logger.info("✓ Database tables created/verified successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Error creating tables: {str(e)}")
                self.logger.error(traceback.format_exc())
                if conn:
                    conn.rollback()
                return False
    
    def check_connection(self) -> bool:
        """Check if database connection is healthy."""
        if self.connection_state != ConnectionState.CONNECTED:
            return False

        if self.type not in ("postgresql", "postgres"):
            return True

        with self.get_connection() as conn:
            if not conn:
                return False
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return True
            except Exception as e:
                self.logger.error(f"Connection check failed: {str(e)}")
                return False
    
    def save_anomaly(self, anomaly: Dict[str, Any]) -> bool:
        """Save an anomaly to the database."""
        if self.connection_state != ConnectionState.CONNECTED:
            self.logger.warning("Cannot save anomaly: not connected")
            return False
        
        try:
            import psycopg2.extras
        except ImportError:
            return False
        
        with self.get_connection() as conn:
            if not conn:
                return False
            
            try:
                cursor = conn.cursor()
                
                anomaly_id = anomaly.get('anomaly_id', str(uuid.uuid4()))
                timestamp = anomaly.get('timestamp', datetime.datetime.utcnow())
                model_name = anomaly.get('model_name', 'unknown')
                score = anomaly.get('score', 0.0)
                data = json.dumps(anomaly.get('data', {}), cls=DateTimeEncoder)
                metadata = json.dumps(anomaly.get('metadata', {}), cls=DateTimeEncoder)
                severity = anomaly.get('severity', 'medium')
                
                cursor.execute("""
                    INSERT INTO anomalies (anomaly_id, timestamp, model_name, score, data, metadata, severity)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                    ON CONFLICT (anomaly_id) DO UPDATE SET
                        timestamp = EXCLUDED.timestamp,
                        model_name = EXCLUDED.model_name,
                        score = EXCLUDED.score,
                        data = EXCLUDED.data,
                        metadata = EXCLUDED.metadata,
                        severity = EXCLUDED.severity,
                        updated_at = CURRENT_TIMESTAMP
                """, (anomaly_id, timestamp, model_name, score, data, metadata, severity))
                
                conn.commit()
                cursor.close()
                return True
                
            except Exception as e:
                self.logger.error(f"Error saving anomaly: {str(e)}")
                self.logger.error(traceback.format_exc())
                if conn:
                    conn.rollback()
                return False
    
    def store_anomalies(self, anomalies: List[Dict[str, Any]]) -> int:
        """Store multiple anomalies to the database. Returns count of successfully stored."""
        stored = 0
        for anomaly in anomalies:
            if self.save_anomaly(anomaly):
                stored += 1
        return stored

    def get_anomalies(self, limit: int = 100, offset: int = 0,
                     filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get anomalies from database with optional filters."""
        anomalies = []
        
        if self.connection_state != ConnectionState.CONNECTED:
            return anomalies
        
        try:
            import psycopg2.extras
        except ImportError:
            return anomalies
        
        with self.get_connection() as conn:
            if not conn:
                return anomalies
            
            try:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                
                query = "SELECT * FROM anomalies WHERE 1=1"
                params = []
                
                if filters:
                    if 'model_name' in filters:
                        query += " AND model_name = %s"
                        params.append(filters['model_name'])
                    if 'severity' in filters:
                        query += " AND severity = %s"
                        params.append(filters['severity'])
                    if 'start_date' in filters:
                        query += " AND timestamp >= %s"
                        params.append(filters['start_date'])
                    if 'end_date' in filters:
                        query += " AND timestamp <= %s"
                        params.append(filters['end_date'])
                
                query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                
                for row in cursor:
                    anomaly = dict(row)
                    # Convert timestamps to ISO format
                    for field in ['timestamp', 'created_at', 'updated_at']:
                        if field in anomaly and anomaly[field]:
                            anomaly[field] = anomaly[field].isoformat()
                    anomalies.append(anomaly)
                
                cursor.close()
                
            except Exception as e:
                self.logger.error(f"Error getting anomalies: {str(e)}")
                self.logger.error(traceback.format_exc())
        
        return anomalies
    
    def save_job(self, job: Dict[str, Any]) -> bool:
        """Save a job to the database."""
        if self.connection_state != ConnectionState.CONNECTED:
            return False
        
        with self.get_connection() as conn:
            if not conn:
                return False
            
            try:
                cursor = conn.cursor()
                
                job_id = job.get('job_id', str(uuid.uuid4()))
                status = job.get('status', 'pending')
                progress = job.get('progress', 0.0)
                total_items = job.get('total_items', 0)
                processed_items = job.get('processed_items', 0)
                results = json.dumps(job.get('results', {}), cls=DateTimeEncoder)
                error = job.get('error')
                
                cursor.execute("""
                    INSERT INTO jobs (job_id, status, progress, total_items, processed_items, results, error)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (job_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        progress = EXCLUDED.progress,
                        total_items = EXCLUDED.total_items,
                        processed_items = EXCLUDED.processed_items,
                        results = EXCLUDED.results,
                        error = EXCLUDED.error,
                        updated_at = CURRENT_TIMESTAMP,
                        completed_at = CASE WHEN EXCLUDED.status IN ('completed', 'failed') 
                                       THEN CURRENT_TIMESTAMP ELSE NULL END
                """, (job_id, status, progress, total_items, processed_items, results, error))
                
                conn.commit()
                cursor.close()
                return True
                
            except Exception as e:
                self.logger.error(f"Error saving job: {str(e)}")
                if conn:
                    conn.rollback()
                return False
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        if self.connection_state != ConnectionState.CONNECTED:
            return None
        
        try:
            import psycopg2.extras
        except ImportError:
            return None
        
        with self.get_connection() as conn:
            if not conn:
                return None
            
            try:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
                cursor.close()
                
                if row:
                    job = dict(row)
                    for field in ['created_at', 'updated_at', 'completed_at']:
                        if field in job and job[field]:
                            job[field] = job[field].isoformat()
                    return job
                
            except Exception as e:
                self.logger.error(f"Error getting job: {str(e)}")
        
        return None
    
    def save_model(self, model_name: str, model_state: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save a model's state to disk.
        
        Args:
            model_name: Name of the model
            model_state: Model state/object to save
            metadata: Optional metadata about the model
            
        Returns:
            True if successful, False otherwise
        """
        try:
            models_dir = self.storage_path / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine file extension based on model_state type
            if hasattr(model_state, '__dict__') or isinstance(model_state, dict):
                # Save as pickle for complex objects
                model_file = models_dir / f"{model_name}.pkl"
                with open(model_file, 'wb') as f:
                    pickle.dump(model_state, f)
            else:
                # Save as joblib for sklearn-like models
                try:
                    import joblib
                    model_file = models_dir / f"{model_name}.joblib"
                    joblib.dump(model_state, model_file)
                except ImportError:
                    # Fallback to pickle if joblib not available
                    model_file = models_dir / f"{model_name}.pkl"
                    with open(model_file, 'wb') as f:
                        pickle.dump(model_state, f)
            
            # Save metadata if provided
            if metadata:
                metadata_file = models_dir / f"{model_name}_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2, cls=DateTimeEncoder)
            
            self.logger.info(f"✓ Saved model {model_name} to {model_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving model {model_name}: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
    
    def load_model(self, model_name: str) -> Optional[Any]:
        """
        Load a model's state from disk.
        
        Args:
            model_name: Name of the model to load
            
        Returns:
            Model state if found, None otherwise
        """
        try:
            models_dir = self.storage_path / "models"
            
            # Try different file extensions
            for extension in ['.pkl', '.joblib', '.json']:
                model_file = models_dir / f"{model_name}{extension}"
                
                if model_file.exists():
                    if extension == '.pkl':
                        with open(model_file, 'rb') as f:
                            model_state = pickle.load(f)
                    elif extension == '.joblib':
                        try:
                            import joblib
                            model_state = joblib.load(model_file)
                        except ImportError:
                            self.logger.warning(f"joblib not available, skipping {model_file}")
                            continue
                    elif extension == '.json':
                        with open(model_file, 'r') as f:
                            model_state = json.load(f)
                    
                    self.logger.info(f"✓ Loaded model {model_name} from {model_file}")
                    return model_state
            
            # Model file not found
            self.logger.debug(f"No saved state found for model {model_name}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error loading model {model_name}: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None
    
    def list_saved_models(self) -> List[str]:
        """
        List all saved models in the storage directory.
        
        Returns:
            List of model names
        """
        try:
            models_dir = self.storage_path / "models"
            if not models_dir.exists():
                return []
            
            model_files = []
            for extension in ['.pkl', '.joblib', '.json']:
                model_files.extend(models_dir.glob(f"*{extension}"))
            
            # Extract unique model names (without extension and metadata suffix)
            model_names = set()
            for model_file in model_files:
                name = model_file.stem
                if not name.endswith('_metadata'):
                    model_names.add(name)
            
            return sorted(list(model_names))
            
        except Exception as e:
            self.logger.error(f"Error listing saved models: {str(e)}")
            return []
    
    def delete_model(self, model_name: str) -> bool:
        """
        Delete a saved model from disk.
        
        Args:
            model_name: Name of the model to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            models_dir = self.storage_path / "models"
            deleted = False
            
            # Delete all related files
            for extension in ['.pkl', '.joblib', '.json']:
                model_file = models_dir / f"{model_name}{extension}"
                if model_file.exists():
                    model_file.unlink()
                    deleted = True
            
            # Delete metadata file
            metadata_file = models_dir / f"{model_name}_metadata.json"
            if metadata_file.exists():
                metadata_file.unlink()
            
            if deleted:
                self.logger.info(f"✓ Deleted model {model_name}")
                return True
            else:
                self.logger.warning(f"Model {model_name} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting model {model_name}: {str(e)}")
            return False
    
    def close(self) -> None:
        """Close all database connections."""
        with self._connection_lock:
            if self.connection_pool:
                try:
                    # Wait for active connections
                    max_wait = 10
                    wait_interval = 0.5
                    elapsed = 0
                    
                    while elapsed < max_wait:
                        with self._connection_tracking_lock:
                            if len(self._active_connections) == 0:
                                break
                        time.sleep(wait_interval)
                        elapsed += wait_interval
                    
                    # Close pool
                    self.connection_pool.closeall()
                    self.logger.info("✓ Database connections closed")
                    
                except Exception as e:
                    self.logger.error(f"Error closing connections: {str(e)}")
                finally:
                    self.connection_pool = None
                    self.connection_state = ConnectionState.DISCONNECTED
                    with self._connection_tracking_lock:
                        self._active_connections.clear()
    
    # =========================================================================
    # NEW METHOD ADDED IN v3.1 - FIX FOR API SERVICES
    # =========================================================================
    
    def _prepare_for_json_field(self, data: Any) -> str:
        """
        Prepare data for insertion into a JSONB field.
        
        This method ensures that data is properly serialized to JSON string
        with proper handling of datetime, numpy, and other non-JSON types.
        
        Args:
            data: Data to prepare (dict, list, or other JSON-serializable type)
            
        Returns:
            JSON string ready for JSONB field insertion
        """
        try:
            # If already a string, validate it's proper JSON
            if isinstance(data, str):
                try:
                    # Test if it's valid JSON
                    json.loads(data)
                    return data
                except json.JSONDecodeError:
                    # Not valid JSON, wrap it in quotes
                    return json.dumps(data, cls=DateTimeEncoder)
            
            # For other types, serialize using custom encoder
            return json.dumps(data, cls=DateTimeEncoder)
            
        except Exception as e:
            self.logger.error(f"Error preparing data for JSON field: {str(e)}")
            self.logger.error(traceback.format_exc())
            # Fallback: return empty dict as JSON string
            return "{}"
    
    # =========================================================================
    # END OF NEW METHOD
    # =========================================================================
    
    def __del__(self):
        """Destructor to ensure connections are closed."""
        try:
            self.close()
        except:
            pass


# Export main class
__all__ = ['StorageManager', 'ConnectionState', 'ConnectionConfig', 'DateTimeEncoder']