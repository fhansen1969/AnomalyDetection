"""
Data service for the Anomaly Detection Dashboard.
Provides functions for retrieving and manipulating data.
"""

import json
import logging
import datetime
import random
import uuid
import psutil
import platform
from services.database import execute_query, query_to_dataframe

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_system_status():
    """
    Get the current system status from the database or real system metrics.
    
    Returns:
        dict: System status data.
    """
    try:
        # Try to get status from database first
        query = """
            SELECT value 
            FROM system_status 
            WHERE key = 'status'
        """
        
        result = execute_query(query)
        
        db_status = None
        if result and len(result) > 0:
            # Try to parse the JSON value
            try:
                status_json = result[0][0]
                if isinstance(status_json, str):
                    db_status = json.loads(status_json)
                else:
                    db_status = status_json
            except Exception as e:
                logger.error(f"Error parsing system status JSON: {e}")
        
        # Enhance with real system metrics
        return get_real_system_metrics(db_status)
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return get_real_system_metrics(None)

def get_real_system_metrics(base_status=None):
    """Get real-time system metrics using psutil.
    
    Args:
        base_status (dict, optional): Base status to enhance. Defaults to None.
        
    Returns:
        dict: Enhanced system status with real metrics.
    """
    status = base_status or {}
    
    # System uptime
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot_time
    
    # Format uptime as days, hours, minutes
    days, remainder = divmod(uptime.total_seconds(), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m"
    
    # Basic system info
    status["hostname"] = platform.node()
    status["platform"] = platform.system()
    status["platform_version"] = platform.version()
    status["uptime"] = uptime_str
    status["last_update"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # System load
    status["system_load"] = {
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "network": get_network_usage()
    }
    
    # Storage information
    disk = psutil.disk_usage('/')
    status["storage"] = {
        "initialized": True,
        "type": "Local Disk",
        "usage": disk.percent,
        "total_space": bytes_to_human_readable(disk.total),
        "used_space": bytes_to_human_readable(disk.used)
    }
    
    # If we don't have jobs data in the base_status, try to get from DB
    if "jobs" not in status or not isinstance(status["jobs"], dict):
        try:
            # Attempt to get job information from database
            job_data = execute_query("SELECT status, COUNT(*) FROM jobs GROUP BY status")
            
            if job_data:
                job_counts = {row[0]: row[1] for row in job_data}
                
                total_jobs = sum(job_counts.values())
                running_jobs = job_counts.get("running", 0)
                completed_jobs = job_counts.get("completed", 0)
                failed_jobs = job_counts.get("failed", 0)
            else:
                # No job data in database
                total_jobs = 0
                running_jobs = 0
                completed_jobs = 0
                failed_jobs = 0
                
            status["jobs"] = {
                "total": total_jobs,
                "running": running_jobs,
                "completed": completed_jobs,
                "failed": failed_jobs
            }
        except Exception as e:
            logger.error(f"Error getting job info: {e}")
            status["jobs"] = {
                "total": 0,
                "running": 0,
                "completed": 0,
                "failed": 0
            }
    
    # If we don't have model data, try to get from DB
    if "models" not in status or not isinstance(status["models"], dict):
        models_data = get_models()
        
        if models_data:
            models_count = len(models_data)
            models_trained = len([m for m in models_data if m.get('status') == 'trained'])
            models_names = [m.get('name') for m in models_data]
            
            status["models"] = {
                "count": models_count,
                "trained": models_trained,
                "names": models_names
            }
        else:
            status["models"] = {
                "count": 0,
                "trained": 0,
                "names": []
            }
    
    # If processor/collector info not present, try to get from database
    component_types = ["processors", "collectors"]
    for component_type in component_types:
        if component_type not in status or not isinstance(status[component_type], dict):
            try:
                component_table = component_type
                component_data = execute_query(f"SELECT * FROM {component_table}")
                
                if component_data:
                    components = [{"name": row[1], "status": row[2]} for row in component_data]
                    components_count = len(components)
                    components_active = len([c for c in components if c["status"] == "active"])
                    components_names = [c["name"] for c in components]
                else:
                    components_count = 0
                    components_active = 0
                    components_names = []
                    
                status[component_type] = {
                    "count": components_count,
                    "active": components_active,
                    "names": components_names
                }
            except Exception as e:
                logger.error(f"Error getting {component_type} info: {e}")
                status[component_type] = {
                    "count": 0,
                    "active": 0,
                    "names": []
                }
    
    return status

def get_network_usage():
    """Get current network usage percentage (estimated)."""
    try:
        # Get initial network stats
        net_io_counters_start = psutil.net_io_counters()
        
        # Wait for a short time
        import time
        time.sleep(0.1)
        
        # Get updated network stats
        net_io_counters_end = psutil.net_io_counters()
        
        # Calculate the data transferred in this small interval
        bytes_sent = net_io_counters_end.bytes_sent - net_io_counters_start.bytes_sent
        bytes_recv = net_io_counters_end.bytes_recv - net_io_counters_start.bytes_recv
        
        # Convert to a percentage (this is a rough estimation)
        # Assuming 1Gbps network (125 MB/s)
        max_theoretical_bytes = 125 * 1024 * 1024 * 0.1  # Max bytes in 0.1 seconds
        actual_bytes = bytes_sent + bytes_recv
        
        usage_percent = min((actual_bytes / max_theoretical_bytes) * 100, 100)
        return round(usage_percent, 1)
    except Exception as e:
        logger.error(f"Error calculating network usage: {e}")
        return 0.0

def get_process_info():
    """Get information about running processes."""
    processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'username', 'status']):
            try:
                proc_info = proc.info
                processes.append({
                    'pid': proc_info['pid'],
                    'name': proc_info['name'],
                    'user': proc_info['username'],
                    'status': proc_info['status']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"Error getting process info: {e}")
        
    return processes

def check_column_exists(table, column):
    """
    Check if a column exists in a table.
    
    Args:
        table (str): Table name
        column (str): Column name
        
    Returns:
        bool: True if the column exists, False otherwise
    """
    try:
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = %s
                AND column_name = %s
            )
        """
        
        result = execute_query(query, (table, column))
        
        if result and len(result) > 0:
            return result[0][0]
        return False
    except Exception as e:
        logger.error(f"Error checking if column exists: {e}")
        return False
    
def bytes_to_human_readable(bytes_value):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024 or unit == 'TB':
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024

def get_models():
    """
    Get list of available models from the database.
    
    Returns:
        list: List of model dictionaries
    """
    try:
        # First, let's check what columns actually exist
        check_columns_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'models' 
            AND table_schema = 'public'
            ORDER BY ordinal_position;
        """
        
        columns_result = execute_query(check_columns_query)
        
        if columns_result:
            available_columns = [row[0] for row in columns_result]
            logger.info(f"Available columns in models table: {available_columns}")
        else:
            logger.warning("Could not fetch column information")
            available_columns = ['id', 'name', 'type', 'status', 'created_at', 'updated_at']
        
        # Build query based on available columns
        select_columns = []
        for col in ['id', 'name', 'type', 'status', 'config', 'performance', 'created_at', 'updated_at']:
            if col in available_columns:
                select_columns.append(col)
        
        # Build the query
        query = f"""
            SELECT {', '.join(select_columns)}
            FROM models
            ORDER BY id
        """
        
        result = execute_query(query)
        
        # Check if result is False or None (error occurred)
        if result is False or result is None:
            logger.warning("Query execution failed or returned None")
            return []
        
        models = []
        if isinstance(result, list):
            # Map column names to indices
            column_indices = {col: idx for idx, col in enumerate(select_columns)}
            
            for row in result:
                # Create model dictionary
                model = {}
                
                # Add each column value
                for col, idx in column_indices.items():
                    if idx < len(row):
                        model[col] = row[idx]
                    else:
                        model[col] = None
                
                # Set defaults for missing columns
                model.setdefault('id', None)
                model.setdefault('name', 'Unknown')
                model.setdefault('type', 'Unknown')
                model.setdefault('status', 'unknown')
                model.setdefault('config', {})
                model.setdefault('performance', {})
                model.setdefault('created_at', None)
                model.setdefault('updated_at', None)
                
                # Parse JSON fields if they're strings
                for field in ['config', 'performance']:
                    if field in model and model[field] is not None:
                        if isinstance(model[field], str):
                            try:
                                model[field] = json.loads(model[field])
                            except json.JSONDecodeError:
                                logger.warning(f"Could not parse JSON for {field} in model {model.get('name')}")
                                model[field] = {}
                        elif not isinstance(model[field], dict):
                            model[field] = {}
                    else:
                        model[field] = {}
                
                # Ensure performance has default values
                if not model['performance'] or not isinstance(model['performance'], dict):
                    model['performance'] = {
                        'accuracy': 0.0,
                        'precision': 0.0,
                        'recall': 0.0,
                        'f1_score': 0.0
                    }
                else:
                    # Ensure all metrics exist
                    for metric in ['accuracy', 'precision', 'recall', 'f1_score']:
                        if metric not in model['performance']:
                            model['performance'][metric] = 0.0
                
                # Add additional fields for compatibility
                model['metrics'] = model.get('performance', {})
                model['training_time'] = model.get('config', {}).get('training_time', 'N/A')
                
                models.append(model)
        
        logger.info(f"Successfully loaded {len(models)} models from database")
        return models
    
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []
    
   
def get_anomalies(limit=100, min_score=0.5, model=None, severity=None, status=None):
    """
    Get anomalies from the database with optional filtering.
    
    Args:
        limit (int): Maximum number of anomalies to return
        min_score (float): Minimum anomaly score
        model (str, optional): Filter by model name
        severity (list, optional): Filter by severity levels
        status (str, optional): Filter by status
        
    Returns:
        list: List of anomaly dictionaries
    """
    try:
        # Try to check if columns exist first
        has_analysis = check_column_exists("anomalies", "analysis")
        has_detection_time = check_column_exists("anomalies", "detection_time")
        has_severity = check_column_exists("anomalies", "severity")
        has_data = check_column_exists("anomalies", "data")
        
        # Build base query
        base_columns = ["id", "model", "timestamp", "score", "status"]
        
        # Add optional columns if they exist
        opt_columns = ["model_id", "location", "src_ip", "dst_ip", "threshold", 
                     "features", "analysis", "details", "created_at", "updated_at"]
        
        # Add newer columns if they exist
        if has_detection_time:
            opt_columns.append("detection_time")
        if has_data:
            opt_columns.append("data")
        if has_severity:
            opt_columns.append("severity")
        
        # Check each optional column
        final_columns = list(base_columns)  # Start with base columns
        
        for col in opt_columns:
            if check_column_exists("anomalies", col):
                final_columns.append(col)
        
        # Build the query with only the columns we know exist
        column_list = ", ".join(final_columns)
        
        query = f"""
            SELECT 
                {column_list}
            FROM 
                anomalies
            WHERE 
                score >= %s
        """
        
        params = [min_score]
        
        # Add model filter if provided
        if model and model != "All Models":
            query += " AND model = %s"
            params.append(model)
        
        # Add severity filter based on available columns
        if severity and isinstance(severity, list) and len(severity) > 0:
            if has_severity:
                # Use direct severity column
                placeholders = []
                for _ in severity:
                    placeholders.append("severity = %s")
                query += f" AND ({' OR '.join(placeholders)})"
                params.extend(severity)
            elif has_analysis:
                # Use JSONB path to check severity in analysis
                placeholders = []
                for _ in severity:
                    placeholders.append("analysis->>'severity' = %s")
                query += f" AND ({' OR '.join(placeholders)})"
                params.extend(severity)
        
        # Add status filter if provided
        if status:
            query += " AND status = %s"
            params.append(status)
        
        # Order by detection_time if it exists, otherwise by timestamp
        if has_detection_time:
            query += " ORDER BY detection_time DESC LIMIT %s"
        else:
            query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        
        # Execute the query
        result = execute_query(query, tuple(params))
        
        # Check if result is False or None (error occurred)
        if result is False or result is None:
            logger.warning("Query execution failed or returned None")
            return []
        
        anomalies = []
        if isinstance(result, list):
            # Process results based on column order from the SELECT statement
            column_map = {col: idx for idx, col in enumerate(final_columns)}
            
            for row in result:
                # Create a basic anomaly dictionary with fields we know exist
                anomaly = {
                    "id": row[column_map["id"]],
                    "model": row[column_map["model"]],
                    "timestamp": row[column_map["timestamp"]],
                    "score": float(row[column_map["score"]]) if row[column_map["score"]] is not None else 0.0,
                    "status": row[column_map["status"]],
                    # Add placeholders for optional fields
                    "model_id": None,
                    "location": "unknown",
                    "src_ip": None,
                    "dst_ip": None,
                    "threshold": 0.5,
                    "features": {},
                    "analysis": {"severity": "Unknown"},
                    "details": {},
                    "created_at": datetime.datetime.now().isoformat(),
                    "updated_at": datetime.datetime.now().isoformat(),
                    "data": {},
                    "severity": "Unknown"
                }
                
                # Fill in optional fields if they exist in results
                for col in opt_columns:
                    if col in column_map:
                        val = row[column_map[col]]
                        
                        # Special handling for JSON fields
                        if col in ["analysis", "features", "details", "data"] and isinstance(val, str):
                            try:
                                import json
                                anomaly[col] = json.loads(val)
                            except json.JSONDecodeError:
                                # Initialize as default if parsing fails
                                if col == "analysis":
                                    anomaly[col] = {"severity": "Unknown"}
                                elif col == "features":
                                    anomaly[col] = {}
                                elif col == "details":
                                    anomaly[col] = {}
                                elif col == "data":
                                    anomaly[col] = {}
                        else:
                            anomaly[col] = val
                
                # Extract severity from dedicated field or analysis field
                if "severity" in column_map and anomaly["severity"] is not None:
                    # Use direct severity field
                    pass
                elif "analysis" in column_map and isinstance(anomaly["analysis"], dict):
                    # Extract from analysis
                    anomaly["severity"] = anomaly["analysis"].get("severity", "Unknown")
                
                # Ensure detection_time is set
                if "detection_time" not in column_map or anomaly["detection_time"] is None:
                    anomaly["detection_time"] = anomaly["timestamp"]
                
                anomalies.append(anomaly)
        
        return anomalies
    
    except Exception as e:
        logger.error(f"Error getting anomalies: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []
        
def get_time_series_data(days=30):
    """
    Get time series data for anomalies.
    
    Args:
        days (int): Number of days to include in the time series
        
    Returns:
        dict: Dictionary containing time series data
    """
    try:
        # Use a simple query that should work with the minimal schema
        query = """
            SELECT 
                DATE(timestamp) as date, 
                COUNT(*) as count
            FROM 
                anomalies
            WHERE 
                timestamp >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY 
                DATE(timestamp)
            ORDER BY 
                date
        """
        
        result = execute_query(query, (days,))
        
        # Check if result is False or None (error occurred)
        if result is False or result is None:
            logger.warning("Query execution failed or returned None")
            return {"data": [], "total": 0, "days": days}
        
        if isinstance(result, list) and len(result) > 0:
            # Process results if we have data
            import pandas as pd
            
            # Basic time series without severity
            df = pd.DataFrame(result, columns=["date", "count"])
            
            # Convert to the expected format
            data = []
            
            for _, row in df.iterrows():
                date = row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])
                count = int(row["count"])
                
                # Simulate severity distribution
                high = int(count * 0.3)
                medium = int(count * 0.4)
                low = count - high - medium
                
                entry = {
                    "date": date,
                    "high_severity": high,
                    "medium_severity": medium,
                    "low_severity": low
                }
                data.append(entry)
            
            return {
                "data": data,
                "total": sum(df["count"]),
                "days": days
            }
        
        # If no data, return empty result
        return {"data": [], "total": 0, "days": days}
    except Exception as e:
        logger.error(f"Error generating time series data: {e}")
        return {"data": [], "total": 0, "days": days}
        
def get_anomaly_by_id(anomaly_id):
    """
    Get a specific anomaly by its ID.
    
    Args:
        anomaly_id (str): ID of the anomaly to retrieve
        
    Returns:
        dict: Anomaly data dictionary or None if not found
    """
    try:
        # Check if columns exist
        has_detection_time = check_column_exists("anomalies", "detection_time")
        has_data = check_column_exists("anomalies", "data")
        has_severity = check_column_exists("anomalies", "severity")
        has_features = check_column_exists("anomalies", "features")
        has_details = check_column_exists("anomalies", "details")
        
        # Build query based on available columns
        columns = [
            "id", "model", "timestamp", "score", "status", 
            "model_id", "location", "src_ip", "dst_ip", 
            "threshold", "analysis", "created_at", "updated_at"
        ]
        
        # Add optional columns if they exist
        if has_detection_time:
            columns.append("detection_time")
        if has_data:
            columns.append("data")
        if has_severity:
            columns.append("severity")
        if has_features:
            columns.append("features")
        if has_details:
            columns.append("details")
        
        query = f"""
            SELECT 
                {', '.join(columns)}
            FROM 
                anomalies
            WHERE 
                id = %s
        """
        
        result = execute_query(query, (anomaly_id,))
        
        if result and isinstance(result, list) and len(result) > 0:
            # Process the first row
            row = result[0]
            
            # Create anomaly dictionary
            anomaly = {}
            for i, col in enumerate(columns):
                anomaly[col] = row[i]
            
            # Ensure detection_time exists
            if "detection_time" not in anomaly or anomaly["detection_time"] is None:
                anomaly["detection_time"] = anomaly["timestamp"]
            
            # Ensure data field exists
            if "data" not in anomaly or anomaly["data"] is None:
                anomaly["data"] = {}
            
            # Ensure features field exists
            if "features" not in anomaly or anomaly["features"] is None:
                anomaly["features"] = []
            
            # Ensure details field exists
            if "details" not in anomaly or anomaly["details"] is None:
                anomaly["details"] = {}
            
            # Try to parse JSON fields
            for field in ["analysis", "features", "details", "data"]:
                if field in anomaly and isinstance(anomaly[field], str):
                    try:
                        anomaly[field] = json.loads(anomaly[field])
                    except:
                        # Initialize as empty if parsing fails
                        anomaly[field] = {} if field != "features" else []
                
                # Ensure field exists with default value
                if field not in anomaly or anomaly[field] is None:
                    anomaly[field] = {} if field != "features" else []
            
            # Extract severity from analysis if not available directly
            if "severity" not in anomaly or anomaly["severity"] is None:
                if isinstance(anomaly["analysis"], dict):
                    anomaly["severity"] = anomaly["analysis"].get("severity", "Unknown")
                else:
                    anomaly["severity"] = "Unknown"
            
            return anomaly
        
        # If not found in database, return None
        return None
    
    except Exception as e:
        logger.error(f"Error retrieving anomaly by ID: {e}")
        return None

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
                    timestamp = NOW()
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
            
            return execute_query(update_query, params)
        else:
            # Insert new analysis
            insert_query = """
                INSERT INTO anomaly_analysis (
                    anomaly_id, model, score, timestamp, 
                    analysis_content, remediation_content, reflection_content
                )
                VALUES (%s, %s, %s, NOW(), %s, %s, %s)
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
            
            return execute_query(insert_query, params)
    except Exception as e:
        logger.error(f"Error adding anomaly analysis: {e}")
        return False

def add_agent_message(anomaly_id, agent_id, message, message_type="info"):
    """
    Add a message from an agent regarding an anomaly investigation.
    
    Args:
        anomaly_id (str): ID of the anomaly
        agent_id (str): ID of the agent
        message (str): Message content
        message_type (str, optional): Message type. Defaults to "info".
            Can be: "info", "warning", "error", "success", "question", "answer"
        
    Returns:
        bool: Success flag
    """
    try:
        # Insert message into database with both message and content fields
        query = """
            INSERT INTO agent_messages
            (anomaly_id, agent_id, agent, message, content, message_type, timestamp, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        
        result = execute_query(
            query, 
            (anomaly_id, agent_id, agent_id, message, message, message_type),
            commit=True
        )
        
        return result is not False
    
    except Exception as e:
        import logging
        logging.error(f"Error adding agent message: {e}")
        return False
    
def add_agent_activity(agent_id, activity_type, description, anomaly_id=None, details=None):
    """
    Add an agent activity record.
    
    Args:
        agent_id (str): ID of the agent
        activity_type (str): Type of activity (e.g., "analysis_started", "investigation")
        description (str): Brief description of the activity
        anomaly_id (str, optional): Related anomaly ID, if applicable
        details (dict, optional): Additional activity details
        
    Returns:
        bool: Success flag
    """
    try:
        # Convert details to JSON if it's a dict
        if isinstance(details, dict):
            import json
            details_json = json.dumps(details)
        else:
            details_json = details
        
        # Determine status from details or description
        status = "completed"
        if isinstance(details, dict) and "status" in details:
            status = details["status"]
        elif "started" in description.lower():
            status = "started"
        elif "completed" in description.lower():
            status = "completed"
        elif "failed" in description.lower():
            status = "failed"
        
        # Insert activity into database
        query = """
            INSERT INTO agent_activities
            (agent_id, agent, activity_type, action, description, status, anomaly_id, timestamp, details, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
        """
        
        result = execute_query(
            query, 
            (agent_id, agent_id, activity_type, activity_type, description, status, anomaly_id, details_json),
            commit=True
        )
        
        return result is not False
    
    except Exception as e:
        import logging
        logging.error(f"Error adding agent activity: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False
    
def get_anomaly_analysis(anomaly_id):
    """
    Get analysis data for a specific anomaly.
    
    Args:
        anomaly_id (str): ID of the anomaly
        
    Returns:
        dict: Analysis data or None if not found
    """
    try:
        # First, check what columns actually exist in the table
        check_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'anomaly_analysis'
        """
        
        columns_result = execute_query(check_query)
        existing_columns = [row[0] for row in columns_result] if columns_result else []
        
        # Build a query based on columns that actually exist
        select_columns = ["anomaly_id"]
        
        # Add columns that we expect might exist
        for col in ["analysis_content", "remediation_content", "reflection_content", 
                  "model", "score", "timestamp", "created_at", "updated_at"]:
            if col in existing_columns:
                select_columns.append(col)
        
        # Fall back to basic columns if none of our expected columns exist
        if len(select_columns) <= 1:
            select_columns = ["anomaly_id"]
            # Add all columns except id
            for col in existing_columns:
                if col != "id" and col != "anomaly_id":
                    select_columns.append(col)
        
        # Build the query
        query = f"""
            SELECT {', '.join(select_columns)}
            FROM 
                anomaly_analysis
            WHERE 
                anomaly_id = %s
            ORDER BY
                id DESC
            LIMIT 1
        """
        
        result = execute_query(query, (anomaly_id,))
        
        if result and isinstance(result, list) and len(result) > 0:
            row = result[0]
            
            # Create analysis dictionary
            analysis = {"anomaly_id": row[0]}
            
            # Add remaining columns dynamically
            for i, col in enumerate(select_columns[1:], 1):
                if i < len(row):
                    analysis[col] = row[i]
            
            # For backward compatibility, make sure we have these fields
            expected_fields = ["analysis_content", "remediation_content", "reflection_content"]
            for field in expected_fields:
                if field not in analysis:
                    analysis[field] = {}
            
            # Parse JSON fields
            json_fields = ["analysis_content", "remediation_content", "reflection_content"]
            for field in json_fields:
                if field in analysis and analysis[field] is not None:
                    if isinstance(analysis[field], str):
                        try:
                            analysis[field] = json.loads(analysis[field])
                        except:
                            # If parsing fails, initialize as empty dict
                            analysis[field] = {}
            
            return analysis
        
        # If no analysis found, return None
        return None
    
    except Exception as e:
        logger.error(f"Error retrieving anomaly analysis: {e}")
        return None

def get_model_by_id(model_id):
    """
    Get a specific model by its ID.
    
    Args:
        model_id (str): ID of the model to retrieve
        
    Returns:
        dict: Model data dictionary or None if not found
    """
    try:
        query = """
            SELECT 
                id,
                name,
                description,
                type,
                status,
                metrics,
                config,
                created_at,
                updated_at
            FROM 
                models
            WHERE 
                id = %s
        """
        
        result = execute_query(query, (model_id,))
        
        if result and len(result) > 0:
            row = result[0]
            
            # Create model dictionary
            model = {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "type": row[3],
                "status": row[4],
                "metrics": row[5],
                "config": row[6],
                "created_at": row[7],
                "updated_at": row[8]
            }
            
            # Try to parse the metrics and config as JSON
            for key in ["metrics", "config"]:
                if isinstance(model[key], str):
                    try:
                        model[key] = json.loads(model[key])
                    except:
                        model[key] = {}
            
            return model
        
        return None
    
    except Exception as e:
        logger.error(f"Error getting model by ID: {e}")
        return None

def update_anomaly_status(anomaly_id, status):
    """
    Update the status of an anomaly.
    
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
        
        result = execute_query(query, (status, anomaly_id), commit=True)
        
        return result
    except Exception as e:
        logger.error(f"Error updating anomaly status: {e}")
        return False

def get_agent_info(agent_id=None):
    """
    Get information about available agents.
    
    Args:
        agent_id (str, optional): Specific agent ID to retrieve
        
    Returns:
        dict or list: Agent information
    """
    try:
        if agent_id:
            query = """
                SELECT id, name, type, status, capabilities, config, created_at
                FROM agents
                WHERE id = %s
            """
            result = execute_query(query, (agent_id,))
            
            if result and len(result) > 0:
                row = result[0]
                
                agent = {
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "status": row[3],
                    "capabilities": row[4],
                    "config": row[5],
                    "created_at": row[6]
                }
                
                # Parse JSON fields
                for key in ["capabilities", "config"]:
                    if isinstance(agent[key], str):
                        try:
                            agent[key] = json.loads(agent[key])
                        except:
                            agent[key] = {}
                
                return agent
            else:
                return None
        else:
            query = """
                SELECT id, name, type, status, capabilities, created_at
                FROM agents
            """
            result = execute_query(query)
            
            agents = []
            if result:
                for row in result:
                    agent = {
                        "id": row[0],
                        "name": row[1],
                        "type": row[2],
                        "status": row[3],
                        "capabilities": row[4],
                        "created_at": row[5]
                    }
                    
                    # Parse capabilities JSON
                    if isinstance(agent["capabilities"], str):
                        try:
                            agent["capabilities"] = json.loads(agent["capabilities"])
                        except:
                            agent["capabilities"] = {}
                    
                    agents.append(agent)
            
            return agents
    except Exception as e:
        logger.error(f"Error getting agent info: {e}")
        return [] if agent_id is None else None

def get_agent_activities(anomaly_id=None, agent_id=None, limit=20):
    """
    Get agent activities.
    
    Args:
        anomaly_id (str, optional): Filter by anomaly ID. Defaults to None.
        agent_id (str, optional): Filter by agent ID. Defaults to None.
        limit (int, optional): Limit number of activities. Defaults to 20.
        
    Returns:
        list: List of activity dictionaries
    """
    try:
        base_query = """
            SELECT 
                id,
                agent,
                action,
                status,
                anomaly_id,
                details,
                timestamp
            FROM 
                agent_activities
            WHERE 1=1
        """
        
        params = []
        
        # Add filters
        if anomaly_id:
            base_query += " AND anomaly_id = %s"
            params.append(anomaly_id)
            
        if agent_id:
            base_query += " AND agent = %s"
            params.append(agent_id)
        
        # Add ordering and limit
        base_query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        
        # Execute query
        result = execute_query(base_query, tuple(params))
        
        activities = []
        if result and isinstance(result, list):
            for row in result:
                activity = {
                    "id": row[0],
                    "agent": row[1],
                    "action": row[2],
                    "status": row[3],
                    "anomaly_id": row[4],
                    "details": row[5],
                    "timestamp": row[6]
                }
                
                # Parse details as JSON if it's a string
                if isinstance(activity["details"], str):
                    try:
                        import json
                        activity["details"] = json.loads(activity["details"])
                    except:
                        # If parsing fails, keep as is
                        pass
                
                activities.append(activity)
        
        return activities
    
    except Exception as e:
        import logging
        logging.error(f"Error getting agent activities: {e}")
        return []

def get_agent_messages(anomaly_id=None, agent_id=None, limit=100):
    """
    Get agent messages.
    
    Args:
        anomaly_id (str, optional): Filter by anomaly ID. Defaults to None.
        agent_id (str, optional): Filter by agent ID. Defaults to None.
        limit (int, optional): Limit number of messages. Defaults to 100.
        
    Returns:
        list: List of message dictionaries
    """
    try:
        base_query = """
            SELECT 
                id,
                anomaly_id,
                agent,
                content,
                timestamp,
                timestamp
            FROM 
                agent_messages
            WHERE 1=1
        """
        
        params = []
        
        # Add filters
        if anomaly_id:
            base_query += " AND anomaly_id = %s"
            params.append(anomaly_id)
            
        if agent_id:
            base_query += " AND agent = %s"
            params.append(agent_id)
        
        # Add ordering and limit
        base_query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        
        # Execute query
        result = execute_query(base_query, tuple(params))
        
        messages = []
        if result and isinstance(result, list):
            for row in result:
                message = {
                    "id": row[0],
                    "anomaly_id": row[1],
                    "agent": row[2],
                    "content": row[3],
                    "timestamp": row[4],
                    "created_at": row[5]
                }
                messages.append(message)
                
            return messages
        
        # If no messages in database, return empty list
        return []
    
    except Exception as e:
        import logging
        logging.error(f"Error getting agent messages: {e}")
        return []