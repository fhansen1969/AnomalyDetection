"""
SQL data collector for the anomaly detection system.

This module provides functionality to collect data from SQL databases
for further processing and analysis.
"""

import logging
import datetime
import json
from typing import Dict, List, Any, Optional

# Database connectors
try:
    import sqlalchemy
    from sqlalchemy import create_engine, text
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logging.warning("SQLAlchemy not installed. SQLCollector will not work.")

from anomaly_detection.collectors.base import Collector


class SQLCollector(Collector):
    """
    Collector implementation for SQL database sources.
    
    This collector executes SQL queries against configured databases and
    converts the result sets to the internal data format.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], storage_manager=None):
        """
        Initialize SQL collector with configuration.
        
        Args:
            name: Collector name
            config: SQL collector configuration
            storage_manager: Optional storage manager for persistence
        """
        super().__init__(name, config)
        self.storage_manager = storage_manager
        
        if not SQLALCHEMY_AVAILABLE:
            self.logger.error("SQLAlchemy not installed. SQLCollector will not work.")
            return
        
        # Connection configuration
        self.connections = config.get("connections", [])
        self.batch_size = config.get("batch_size", 1000)
        self.timeout = config.get("timeout_seconds", 300)
        
        # Cache for database engines
        self._engines = {}
        
        self.logger.info(f"Initialized SQL collector with {len(self.connections)} connection configurations")
    
    def _get_engine(self, connection_config):
        """Get or create a SQLAlchemy engine for the given connection config."""
        connection_name = connection_config.get("name", "default")
        
        if connection_name in self._engines:
            return self._engines[connection_name]
        
        # Create connection string
        dialect = connection_config.get("dialect", "postgresql")
        driver = connection_config.get("driver", "")
        if driver:
            dialect_str = f"{dialect}+{driver}"
        else:
            dialect_str = dialect
            
        host = connection_config.get("host", "localhost")
        port = connection_config.get("port", "")
        if port:
            host_str = f"{host}:{port}"
        else:
            host_str = host
            
        database = connection_config.get("database", "")
        user = connection_config.get("user", "")
        password = connection_config.get("password", "")
        
        # Handle different authentication methods
        if user and password:
            auth_str = f"{user}:{password}@"
        elif user:
            auth_str = f"{user}@"
        else:
            auth_str = ""
        
        # Create connection string
        conn_str = f"{dialect_str}://{auth_str}{host_str}/{database}"
        
        # Add connection options if specified
        options = connection_config.get("options", {})
        if options:
            option_strs = []
            for key, value in options.items():
                option_strs.append(f"{key}={value}")
            conn_str += "?" + "&".join(option_strs)
        
        # Create engine with appropriate configuration
        connect_args = connection_config.get("connect_args", {})
        engine = create_engine(
            conn_str,
            connect_args=connect_args,
            pool_size=connection_config.get("pool_size", 5),
            max_overflow=connection_config.get("max_overflow", 10),
            pool_timeout=connection_config.get("pool_timeout", 30),
            pool_recycle=connection_config.get("pool_recycle", 3600),
        )
        
        self._engines[connection_name] = engine
        self.logger.debug(f"Created database engine for connection {connection_name}")
        
        return engine
    
    def collect(self) -> List[Dict[str, Any]]:
        """
        Collect data from SQL databases using configured queries.
        
        Returns:
            List of collected data items as dictionaries
        """
        if not SQLALCHEMY_AVAILABLE:
            self.logger.error("SQLAlchemy not installed. Cannot collect data.")
            return []
        
        results = []
        
        for connection_config in self.connections:
            connection_name = connection_config.get("name", "default")
            queries = connection_config.get("queries", [])
            
            if not queries:
                self.logger.warning(f"No queries configured for connection {connection_name}")
                continue
            
            try:
                # Get or create engine
                engine = self._get_engine(connection_config)
                
                # Execute each query
                for query_config in queries:
                    query_name = query_config.get("name", "unnamed")
                    query_sql = query_config.get("sql", "")
                    query_params = query_config.get("params", {})
                    max_rows = query_config.get("max_rows", self.batch_size)
                    
                    if not query_sql:
                        self.logger.warning(f"Empty SQL for query {query_name} on connection {connection_name}")
                        continue
                    
                    self.logger.info(f"Executing query {query_name} on connection {connection_name}")
                    
                    # Execute query with parameters
                    try:
                        with engine.connect() as conn:
                            # Set query timeout if supported
                            if hasattr(conn, 'execution_options'):
                                conn = conn.execution_options(timeout=self.timeout)
                            
                            # Execute query
                            result_proxy = conn.execute(text(query_sql), query_params)
                            
                            # Process results
                            row_count = 0
                            for row in result_proxy:
                                # Convert row to dict
                                row_dict = dict(row._mapping)
                                
                                # Add metadata
                                row_dict["_source"] = {
                                    "collector": self.name,
                                    "connection": connection_name,
                                    "query": query_name,
                                    "timestamp": datetime.datetime.utcnow().isoformat()
                                }
                                
                                results.append(row_dict)
                                row_count += 1
                                
                                if row_count >= max_rows:
                                    self.logger.info(f"Reached max rows limit ({max_rows}) for query {query_name}")
                                    break
                            
                            self.logger.info(f"Collected {row_count} rows from query {query_name}")
                    
                    except Exception as e:
                        self.logger.error(f"Error executing query {query_name} on connection {connection_name}: {str(e)}")
            
            except Exception as e:
                self.logger.error(f"Error connecting to database {connection_name}: {str(e)}")
        
        self.logger.info(f"Total data items collected from SQL sources: {len(results)}")
        return results