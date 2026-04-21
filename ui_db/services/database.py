"""
Database connector for the Anomaly Detection Dashboard services.
Uses SQLite via the built-in sqlite3 module.
"""

import os
import sys
import sqlite3
import threading
import yaml
import pandas as pd
from contextlib import contextmanager
import logging
import datetime
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)


def load_config():
    config_path = os.path.join(project_root, '../config', 'config.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config file: {e}")
        return None


config = load_config()

if config:
    db_section = config.get('database', {})
    DB_PATH = db_section.get('path') or db_section.get('file_path') or 'storage/anomaly_detection.db'
else:
    DB_PATH = 'storage/anomaly_detection.db'

# Resolve relative paths against the project root
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.normpath(os.path.join(project_root, '..', DB_PATH))

logger.info(f"SQLite database path: {DB_PATH}")

# Single shared connection with a lock for thread safety
_connection: sqlite3.Connection | None = None
_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def initialize_connection_pool():
    """Open (or reopen) the SQLite connection. Returns True on success."""
    global _connection
    with _lock:
        try:
            if _connection is not None:
                try:
                    _connection.close()
                except Exception:
                    pass
            _ensure_dir()
            _connection = sqlite3.connect(
                DB_PATH,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            _connection.row_factory = sqlite3.Row
            _connection.execute("PRAGMA journal_mode=WAL")
            _connection.execute("PRAGMA foreign_keys=ON")
            logger.info("SQLite connection opened")
            return True
        except Exception as e:
            logger.error(f"Error opening SQLite connection: {e}")
            _connection = None
            return False


@contextmanager
def get_connection():
    global _connection
    if _connection is None:
        if not initialize_connection_pool():
            raise Exception("Failed to open SQLite connection")
    with _lock:
        yield _connection


@contextmanager
def get_cursor(commit=False):
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()


def execute_query(query, params=None, commit=False):
    """Execute a SQL query and return the results (list of rows), or False on error."""
    query = query.replace('%s', '?')
    try:
        with get_cursor(commit=commit) as cursor:
            cursor.execute(query, params or [])
            if cursor.description is None:
                return []
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error executing query: {e}\nQuery: {query}\nParams: {params}")
        return False


def query_to_dataframe(query, params=None):
    """Execute a query and return results as a pandas DataFrame."""
    query = query.replace('%s', '?')
    try:
        with get_cursor() as cursor:
            cursor.execute(query, params or [])
            if cursor.description is None:
                return pd.DataFrame()
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
        return pd.DataFrame([dict(zip(columns, row)) for row in rows])
    except Exception as e:
        logger.error(f"Error executing query: {e}\nQuery: {query}")
        return pd.DataFrame()


def setup_database_schema():
    """Create all required tables if they don't exist."""
    ddl_statements = [
        """CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,
            status TEXT DEFAULT 'not_trained',
            config TEXT DEFAULT '{}',
            performance TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

        """CREATE TABLE IF NOT EXISTS processed_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            collector TEXT NOT NULL,
            data TEXT NOT NULL,
            features TEXT,
            batch_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",

        """CREATE TABLE IF NOT EXISTS anomalies (
            id TEXT PRIMARY KEY,
            model_id INTEGER REFERENCES models(id),
            model TEXT NOT NULL,
            score REAL NOT NULL,
            threshold REAL DEFAULT 0.5,
            timestamp TEXT NOT NULL,
            detection_time TEXT DEFAULT (datetime('now')),
            location TEXT,
            src_ip TEXT,
            dst_ip TEXT,
            details TEXT DEFAULT '{}',
            features TEXT DEFAULT '[]',
            analysis TEXT DEFAULT '{}',
            status TEXT DEFAULT 'new',
            data TEXT DEFAULT '{}',
            severity TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

        """CREATE TABLE IF NOT EXISTS model_states (
            model_name TEXT PRIMARY KEY,
            model_type TEXT NOT NULL,
            state TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",

        """CREATE TABLE IF NOT EXISTS anomaly_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anomaly_id TEXT REFERENCES anomalies(id) ON DELETE CASCADE,
            model TEXT,
            score REAL,
            timestamp TEXT DEFAULT (datetime('now')),
            analysis_content TEXT DEFAULT '{}',
            remediation_content TEXT DEFAULT '{}',
            reflection_content TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

        """CREATE TABLE IF NOT EXISTS agent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anomaly_id TEXT REFERENCES anomalies(id) ON DELETE SET NULL,
            agent_id TEXT,
            agent TEXT,
            message TEXT,
            content TEXT,
            message_type TEXT DEFAULT 'info',
            timestamp TEXT DEFAULT (datetime('now')),
            job_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            agent_name TEXT
        )""",

        """CREATE TABLE IF NOT EXISTS agent_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anomaly_id TEXT REFERENCES anomalies(id) ON DELETE SET NULL,
            agent_id TEXT,
            agent TEXT,
            activity_type TEXT,
            action TEXT,
            description TEXT,
            status TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            details TEXT DEFAULT '{}',
            job_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            agent_name TEXT
        )""",

        """CREATE TABLE IF NOT EXISTS system_status (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

        """CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            job_type TEXT,
            status TEXT DEFAULT 'pending',
            progress REAL DEFAULT 0,
            result TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

        """CREATE TABLE IF NOT EXISTS background_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT,
            status TEXT DEFAULT 'pending',
            progress REAL DEFAULT 0,
            result TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

        """CREATE TABLE IF NOT EXISTS processors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,
            status TEXT DEFAULT 'inactive',
            config TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

        """CREATE TABLE IF NOT EXISTS collectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,
            status TEXT DEFAULT 'inactive',
            config TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

        "CREATE INDEX IF NOT EXISTS idx_models_name ON models(name)",
        "CREATE INDEX IF NOT EXISTS idx_models_status ON models(status)",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_model ON anomalies(model)",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_score ON anomalies(score)",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_status ON anomalies(status)",
        "CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity)",
        "CREATE INDEX IF NOT EXISTS idx_agent_messages_anomaly_id ON agent_messages(anomaly_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_messages_job_id ON agent_messages(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_activities_anomaly_id ON agent_activities(anomaly_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_activities_job_id ON agent_activities(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_processed_data_timestamp ON processed_data(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_processed_data_collector ON processed_data(collector)",
    ]

    try:
        with get_cursor(commit=True) as cursor:
            for stmt in ddl_statements:
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    logger.warning(f"DDL warning: {e} | stmt: {stmt[:80]}")
        logger.info("Database schema setup completed")
        return True
    except Exception as e:
        logger.error(f"Error setting up database schema: {e}")
        return False


def update_schema_with_missing_columns():
    """Add columns that may be missing from older schema versions (SQLite ALTER TABLE ADD COLUMN)."""
    additions = [
        ("anomalies", "detection_time", "TEXT DEFAULT (datetime('now'))"),
        ("anomalies", "data", "TEXT DEFAULT '{}'"),
        ("anomalies", "severity", "TEXT"),
        ("agent_messages", "job_id", "TEXT"),
        ("agent_messages", "agent_name", "TEXT"),
        ("agent_messages", "message", "TEXT"),
        ("agent_messages", "content", "TEXT"),
        ("agent_activities", "job_id", "TEXT"),
        ("agent_activities", "agent_name", "TEXT"),
    ]

    try:
        with get_cursor(commit=True) as cursor:
            for table, column, col_def in additions:
                cursor.execute(f"PRAGMA table_info({table})")
                existing_cols = [row[1] for row in cursor.fetchall()]
                if column not in existing_cols:
                    try:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
                        logger.info(f"Added column {table}.{column}")
                    except Exception as e:
                        logger.warning(f"Could not add {table}.{column}: {e}")
        return True
    except Exception as e:
        logger.error(f"Error updating schema: {e}")
        return False


def _parse_json(value, default):
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def get_anomaly_by_id(anomaly_id):
    try:
        query = """
            SELECT id, model_id, model, score, timestamp, detection_time,
                   location, src_ip, dst_ip, details, features, analysis,
                   threshold, status, data, severity, created_at, updated_at
            FROM anomalies WHERE id = ?
        """
        df = query_to_dataframe(query, (anomaly_id,))
        if df.empty:
            return None
        anomaly = df.iloc[0].to_dict()
        for field in ['details', 'features', 'analysis', 'data']:
            default = [] if field == 'features' else {}
            anomaly[field] = _parse_json(anomaly.get(field), default)
        return anomaly
    except Exception as e:
        logger.error(f"Error fetching anomaly by ID: {e}")
        return None


def get_anomaly_analysis(anomaly_id):
    try:
        query = """
            SELECT id, anomaly_id, model, score, timestamp,
                   analysis_content, remediation_content, reflection_content,
                   created_at, updated_at
            FROM anomaly_analysis WHERE anomaly_id = ?
        """
        df = query_to_dataframe(query, (anomaly_id,))
        if df.empty:
            return None
        analysis = df.iloc[0].to_dict()
        for field in ['analysis_content', 'remediation_content', 'reflection_content']:
            analysis[field] = _parse_json(analysis.get(field), {})
        return analysis
    except Exception as e:
        logger.error(f"Error fetching anomaly analysis: {e}")
        return None


def get_agent_messages(anomaly_id):
    try:
        query = """
            SELECT id, agent_id, agent,
                   COALESCE(message, content) as content,
                   message_type, anomaly_id, timestamp, created_at, job_id, agent_name
            FROM agent_messages WHERE anomaly_id = ?
            ORDER BY timestamp
        """
        df = query_to_dataframe(query, (anomaly_id,))
        if df.empty:
            return []
        messages = df.to_dict('records')
        for m in messages:
            if not m.get('agent_id') and m.get('agent'):
                m['agent_id'] = m['agent']
        return messages
    except Exception as e:
        logger.error(f"Error fetching agent messages: {e}")
        return []


def get_agent_activities(anomaly_id=None):
    try:
        if anomaly_id:
            query = """
                SELECT id, agent_id, agent, activity_type, action,
                       description, status, anomaly_id, timestamp, details,
                       created_at, job_id, agent_name
                FROM agent_activities WHERE anomaly_id = ?
                ORDER BY timestamp
            """
            params = (anomaly_id,)
        else:
            query = """
                SELECT id, agent_id, agent, activity_type, action,
                       description, status, anomaly_id, timestamp, details,
                       created_at, job_id, agent_name
                FROM agent_activities ORDER BY timestamp DESC LIMIT 100
            """
            params = None
        df = query_to_dataframe(query, params)
        if df.empty:
            return []
        activities = df.to_dict('records')
        for a in activities:
            if not a.get('agent_id') and a.get('agent'):
                a['agent_id'] = a['agent']
            if not a.get('activity_type') and a.get('action'):
                a['activity_type'] = a['action']
            a['details'] = _parse_json(a.get('details'), {})
        return activities
    except Exception as e:
        logger.error(f"Error fetching agent activities: {e}")
        return []


def get_time_series_data(days=30):
    try:
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
        query = """
            SELECT
                date(timestamp) as date,
                COUNT(*) as anomaly_count,
                SUM(CASE WHEN severity = 'High' THEN 1 ELSE 0 END) as high_severity,
                SUM(CASE WHEN severity = 'Medium' THEN 1 ELSE 0 END) as medium_severity,
                SUM(CASE WHEN severity = 'Low' THEN 1 ELSE 0 END) as low_severity,
                AVG(score) as avg_score
            FROM anomalies
            WHERE timestamp >= ?
            GROUP BY date(timestamp)
            ORDER BY date
        """
        return query_to_dataframe(query, (cutoff,))
    except Exception as e:
        logger.error(f"Error fetching time series data: {e}")
        return pd.DataFrame()


def update_anomaly_status(anomaly_id, status):
    try:
        query = "UPDATE anomalies SET status = ?, updated_at = datetime('now') WHERE id = ?"
        return execute_query(query, (status, anomaly_id), commit=True)
    except Exception as e:
        logger.error(f"Error updating anomaly status: {e}")
        return False


def add_anomaly_analysis(anomaly_id, analysis_data):
    try:
        def _to_json(val):
            return val if isinstance(val, str) else json.dumps(val or {})

        check_df = query_to_dataframe(
            "SELECT id FROM anomaly_analysis WHERE anomaly_id = ?", (anomaly_id,)
        )
        if not check_df.empty:
            query = """
                UPDATE anomaly_analysis
                SET model = ?, score = ?, analysis_content = ?,
                    remediation_content = ?, reflection_content = ?,
                    updated_at = datetime('now')
                WHERE anomaly_id = ?
            """
            params = (
                analysis_data.get('model', 'unknown'),
                float(analysis_data.get('score', 0.0)),
                _to_json(analysis_data.get('analysis', {})),
                _to_json(analysis_data.get('remediation', {})),
                _to_json(analysis_data.get('reflection', {})),
                anomaly_id,
            )
        else:
            query = """
                INSERT INTO anomaly_analysis
                (anomaly_id, model, score, timestamp, analysis_content,
                 remediation_content, reflection_content, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), ?, ?, ?, datetime('now'), datetime('now'))
            """
            params = (
                anomaly_id,
                analysis_data.get('model', 'unknown'),
                float(analysis_data.get('score', 0.0)),
                _to_json(analysis_data.get('analysis', {})),
                _to_json(analysis_data.get('remediation', {})),
                _to_json(analysis_data.get('reflection', {})),
            )
        return execute_query(query, params, commit=True)
    except Exception as e:
        logger.error(f"Error adding anomaly analysis: {e}")
        return False


def add_agent_message(anomaly_id, agent_id, message, message_type="info"):
    try:
        query = """
            INSERT INTO agent_messages
            (anomaly_id, agent_id, agent, message, content, message_type, timestamp, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """
        result = execute_query(
            query,
            (anomaly_id, agent_id, agent_id, message, message, message_type),
            commit=True,
        )
        return result is not None
    except Exception as e:
        logger.error(f"Error adding agent message: {e}")
        return False


def add_agent_activity(agent_id, activity_type, description, anomaly_id=None, details=None):
    try:
        status = "completed"
        if details and isinstance(details, dict):
            status = details.get('status', 'completed')
        elif 'started' in description.lower():
            status = 'started'
        elif 'failed' in description.lower():
            status = 'failed'

        query = """
            INSERT INTO agent_activities
            (agent_id, agent, activity_type, action, description, status,
             anomaly_id, timestamp, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, datetime('now'))
        """
        params = (
            agent_id, agent_id, activity_type, activity_type,
            description, status, anomaly_id,
            json.dumps(details) if details else None,
        )
        result = execute_query(query, params, commit=True)
        return result is not None
    except Exception as e:
        logger.error(f"Error adding agent activity: {e}")
        return False


def test_connection():
    """Test the SQLite connection and ensure schema is up to date.

    Returns:
        tuple: (bool, str)
    """
    try:
        initialize_connection_pool()
        with get_cursor() as cursor:
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
        setup_database_schema()
        update_schema_with_missing_columns()
        return True, f"Connected to SQLite {version} at {DB_PATH}"
    except Exception as e:
        logger.error(f"SQLite connection test failed: {e}")
        return False, f"Connection failed: {str(e)}"


# Initialise on import
initialize_connection_pool()
if _connection is not None:
    setup_database_schema()
    update_schema_with_missing_columns()
