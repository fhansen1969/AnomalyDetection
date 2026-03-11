"""
Reset the database for the Anomaly Detection Dashboard.
This script drops all tables and recreates them from scratch.
"""

import os
import sys
import yaml
import psycopg2
import logging
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

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

def reset_database():
    """Reset the database by dropping all tables and recreating them."""
    # Load configuration
    config = load_config()
    
    if not config:
        logger.error("Failed to load configuration. Aborting.")
        return False
    
    # Get database configuration
    db_config = config['config']['database']['connection']
    logger.info(f"Loaded database configuration: Host={db_config['host']}, Database={db_config['database']}")
    
    # Confirm before proceeding
    print("\n" + "="*80)
    print("WARNING: This will drop all tables in the database and recreate them.")
    print("All existing data will be lost!")
    print("="*80 + "\n")
    
    confirm = input("Are you sure you want to proceed? (y/n): ")
    if confirm.lower() != 'y':
        logger.info("Operation cancelled by user.")
        return False
    
    # Connect to the database
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"]
        )
        conn.autocommit = True
        cursor = conn.cursor()
        logger.info("Connected to database successfully")
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        logger.error("Make sure PostgreSQL is running and the database exists.")
        return False
    
    try:
        # Drop all tables
        logger.info("Dropping all tables...")
        drop_tables = """
        DROP TABLE IF EXISTS agent_messages CASCADE;
        DROP TABLE IF EXISTS agent_activities CASCADE;
        DROP TABLE IF EXISTS anomaly_analysis CASCADE;
        DROP TABLE IF EXISTS anomalies CASCADE;
        DROP TABLE IF EXISTS jobs CASCADE;
        DROP TABLE IF EXISTS models CASCADE;
        DROP TABLE IF EXISTS system_status CASCADE;
        """
        cursor.execute(drop_tables)
        logger.info("All tables dropped successfully")
        
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")
        return False
    finally:
        cursor.close()
        conn.close()
    
    # Now run init_db.py as a separate process
    logger.info("Reinitializing database...")
    init_db_path = os.path.join(current_dir, 'init_db.py')
    
    if not os.path.exists(init_db_path):
        logger.error(f"init_db.py not found at {init_db_path}")
        return False
    
    # Run the init_db.py as a separate process
    try:
        result = subprocess.run(
            [sys.executable, init_db_path],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Check if initialization was successful
        if result.returncode == 0:
            logger.info("Database reset and reinitialization completed successfully!")
            return True
        else:
            logger.error(f"Error initializing database: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error running initialization script: {e}")
        return False

if __name__ == "__main__":
    success = reset_database()
    if not success:
        logger.error("Database reset failed.")
        sys.exit(1)
