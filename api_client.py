"""
API client for the anomaly detection system.

This module provides client functionality to interact with the
anomaly detection system's REST APIs.
"""

import os
import sys
import json
import time
import argparse
import requests
import asyncio
import websockets
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator
from datetime import datetime, timedelta
import logging
import textwrap


class AnomalyDetectionClient:
    """
    Client for interacting with the anomaly detection API.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the client with the API base URL.
        
        Args:
            base_url: Base URL of the API service
        """
        self.base_url = base_url
        self.ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.logger = logging.getLogger("anomaly_client")
    
    def _request(self, method: str, endpoint: str, data: Any = None, params: Dict[str, Any] = None, timeout: int = 300) -> Dict[str, Any]:
        """
        Make a request to the API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request data
            params: Query parameters
            timeout: Request timeout in seconds (default: 300 for long-running operations)
            
        Returns:
            Response from the API
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, params=params, timeout=timeout)
            elif method == "POST":
                response = requests.post(url, json=data, params=params, timeout=timeout)
            elif method == "DELETE":
                response = requests.delete(url, json=data, params=params, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                return response.json()
            except json.JSONDecodeError:
                # If response is not JSON, return a dict with the text
                return {"response": response.text, "status_code": response.status_code}
                
        except requests.exceptions.Timeout:
            self.logger.error(f"Request to {url} timed out")
            raise Exception(f"Request timed out: {url}")
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error for {url}: {str(e)}")
            raise Exception(f"Connection error: Could not connect to {url}. Is the server running?")
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error for {url}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json().get('detail', str(e))
                    self.logger.error(f"API error detail: {error_detail}")
                    raise Exception(f"API error: {error_detail}")
                except (json.JSONDecodeError, AttributeError):
                    raise Exception(f"API error ({e.response.status_code}): {e.response.text[:200]}")
            else:
                raise Exception(f"HTTP error: {str(e)}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error for {url}: {str(e)}")
            raise Exception(f"Request error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error making request to {url}: {str(e)}")
            raise Exception(f"Unexpected error: {str(e)}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the API service.
        
        Returns:
            Health check response
        """
        return self._request("GET", "/health")
    
    def initialize_system(self, config_path: str, auto_init: bool = False) -> Dict[str, Any]:
        """
        Initialize the system with a configuration file.
        
        Args:
            config_path: Path to configuration file
            auto_init: Automatically initialize system
            
        Returns:
            Initialization response
        """
        return self._request("POST", "/init", {
            "config_path": config_path,
            "auto_init": auto_init
        })
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current system configuration.
        
        Returns:
            Current configuration
        """
        return self._request("GET", "/config")
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        List all available models.
        
        Returns:
            List of model information
        """
        return self._request("GET", "/models")
    
    def create_model(self, model_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new model.
        
        Args:
            model_type: Type of model to create
            config: Model configuration
            
        Returns:
            Model creation response
        """
        return self._request("POST", "/models/create", {
            "type": model_type,
            "config": config
        })
    
    def train_model(self, model_name: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Train a model with the provided data.
        
        Args:
            model_name: Name of the model to train
            data: Training data
            
        Returns:
            Job status information
        """
        return self._request("POST", f"/models/{model_name}/train", {"items": data})
    
    def detect_anomalies(self, model_name: str, data: List[Dict[str, Any]], threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Detect anomalies in the provided data.
        
        Args:
            model_name: Name of the model to use
            data: Data for anomaly detection
            threshold: Optional detection threshold (default is 0.5)
            
        Returns:
            Job status information
        """
        payload = {"items": data}
        params = {}
        if threshold is not None:
            params["threshold"] = threshold
        return self._request("POST", f"/models/{model_name}/detect", payload, params=params)
    
    def detect_anomalies_simple(self, model_name: str, data: List[Dict[str, Any]], threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Simplified anomaly detection endpoint.
        
        Args:
            model_name: Name of the model to use
            data: Data for anomaly detection
            threshold: Optional detection threshold
            
        Returns:
            Job status information
        """
        payload = {
            "model_name": model_name,
            "data": data
        }
        if threshold is not None:
            payload["threshold"] = threshold
        return self._request("POST", "/detect", payload)
    
    def bulk_detect_anomalies(self, models: List[str], data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect anomalies using multiple models.
        
        Args:
            models: List of model names
            data: Data for anomaly detection
            
        Returns:
            Job status information
        """
        return self._request("POST", "/bulk-detect", {
            "models": models,
            "data": data
        })
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a background job.
        
        Args:
            job_id: ID of the job to check
            
        Returns:
            Job status information
        """
        return self._request("GET", f"/jobs/{job_id}")
    
    def list_jobs(self, status: Optional[str] = None, job_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List background jobs.
        
        Args:
            status: Filter by status
            job_type: Filter by job type
            limit: Maximum number of jobs
            
        Returns:
            List of job status information
        """
        params = {"limit": limit}
        if status:
            params["status"] = status
        if job_type:
            params["job_type"] = job_type
        return self._request("GET", "/jobs", params=params)
    
    def list_anomalies(self, model: Optional[str] = None, min_score: float = 0.0, 
                  status: Optional[str] = None, severity: Optional[str] = None, 
                  limit: int = 100) -> List[Dict[str, Any]]:
        """
        List detected anomalies.
        
        Args:
            model: Filter by model name
            min_score: Minimum anomaly score
            status: Filter by status
            severity: Filter by severity
            limit: Maximum number of anomalies
            
        Returns:
            List of anomaly objects
        """
        params = {
            "min_score": min_score,
            "limit": limit
        }
        if model:
            params["model"] = model
        if status:
            params["status"] = status
        if severity:
            params["severity"] = severity
        return self._request("GET", "/anomalies", params=params)
    
    def store_anomalies(self, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Store anomalies explicitly in the database.
        
        Args:
            anomalies: List of anomalies to store
            
        Returns:
            Storage status
        """
        return self._request("POST", "/anomalies/store", anomalies)
    
    def correlate_anomalies(self, anomaly_id: str, time_window_hours: int = 24, 
                           min_correlation_score: float = 0.3, max_results: int = 50) -> Dict[str, Any]:
        """
        Analyze correlations for a specific anomaly (async).
        
        Args:
            anomaly_id: ID of the anomaly to analyze
            time_window_hours: Time window in hours
            min_correlation_score: Minimum correlation score
            max_results: Maximum results
            
        Returns:
            Job status information
        """
        return self._request("POST", "/anomalies/correlate", {
            "anomaly_id": anomaly_id,
            "time_window_hours": time_window_hours,
            "min_correlation_score": min_correlation_score,
            "max_results": max_results
        })
    
    def get_anomaly_correlations(self, anomaly_id: str, time_window_hours: int = 24,
                                min_correlation_score: float = 0.3, max_results: int = 50) -> Dict[str, Any]:
        """
        Get correlations for a specific anomaly (synchronous).
        
        Args:
            anomaly_id: ID of the anomaly
            time_window_hours: Time window in hours
            min_correlation_score: Minimum correlation score
            max_results: Maximum results
            
        Returns:
            Correlation analysis results
        """
        params = {
            "time_window_hours": time_window_hours,
            "min_correlation_score": min_correlation_score,
            "max_results": max_results
        }
        return self._request("GET", f"/anomalies/{anomaly_id}/correlations", params=params)
    
    def bulk_correlate_anomalies(self, anomaly_ids: List[str], cross_correlate: bool = False,
                                time_window_hours: int = 24, min_correlation_score: float = 0.3) -> Dict[str, Any]:
        """
        Analyze correlations for multiple anomalies.
        
        Args:
            anomaly_ids: List of anomaly IDs
            cross_correlate: Whether to cross-correlate between provided anomalies
            time_window_hours: Time window in hours
            min_correlation_score: Minimum correlation score
            
        Returns:
            Bulk correlation results
        """
        return self._request("POST", "/anomalies/bulk-correlate", {
            "anomaly_ids": anomaly_ids,
            "cross_correlate": cross_correlate,
            "time_window_hours": time_window_hours,
            "min_correlation_score": min_correlation_score
        })
    
    def generate_correlation_matrix(self, anomaly_ids: List[str], include_metadata: bool = True) -> Dict[str, Any]:
        """
        Generate a correlation matrix for specified anomalies.
        
        Args:
            anomaly_ids: List of anomaly IDs (2-50)
            include_metadata: Include anomaly metadata in response
            
        Returns:
            Correlation matrix and metadata
        """
        if not anomaly_ids or not isinstance(anomaly_ids, list):
            raise ValueError("anomaly_ids must be a non-empty list")
        
        if len(anomaly_ids) < 2:
            raise ValueError("At least 2 anomaly IDs required for correlation matrix")
        
        if len(anomaly_ids) > 50:
            raise ValueError("Maximum 50 anomaly IDs allowed for correlation matrix")
        
        try:
            return self._request("POST", "/anomalies/correlation-matrix", {
                "anomaly_ids": anomaly_ids,
                "include_metadata": include_metadata
            })
        except Exception as e:
            self.logger.error(f"Error generating correlation matrix: {e}")
            raise
    
    def get_correlation_statistics(self, time_window_hours: int = 24, min_correlation_score: float = 0.3) -> Dict[str, Any]:
        """
        Get overall correlation statistics for recent anomalies.
        
        Args:
            time_window_hours: Time window in hours
            min_correlation_score: Minimum correlation score
            
        Returns:
            Correlation statistics
        """
        params = {
            "time_window_hours": time_window_hours,
            "min_correlation_score": min_correlation_score
        }
        return self._request("GET", "/anomalies/correlation-stats", params=params)

    
    def list_collectors(self) -> List[Dict[str, Any]]:
        """
        List all available collectors.
        
        Returns:
            List of collector information
        """
        return self._request("GET", "/collectors")
    
    def collect_data(self, collector_name: str) -> Dict[str, Any]:
        """
        Collect data using a specific collector.
        
        Args:
            collector_name: Name of the collector to use
            
        Returns:
            Job status information
        """
        return self._request("POST", f"/collectors/{collector_name}/collect")
    
    def debug_collectors(self) -> Dict[str, Any]:
        """
        Get debug information about collectors.
        
        Returns:
            Debug information
        """
        return self._request("GET", "/debug/collectors")
    
    def list_processors(self) -> List[Dict[str, Any]]:
        """
        List all available processors.
        
        Returns:
            List of processor information
        """
        return self._request("GET", "/processors")
    
    def get_processors_status(self) -> Dict[str, Any]:
        """
        Get detailed status of all processors.
        
        Returns:
            Processor status information
        """
        return self._request("GET", "/processors/status")
    
    def process_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process data through the entire pipeline.
        
        Args:
            data: Data to process
            
        Returns:
            Processed data
        """
        return self._request("POST", "/data/process", {"items": data})
    
    def normalize_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize a batch of data items.
        
        Args:
            data: Data to normalize
            
        Returns:
            Normalized data
        """
        return self._request("POST", "/processors/normalize", {"items": data})
    
    def extract_features(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract features from data.
        
        Args:
            data: Data for feature extraction
            
        Returns:
            Data with extracted features
        """
        return self._request("POST", "/processors/extract_features", {"items": data})
    
    def store_processed_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Store processed data in the storage backend.
        
        Args:
            data: Processed data to store
            
        Returns:
            Storage status
        """
        return self._request("POST", "/data/store", {"items": data})
    
    def load_processed_data(self, latest: bool = False) -> List[Dict[str, Any]]:
        """
        Load processed data from storage.
        
        Args:
            latest: Whether to load only the latest batch
            
        Returns:
            Processed data
        """
        params = {"latest": latest}
        return self._request("GET", "/data/load", params=params)
    
    def check_database_status(self) -> Dict[str, Any]:
        """
        Check database connectivity and status.
        
        Returns:
            Database status information
        """
        return self._request("GET", "/database/status")
    
    def check_database_health(self) -> Dict[str, Any]:
        """
        Comprehensive database health check with auto-recovery.
        
        Returns:
            Database health status and metrics
        """
        return self._request("GET", "/database/health")
    
    def analyze_with_agents(self, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze anomalies using the agent-based system.
        
        Args:
            anomalies: Anomalies to analyze (must include 'id' field)
            
        Returns:
            Job status information
        """
        # Ensure all anomalies have the required fields
        for anomaly in anomalies:
            if "detection_time" not in anomaly and "timestamp" in anomaly:
                anomaly["detection_time"] = anomaly["timestamp"]
                
            # Ensure data field exists
            if "data" not in anomaly:
                anomaly["data"] = {}
                
            # Convert features if needed
            if "features" in anomaly and not isinstance(anomaly["features"], list):
                if isinstance(anomaly["features"], dict):
                    anomaly["features"] = list(anomaly["features"].keys())
                else:
                    anomaly["features"] = []
        
        return self._request("POST", "/agents/analyze", anomalies)
    
    def analyze_with_agents_verbose(self, anomalies: List[Dict[str, Any]], 
                                  wait: bool = True,
                                  poll_interval: int = 1,
                                  output_format: str = "detailed") -> Dict[str, Any]:
        """
        Analyze anomalies with verbose agent output.
        
        Args:
            anomalies: Anomalies to analyze
            wait: Whether to wait for completion
            poll_interval: Polling interval in seconds
            output_format: Output format
            
        Returns:
            Analysis results
        """
        response = self._request("POST", "/agents/verbose-analyze", anomalies)
        
        if wait:
            job_id = response["job_id"]
            print(f"Started verbose agent analysis job {job_id}")

            # Poll for completion with timeout
            max_wait = 1800  # 30 minutes
            elapsed = 0
            while elapsed < max_wait:
                job_status = self.get_job_status(job_id)

                if job_status["status"] == "running":
                    progress = job_status.get("progress", 0) * 100
                    print(f"\rAnalyzing... {progress:.1f}%", end="")

                if job_status["status"] in ["completed", "failed"]:
                    print("\n")

                    if job_status["status"] == "completed":
                        result = job_status.get("result", {})

                        # Format output based on format type
                        if output_format == "detailed":
                            print(f"Analysis complete!")
                            print(f"Anomalies analyzed: {result.get('anomalies_analyzed', 0)}")
                            print(f"Agent activities: {result.get('agent_activities_count', 0)}")

                            severity_counts = result.get("severity_counts", {})
                            if severity_counts:
                                print("\nSeverity breakdown:")
                                for severity, count in severity_counts.items():
                                    print(f"- {severity}: {count}")

                            print(f"\nFalse positives: {result.get('false_positives', 0)}")

                        return job_status
                    else:
                        print(f"Analysis failed: {job_status.get('result', {}).get('error')}")
                        return job_status

                time.sleep(poll_interval)
                elapsed += poll_interval

            print(f"\nTimeout: verbose analysis job {job_id} did not complete within {max_wait}s")
            return {"job_id": job_id, "status": "timeout"}

        return response
    
    def get_agent_workflow(self) -> Dict[str, Any]:
        """
        Get the agent workflow configuration.
        
        Returns:
            Agent workflow configuration
        """
        return self._request("GET", "/agents/workflow")
    
    def get_agent_details(self, agent_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent details
        """
        return self._request("GET", f"/agents/{agent_name}")
    
    def get_agent_activities(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get agent activities for a specific job.
        
        Args:
            job_id: Job ID
            
        Returns:
            List of agent activities
        """
        return self._request("GET", f"/agents/activities/{job_id}")
    
    def get_agent_analysis_steps(self, job_id: str) -> Dict[str, Any]:
        """
        Get detailed steps of agent analysis.
        
        Args:
            job_id: Job ID
            
        Returns:
            Analysis steps and statistics
        """
        return self._request("GET", f"/agents/steps/{job_id}")
    
    def test_agents_endpoint(self) -> Dict[str, Any]:
        """
        Test endpoint to verify agents routing is working.
        
        Returns:
            Test status
        """
        return self._request("GET", "/agents/test")
    
    def display_agent_workflow(self, show_details: bool = False) -> None:
        """
        Display the agent workflow in a visual format.
        
        Args:
            show_details: Whether to show detailed information
        """
        workflow = self.get_agent_workflow()
        
        print("\n=== Agent Workflow ===\n")
        
        nodes = workflow.get("nodes", [])
        edges = workflow.get("edges", [])
        
        print("Agents:")
        for node in nodes:
            print(f"  • {node}")
            if show_details:
                try:
                    details = self.get_agent_details(node)
                    print(f"    Description: {details.get('description', 'N/A')}")
                except:
                    pass
        
        print("\nWorkflow:")
        for edge in edges:
            edge_type = edge.get("type", "")
            arrow = "⟲" if edge_type == "feedback" else "→"
            print(f"  {edge['from']} {arrow} {edge['to']}")
            if edge_type:
                print(f"    ({edge_type})")
        
        if workflow.get("description"):
            print(f"\nDescription: {workflow['description']}")
    
    def delete_model(self, model_name: str) -> Dict[str, Any]:
        """
        Delete a model.
        
        Args:
            model_name: Name of the model to delete
            
        Returns:
            Deletion status
        """
        return self._request("DELETE", f"/models/{model_name}")
    
    def load_models_from_storage(self) -> Dict[str, Any]:
        """
        Load all saved models from storage.
        
        Returns:
            Status of loaded models
        """
        return self._request("POST", "/models/load-from-storage")
    
    def list_saved_model_files(self) -> Dict[str, Any]:
        """
        List all saved model files.
        
        Returns:
            List of saved model files
        """
        return self._request("GET", "/models/saved-files")
    
    def system_status(self) -> Dict[str, Any]:
        """
        Get the current status of system components.
        
        Returns:
            System status information
        """
        return self._request("GET", "/system/status")
    
    def test_alert(self, alert_type: str = "email", recipient: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a test alert.
        
        Args:
            alert_type: Type of alert to test
            recipient: Optional recipient
            
        Returns:
            Alert test status
        """
        params = {"alert_type": alert_type}
        if recipient:
            params["recipient"] = recipient
        return self._request("POST", "/alerts/test", params=params)
    
    def update_alert_config(self, enabled: bool, threshold: float, channels: List[str],
                           email: Optional[Dict[str, Any]] = None, webhook: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Update alert configuration.
        
        Args:
            enabled: Whether alerts are enabled
            threshold: Alert threshold
            channels: Alert channels
            email: Email configuration
            webhook: Webhook configuration
            
        Returns:
            Updated configuration
        """
        config = {
            "enabled": enabled,
            "threshold_score": threshold,
            "channels": channels
        }
        if email:
            config["email"] = email
        if webhook:
            config["webhook"] = webhook
        return self._request("POST", "/alerts/config", config)
    
    def cleanup_system(self) -> Dict[str, Any]:
        """
        Clean up temporary files and completed jobs.
        
        Returns:
            Cleanup status
        """
        return self._request("POST", "/system/cleanup")
    
    def shutdown_system(self) -> Dict[str, Any]:
        """
        Gracefully shut down the system.
        
        Returns:
            Shutdown status
        """
        return self._request("POST", "/system/shutdown")
    
    def get_agents_status(self) -> Dict[str, Any]:
        """
        Get the status of the agent system.
        
        Returns:
            Agent system status
        """
        return self._request("GET", "/agents/status")
    
    def analyze_with_agents_detailed(self, anomalies: List[Dict[str, Any]], 
                               include_dialogue: bool = True,
                               include_evidence: bool = True,
                               wait: bool = True) -> Dict[str, Any]:
        """
        Analyze anomalies using the enhanced agent system with detailed results.
        
        Args:
            anomalies: Anomalies to analyze
            include_dialogue: Include agent dialogue in results
            include_evidence: Include evidence chain in results
            wait: Whether to wait for completion
            
        Returns:
            Detailed analysis results
        """
        params = {
            "include_dialogue": include_dialogue,
            "include_evidence": include_evidence
        }
        
        response = self._request("POST", "/agents/analyze-detailed", anomalies, params)
        
        if wait:
            job_id = response["job_id"]
            print(f"Started detailed agent analysis job {job_id}")

            # Poll for completion with progress and timeout
            max_wait = 1800  # 30 minutes
            elapsed = 0
            poll_interval_secs = 1
            while elapsed < max_wait:
                job_status = self.get_job_status(job_id)

                if job_status["status"] == "running":
                    progress = job_status.get("progress", 0) * 100
                    print(f"\rAnalyzing... {progress:.1f}%", end="")

                if job_status["status"] in ["completed", "failed"]:
                    print("\n")

                    if job_status["status"] == "completed":
                        result = job_status.get("result", {})
                        print(f"Analysis complete!")
                        print(f"- Anomalies analyzed: {result.get('anomalies_analyzed', 0)}")
                        print(f"- Total agent dialogues: {result.get('total_agent_dialogues', 0)}")

                        # Show confidence scores
                        avg_confidence = result.get("average_confidence_scores", {})
                        if avg_confidence:
                            print("\nAverage Agent Confidence:")
                            for agent, score in avg_confidence.items():
                                print(f"- {agent}: {score*100:.1f}%")

                        return job_status
                    else:
                        print(f"Analysis failed: {job_status.get('result', {}).get('error')}")
                        return job_status

                time.sleep(poll_interval_secs)
                elapsed += poll_interval_secs

            print(f"\nTimeout: detailed analysis job {job_id} did not complete within {max_wait}s")
            return {"job_id": job_id, "status": "timeout"}

        return response

    def get_agent_dialogue(self, job_id: str, anomaly_id: str) -> Dict[str, Any]:
        """
        Get the agent dialogue for a specific anomaly.
        
        Args:
            job_id: Job ID from analysis
            anomaly_id: Anomaly ID
            
        Returns:
            Agent dialogue and related information
        """
        return self._request("GET", f"/agents/dialogue/{job_id}/{anomaly_id}")

    def display_agent_dialogue(self, dialogue: List[Dict[str, Any]], 
                             show_timestamps: bool = False) -> None:
        """
        Display agent dialogue in a readable format.
        
        Args:
            dialogue: List of dialogue entries
            show_timestamps: Whether to show timestamps
        """
        if not dialogue:
            print("No agent dialogue available")
            return
        
        print("\n=== Agent Dialogue ===\n")
        
        for entry in dialogue:
            from_agent = entry.get("from", "unknown")
            to_agent = entry.get("to", "unknown")
            message_type = entry.get("type", "communication")
            message = entry.get("message", "")
            
            # Format based on message type
            if message_type == "question":
                prefix = "❓"
            elif message_type == "challenge":
                prefix = "⚠️"
            elif message_type == "consensus":
                prefix = "✅"
            elif message_type == "urgent_request":
                prefix = "🚨"
            elif message_type == "feedback":
                prefix = "💭"
            else:
                prefix = "💬"
            
            print(f"{prefix} {from_agent.upper()} → {to_agent.upper()}")
            
            if show_timestamps and "timestamp" in entry:
                print(f"   [{entry['timestamp']}]")
            
            # Wrap long messages
            wrapped = textwrap.wrap(message, width=70)
            for line in wrapped:
                print(f"   {line}")
            print()
    
    def get_job_results(self, job_id: str) -> Dict[str, Any]:
        """
        Get detailed results for a job from the database.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job results including all stored data
        """
        return self._request("GET", f"/results/{job_id}")
    
    def export_anomalies(self, format: str = "json", start_date: Optional[str] = None,
                        end_date: Optional[str] = None, model: Optional[str] = None,
                        severity: Optional[str] = None, limit: int = 1000) -> Union[Dict[str, Any], str]:
        """
        Export anomalies from database with filters.
        
        Args:
            format: Export format (json or csv)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            model: Filter by model
            severity: Filter by severity
            limit: Maximum records to export
            
        Returns:
            Exported data in requested format
        """
        params = {"format": format, "limit": limit}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if model:
            params["model"] = model
        if severity:
            params["severity"] = severity
        
        if format == "csv":
            # For CSV, make raw request to get the text response
            url = f"{self.base_url}/export/anomalies"
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.text
        else:
            return self._request("GET", "/export/anomalies", params=params)
    
    def get_stream_status(self) -> Dict[str, Any]:
        """
        Get the status of real-time data streams.
        
        Returns:
            Stream status information
        """
        return self._request("GET", "/stream/status")
    
    def wait_for_job(self, job_id: str, timeout: int = 300, poll_interval: int = 2) -> Dict[str, Any]:
        """
        Wait for a job to complete.
        
        Args:
            job_id: Job ID to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks
            
        Returns:
            Final job status
        """
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
            
            job_status = self.get_job_status(job_id)
            
            if job_status["status"] in ["completed", "failed"]:
                return job_status
            
            # Show progress if available
            progress = job_status.get("progress", 0)
            print(f"\rJob {job_id}: {job_status['status']} ({progress*100:.1f}%)", end="")
            
            time.sleep(poll_interval)
    
    def split_data(self, args):
        """
        Split data into training and validation sets
        
        Args:
            args: Argparse arguments containing input_file, train_output, val_output, test_split
        
        Returns:
            dict: Summary of the split operation
        """
        import random
        from pathlib import Path
        
        try:
            # Read input file
            self.logger.info(f"Reading input file: {args.input_file}")
            with open(args.input_file, 'r') as f:
                data = json.load(f)
            
            # Handle different data formats
            if isinstance(data, dict):
                if 'raw_data' in data:
                    items = data['raw_data']
                    self.logger.info("Using 'raw_data' field")
                elif 'items' in data:
                    items = data['items']
                    self.logger.info("Using 'items' field")
                elif 'features' in data:
                    items = data['features']
                    self.logger.info("Using 'features' field")
                else:
                    items = [data]
                    self.logger.info("Single dict record")
            elif isinstance(data, list):
                items = data
                self.logger.info("Data is a list")
            else:
                items = [data]
                self.logger.info("Single item")
            
            total_count = len(items)
            self.logger.info(f"Total records: {total_count}")
            
            if total_count == 0:
                raise ValueError("No data found in input file")
            
            # Calculate split
            val_count = max(1, int(total_count * args.test_split))
            train_count = total_count - val_count
            
            self.logger.info(f"Splitting: {train_count} train, {val_count} validation")
            
            # Perform random split with seed
            random.seed(getattr(args, 'random_seed', 42))
            shuffled = items.copy()
            random.shuffle(shuffled)
            
            train_data = shuffled[:train_count]
            val_data = shuffled[train_count:]
            
            # Create output directories
            Path(args.train_output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.val_output).parent.mkdir(parents=True, exist_ok=True)
            
            # Save training data
            self.logger.info(f"Saving training data: {args.train_output}")
            with open(args.train_output, 'w') as f:
                json.dump(train_data, f, indent=2)
            
            # Save validation data
            self.logger.info(f"Saving validation data: {args.val_output}")
            with open(args.val_output, 'w') as f:
                json.dump(val_data, f, indent=2)
            
            result = {
                "status": "success",
                "total_records": total_count,
                "train_records": len(train_data),
                "validation_records": len(val_data),
                "split_ratio": args.test_split,
                "train_output": args.train_output,
                "val_output": args.val_output
            }
            
            self.logger.info("✓ Data split completed successfully")
            print(json.dumps(result, indent=2))
            return result
            
        except FileNotFoundError:
            self.logger.error(f"Input file not found: {args.input_file}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in input file: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error splitting data: {e}")
            raise
    
    def generate_data(self, args):
        """
        Generate synthetic test data for anomaly detection
        
        FIXED VERSION: Outputs plain array format for pipeline compatibility
        
        Args:
            args: Argparse arguments containing count, anomaly_ratio, output
        
        Returns:
            dict: Summary of data generation
        """
        import random
        from pathlib import Path
        
        try:
            count = args.count
            anomaly_ratio = getattr(args, 'anomaly_ratio', 0.3)
            output_file = args.output
            
            self.logger.info(f"Generating {count} records ({anomaly_ratio*100}% anomalies)")
            
            # Calculate normal vs anomaly counts
            anomaly_count = int(count * anomaly_ratio)
            normal_count = count - anomaly_count
            
            # Normal data templates
            normal_templates = [
                {
                    "computerName": "SERVER-PROD-{:02d}",
                    "domain": "corp.company.com",
                    "osName": "Windows Server 2019",
                    "siteName": "HQ",
                    "activeThreats": 0,
                    "totalMemory": 32768,
                    "cpuCount": 8,
                    "isActive": True
                },
                {
                    "computerName": "SERVER-PROD-{:02d}",
                    "domain": "corp.company.com",
                    "osName": "Ubuntu 22.04",
                    "siteName": "HQ",
                    "activeThreats": 0,
                    "totalMemory": 65536,
                    "cpuCount": 16,
                    "isActive": True
                },
                {
                    "computerName": "DESKTOP-USER-{:02d}",
                    "domain": "corp.company.com",
                    "osName": "Windows 10 Pro",
                    "siteName": "Remote",
                    "activeThreats": 0,
                    "totalMemory": 16384,
                    "cpuCount": 4,
                    "isActive": True
                }
            ]
            
            # Anomaly templates
            anomaly_templates = [
                {
                    "computerName": "SUSPICIOUS-HOST-{:02d}",
                    "domain": "malware.external.com",
                    "osName": "Unknown OS",
                    "siteName": "Unknown",
                    "activeThreats": random.randint(10, 25),
                    "totalMemory": 2048,
                    "cpuCount": 1,
                    "isActive": False
                },
                {
                    "computerName": "BACKDOOR-{:02d}",
                    "domain": "hacker-c2.darkweb.onion",
                    "osName": "Kali Linux",
                    "siteName": "External",
                    "activeThreats": random.randint(15, 30),
                    "totalMemory": 4096,
                    "cpuCount": 2,
                    "isActive": False
                },
                {
                    "computerName": "COMPROMISED-{:02d}",
                    "domain": "suspicious.domain.xyz",
                    "osName": "Custom Linux",
                    "siteName": "Unknown",
                    "activeThreats": random.randint(5, 15),
                    "totalMemory": 8192,
                    "cpuCount": 4,
                    "isActive": False
                }
            ]
            
            records = []
            base_time = datetime.now()
            
            # Generate normal records
            for i in range(normal_count):
                template = random.choice(normal_templates).copy()
                # Format computerName with index
                if "{:02d}" in template["computerName"]:
                    template["computerName"] = template["computerName"].format(i + 1)
                
                # Add timestamp
                timestamp = base_time + timedelta(minutes=i)
                template["timestamp"] = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                
                records.append(template)
            
            # Generate anomaly records
            for i in range(anomaly_count):
                template = random.choice(anomaly_templates).copy()
                # Format computerName with index
                if "{:02d}" in template["computerName"]:
                    template["computerName"] = template["computerName"].format(i + 1)
                
                # Add timestamp
                timestamp = base_time + timedelta(minutes=normal_count + i)
                template["timestamp"] = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                
                # Randomize threat count
                template["activeThreats"] = random.randint(
                    template["activeThreats"] - 5,
                    template["activeThreats"] + 5
                )
                
                records.append(template)
            
            # Shuffle records
            random.shuffle(records)
            
            # ============================================================
            # FIX: Output plain array instead of wrapped structure
            # ============================================================
            
            # Save data as plain array (what the pipeline expects)
            output_data = records
            
            # Create metadata separately
            metadata = {
                "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "total_records": count,
                "normal_records": normal_count,
                "anomaly_records": anomaly_count,
                "anomaly_ratio": anomaly_ratio,
                "output_format": "plain_array",
                "compatible_with": "pipeline process-data command"
            }
            
            # Create output directory
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            
            # Save data file (plain array)
            self.logger.info(f"Saving generated data to: {output_file}")
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            # Save metadata to separate file
            metadata_file = output_file.replace('.json', '_metadata.json')
            self.logger.info(f"Saving metadata to: {metadata_file}")
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            result = {
                "status": "success",
                "output_file": output_file,
                "metadata_file": metadata_file,
                "total_records": count,
                "normal_records": normal_count,
                "anomaly_records": anomaly_count,
                "anomaly_ratio": anomaly_ratio,
                "format": "plain_array"
            }
            
            self.logger.info("✓ Data generation completed successfully")
            self.logger.info(f"✓ Data format: plain array (pipeline compatible)")
            self.logger.info(f"✓ Metadata saved separately to {metadata_file}")
            print(json.dumps(result, indent=2))
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating data: {e}")
            raise

class WebSocketConnection:
    """WebSocket connection handler for real-time updates."""
    
    def __init__(self, ws_url: str, on_message: Optional[Callable] = None,
                 on_error: Optional[Callable] = None, on_close: Optional[Callable] = None):
        """
        Initialize WebSocket connection handler.
        
        Args:
            ws_url: WebSocket URL
            on_message: Callback for received messages
            on_error: Callback for errors
            on_close: Callback for connection close
        """
        self.ws_url = ws_url + "/ws"
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.websocket = None
        self.client_id = None
        self.logger = logging.getLogger("websocket_client")
    
    async def connect(self):
        """Connect to the WebSocket server."""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            
            # Receive initial connection message
            message = await self.websocket.recv()
            data = json.loads(message)
            
            if data.get("type") == "connection":
                self.client_id = data.get("client_id")
                self.logger.info(f"Connected to WebSocket with client ID: {self.client_id}")
                
                if self.on_message:
                    self.on_message(data)
            
            # Start listening for messages
            await self._listen()
            
        except Exception as e:
            self.logger.error(f"WebSocket connection error: {str(e)}")
            if self.on_error:
                self.on_error(e)
    
    async def _listen(self):
        """Listen for incoming WebSocket messages."""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                if self.on_message:
                    self.on_message(data)
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("WebSocket connection closed")
            if self.on_close:
                self.on_close()
        except Exception as e:
            self.logger.error(f"WebSocket error: {str(e)}")
            if self.on_error:
                self.on_error(e)
    
    async def send(self, message: Dict[str, Any]):
        """
        Send a message through the WebSocket.
        
        Args:
            message: Message to send
        """
        if self.websocket:
            await self.websocket.send(json.dumps(message))
    
    async def subscribe(self, topics: List[str]):
        """
        Subscribe to specific topics for updates.
        
        Args:
            topics: List of topics to subscribe to
        """
        await self.send({
            "type": "subscribe",
            "topics": topics
        })
    
    async def ping(self):
        """Send a ping message to keep the connection alive."""
        await self.send({"type": "ping"})
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()


def load_json_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Load data from a JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        List of data items from the file
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Convert to list if it's a single object
        if isinstance(data, dict):
            return [data]
        
        return data
    except FileNotFoundError:
        raise Exception(f"File not found: {file_path}")
    except json.JSONDecodeError:
        raise Exception(f"Invalid JSON format in file: {file_path}")


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(description="Anomaly Detection API Client")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API service")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    subparsers.required = True  # Make command argument required
    
    # Health check
    subparsers.add_parser("health", help="Check the health of the API service")
    
    # Initialize system
    init_parser = subparsers.add_parser("init", help="Initialize the system with a configuration file")
    init_parser.add_argument("config_path", help="Path to configuration file")
    init_parser.add_argument("--auto-init", action="store_true", help="Automatically initialize system")
    
    # Get config
    subparsers.add_parser("config", help="Get the current system configuration")
    
    # List models
    subparsers.add_parser("list-models", help="List all available models")
    
    # Train model
    train_parser = subparsers.add_parser("train-model", help="Train a model with data")
    train_parser.add_argument("model_name", help="Name of the model to train")
    train_parser.add_argument("data_file", help="Path to JSON file with training data")
    train_parser.add_argument("--wait", action="store_true", help="Wait for the job to complete")
    
    # Detect anomalies
    detect_parser = subparsers.add_parser("detect-anomalies", help="Detect anomalies in data")
    detect_parser.add_argument("model_name", help="Name of the model to use")
    detect_parser.add_argument("data_file", help="Path to JSON file with data for detection")
    detect_parser.add_argument("--threshold", type=float, help="Optional detection threshold")
    detect_parser.add_argument("--wait", action="store_true", help="Wait for the job to complete")
    
    # Detect anomalies (simplified)
    detect_simple_parser = subparsers.add_parser("detect-simple", help="Detect anomalies using simplified endpoint")
    detect_simple_parser.add_argument("model_name", help="Name of the model to use")
    detect_simple_parser.add_argument("data_file", help="Path to JSON file with data for detection")
    detect_simple_parser.add_argument("--threshold", type=float, help="Optional detection threshold")
    detect_simple_parser.add_argument("--wait", action="store_true", help="Wait for the job to complete")
    
    # Bulk detect anomalies
    bulk_detect_parser = subparsers.add_parser("bulk-detect", help="Detect anomalies using multiple models")
    bulk_detect_parser.add_argument("models", nargs="+", help="List of model names to use")
    bulk_detect_parser.add_argument("data_file", help="Path to JSON file with data for detection")
    bulk_detect_parser.add_argument("--wait", action="store_true", help="Wait for the job to complete")
    
    # Get job status
    job_parser = subparsers.add_parser("job-status", help="Get the status of a background job")
    job_parser.add_argument("job_id", help="ID of the job to check")
    
    # List jobs
    jobs_parser = subparsers.add_parser("list-jobs", help="List background jobs")
    jobs_parser.add_argument("--status", help="Filter jobs by status")
    jobs_parser.add_argument("--job-type", help="Filter jobs by type")
    jobs_parser.add_argument("--limit", type=int, default=10, help="Maximum number of jobs to return")
    
    # Collect data
    collect_parser = subparsers.add_parser("collect-data", help="Collect data using a collector")
    collect_parser.add_argument("collector_name", help="Name of the collector to use")
    collect_parser.add_argument("--wait", action="store_true", help="Wait for the job to complete")
    
    # List collectors
    subparsers.add_parser("list-collectors", help="List all available collectors")
    
    # Debug collectors
    subparsers.add_parser("debug-collectors", help="Debug information about collectors")
    
    # List processors
    subparsers.add_parser("list-processors", help="List all available processors")
    
    # Processor status
    subparsers.add_parser("processor-status", help="Get detailed status of all processors")
    
    # Normalize data
    normalize_parser = subparsers.add_parser("normalize-data", help="Normalize a batch of data items")
    normalize_parser.add_argument("data_file", help="Path to JSON file with data to normalize")
    
    # Extract features
    features_parser = subparsers.add_parser("extract-features", help="Extract features from data")
    features_parser.add_argument("data_file", help="Path to JSON file with data for feature extraction")
    
    # List anomalies
    anomalies_parser = subparsers.add_parser("list-anomalies", help="List detected anomalies")
    anomalies_parser.add_argument("--model", help="Filter anomalies by model name")
    anomalies_parser.add_argument("--status", help="Filter anomalies by status")
    anomalies_parser.add_argument("--severity", help="Filter anomalies by severity (Critical, High, Medium, Low)")
    anomalies_parser.add_argument("--min-score", type=float, default=0.0, help="Minimum anomaly score")
    anomalies_parser.add_argument("--limit", type=int, default=100, help="Maximum number of anomalies to return")
    
    # Store anomalies
    store_anomalies_parser = subparsers.add_parser("store-anomalies", help="Store anomalies explicitly")
    store_anomalies_parser.add_argument("anomalies_file", help="Path to JSON file with anomalies to store")
    
    # Correlate anomalies
    correlate_parser = subparsers.add_parser("correlate-anomaly", help="Analyze correlations for an anomaly")
    correlate_parser.add_argument("anomaly_id", help="ID of the anomaly to analyze")
    correlate_parser.add_argument("--time-window", type=int, default=24, help="Time window in hours")
    correlate_parser.add_argument("--min-score", type=float, default=0.3, help="Minimum correlation score")
    correlate_parser.add_argument("--max-results", type=int, default=50, help="Maximum results")
    correlate_parser.add_argument("--wait", action="store_true", help="Wait for the job to complete")
    
    # Get anomaly correlations (sync)
    get_correlations_parser = subparsers.add_parser("get-correlations", help="Get correlations for an anomaly (sync)")
    get_correlations_parser.add_argument("anomaly_id", help="ID of the anomaly")
    get_correlations_parser.add_argument("--time-window", type=int, default=24, help="Time window in hours")
    get_correlations_parser.add_argument("--min-score", type=float, default=0.3, help="Minimum correlation score")
    get_correlations_parser.add_argument("--max-results", type=int, default=50, help="Maximum results")
    
    # Bulk correlate anomalies
    bulk_correlate_parser = subparsers.add_parser("bulk-correlate", help="Analyze correlations for multiple anomalies")
    bulk_correlate_parser.add_argument("anomaly_ids", nargs="+", help="List of anomaly IDs")
    bulk_correlate_parser.add_argument("--cross-correlate", action="store_true", help="Cross-correlate between provided anomalies")
    bulk_correlate_parser.add_argument("--time-window", type=int, default=24, help="Time window in hours")
    bulk_correlate_parser.add_argument("--min-score", type=float, default=0.3, help="Minimum correlation score")
    
    # Correlation matrix
    matrix_parser = subparsers.add_parser("correlation-matrix", help="Generate correlation matrix")
    matrix_parser.add_argument("anomaly_ids", nargs="+", help="List of anomaly IDs (2-50)")
    matrix_parser.add_argument("--no-metadata", action="store_true", help="Exclude metadata from response")
    
    # Correlation statistics
    correlation_stats_parser = subparsers.add_parser("correlation-stats", help="Get correlation statistics")
    correlation_stats_parser.add_argument("--time-window", type=int, default=24, help="Time window in hours")
    correlation_stats_parser.add_argument("--min-score", type=float, default=0.3, help="Minimum correlation score")
    
    # Database status
    subparsers.add_parser("database-status", help="Check database connectivity and status")
    
    # Database health
    subparsers.add_parser("database-health", help="Comprehensive database health check")
    
    # Analyze with agents
    agent_parser = subparsers.add_parser("analyze-with-agents", help="Analyze anomalies with agents")
    agent_parser.add_argument("anomalies_file", help="Path to JSON file with anomalies to analyze")
    agent_parser.add_argument("--wait", action="store_true", help="Wait for the job to complete")
    
    # Get agent workflow
    subparsers.add_parser("agent-workflow", help="Get the agent workflow configuration")
    
    # Test agents endpoint
    subparsers.add_parser("test-agents", help="Test agents endpoint")
    
    # Get agents status
    subparsers.add_parser("agents-status", help="Get the status of the agent system")
    
    # Process data
    process_parser = subparsers.add_parser("process-data", help="Process data through the entire pipeline")
    process_parser.add_argument("data_file", help="Path to JSON file with data to process")
    
    # Store processed data
    store_parser = subparsers.add_parser("store-data", help="Store processed data in the storage backend")
    store_parser.add_argument("data_file", help="Path to JSON file with processed data to store")
    
    # Load processed data
    load_parser = subparsers.add_parser("load-data", help="Load processed data from storage")
    load_parser.add_argument("--latest", action="store_true", help="Load only the latest batch")
    
    # Test alert
    alert_parser = subparsers.add_parser("test-alert", help="Send a test alert")
    alert_parser.add_argument("--type", dest="alert_type", default="email", choices=["email", "webhook"], help="Type of alert to test")
    alert_parser.add_argument("--recipient", help="Recipient for the test alert")
    
    # Update alert config
    alert_config_parser = subparsers.add_parser("update-alert-config", help="Update alert configuration")
    alert_config_parser.add_argument("--enabled", type=bool, default=True, help="Enable/disable alerts")
    alert_config_parser.add_argument("--threshold", type=float, default=0.8, help="Minimum score to trigger alerts")
    alert_config_parser.add_argument("--channels", nargs="+", default=["console"], help="Alert channels")
    
    # Create model
    create_model_parser = subparsers.add_parser("create-model", help="Create a new model")
    create_model_parser.add_argument("model_type", choices=["isolation_forest", "one_class_svm", "autoencoder", "gan", "ensemble", "statistical"], 
                                    help="Type of model to create")
    create_model_parser.add_argument("config_file", help="Path to JSON file with model configuration")
    
    # Load models from storage
    subparsers.add_parser("load-models", help="Load all saved models from storage")
    
    # List saved model files
    subparsers.add_parser("list-model-files", help="List all saved model files")
    
    # Delete model
    delete_parser = subparsers.add_parser("delete-model", help="Delete a model")
    delete_parser.add_argument("model_name", help="Name of the model to delete")
    
    # System status
    subparsers.add_parser("system-status", help="Get the current status of the system components")
    
    # Shutdown system
    subparsers.add_parser("shutdown-system", help="Gracefully shut down the system")
    
    # Cleanup system
    subparsers.add_parser("cleanup-system", help="Clean up temporary files and completed jobs")
    
    detailed_parser = subparsers.add_parser(
        "analyze-detailed", 
        help="Analyze anomalies with enhanced agents and detailed results"
    )
    detailed_parser.add_argument(
        "anomalies_file", 
        help="Path to JSON file with anomalies"
    )
    detailed_parser.add_argument(
        "--no-dialogue", 
        action="store_true", 
        help="Exclude agent dialogue from results"
    )
    detailed_parser.add_argument(
        "--no-evidence", 
        action="store_true", 
        help="Exclude evidence chain from results"
    )
    detailed_parser.add_argument(
        "--show-dialogue", 
        action="store_true", 
        help="Display agent dialogue after analysis"
    )

    # Agent verbose analysis command
    agent_analyze_verbose_parser = subparsers.add_parser(
        "analyze-with-agents-verbose", 
        help="Analyze anomalies with agents with verbose output"
    )
    agent_analyze_verbose_parser.add_argument(
        "anomalies_file", 
        help="Path to JSON file with anomalies to analyze"
    )
    agent_analyze_verbose_parser.add_argument(
        "--no-wait", 
        action="store_true", 
        help="Don't wait for the job to complete"
    )
    agent_analyze_verbose_parser.add_argument(
        "--poll-interval", 
        type=int, 
        default=1, 
        help="Time between status checks in seconds"
    )
    agent_analyze_verbose_parser.add_argument(
        "--output-format", 
        choices=["detailed", "compact", "minimal"],
        default="detailed",
        help="Output format for agent activities"
    )

    # Get agent details command
    agent_details_parser = subparsers.add_parser(
        "agent-details", 
        help="Get detailed information about a specific agent"
    )
    agent_details_parser.add_argument(
        "agent_name", 
        help="Name of the agent"
    )

    # Get agent activities command
    agent_activities_parser = subparsers.add_parser(
        "agent-activities", 
        help="Get activities of agents for a specific job"
    )
    agent_activities_parser.add_argument(
        "job_id", 
        help="ID of the agent analysis job"
    )

    # Display agent workflow command
    agent_workflow_display_parser = subparsers.add_parser(
        "display-agent-workflow", 
        help="Display the agent workflow in a visual format"
    )
    agent_workflow_display_parser.add_argument(
        "--details", 
        action="store_true",
        help="Show detailed agent information"
    )

    # Get agent analysis steps command
    agent_steps_parser = subparsers.add_parser(
        "agent-steps", 
        help="Get detailed steps of the agent analysis process"
    )
    agent_steps_parser.add_argument(
        "job_id", 
        help="ID of the agent analysis job"
    )
    agent_steps_parser.add_argument(
        "--details", 
        action="store_true",
        help="Show detailed step information"
    )
    
    # Get job results
    job_results_parser = subparsers.add_parser("job-results", help="Get detailed job results from database")
    job_results_parser.add_argument("job_id", help="Job ID to retrieve results for")
    
    # Export anomalies
    export_parser = subparsers.add_parser("export-anomalies", help="Export anomalies with filters")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")
    export_parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    export_parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    export_parser.add_argument("--model", help="Filter by model")
    export_parser.add_argument("--severity", help="Filter by severity")
    export_parser.add_argument("--limit", type=int, default=1000, help="Maximum records to export")
    export_parser.add_argument("--output", help="Output file (for CSV format)")
    
    # Stream status
    subparsers.add_parser("stream-status", help="Get real-time stream status")
    
    # Split data command
    parser_split = subparsers.add_parser(
        'split-data',
        help='Split data into training and validation sets'
    )
    parser_split.add_argument(
        'input_file',
        help='Path to input data file'
    )
    parser_split.add_argument(
        '--train-output',
        required=True,
        help='Path for training data output'
    )
    parser_split.add_argument(
        '--val-output',
        required=True,
        help='Path for validation data output'
    )
    parser_split.add_argument(
        '--test-split',
        type=float,
        default=0.2,
        help='Fraction of data for validation (default: 0.2)'
    )
    parser_split.add_argument(
        '--random-seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )
    
    # Generate data command
    parser_generate = subparsers.add_parser(
        'generate-data',
        help='Generate synthetic test data for anomaly detection'
    )
    parser_generate.add_argument(
        '--output',
        required=True,
        help='Path for generated data output'
    )
    parser_generate.add_argument(
        '--count',
        type=int,
        default=100,
        help='Number of records to generate (default: 100)'
    )
    parser_generate.add_argument(
        '--anomaly-ratio',
        type=float,
        default=0.3,
        help='Fraction of records that are anomalies (default: 0.3)'
    )
    parser_generate.add_argument(
        '--random-seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("anomaly_client")
    
    # Create client
    client = AnomalyDetectionClient(args.url)
    
    try:
        # Execute command
        if args.command == "health":
            result = client.health_check()
        
        elif args.command == "init":
            result = client.initialize_system(args.config_path, args.auto_init)
        
        elif args.command == "config":
            result = client.get_config()
        
        elif args.command == "list-models":
            result = client.list_models()
        
        elif args.command == "train-model":
            data = load_json_data(args.data_file)
            result = client.train_model(args.model_name, data)
            
            if args.wait:
                logger.info(f"Waiting for training job {result['job_id']} to complete...")
                result = client.wait_for_job(result["job_id"])
        
        elif args.command == "detect-anomalies":
            data = load_json_data(args.data_file)
            result = client.detect_anomalies(args.model_name, data, args.threshold)
            
            if args.wait:
                logger.info(f"Waiting for detection job {result['job_id']} to complete...")
                result = client.wait_for_job(result["job_id"])
        
        elif args.command == "detect-simple":
            data = load_json_data(args.data_file)
            result = client.detect_anomalies_simple(args.model_name, data, args.threshold)
            
            if args.wait:
                logger.info(f"Waiting for detection job {result['job_id']} to complete...")
                result = client.wait_for_job(result["job_id"])
        
        elif args.command == "bulk-detect":
            data = load_json_data(args.data_file)
            result = client.bulk_detect_anomalies(args.models, data)
            
            if args.wait:
                logger.info(f"Waiting for bulk detection job {result['job_id']} to complete...")
                result = client.wait_for_job(result["job_id"])
        
        elif args.command == "job-status":
            result = client.get_job_status(args.job_id)
        
        elif args.command == "list-jobs":
            result = client.list_jobs(args.status, args.job_type, args.limit)
        
        elif args.command == "collect-data":
            result = client.collect_data(args.collector_name)
            
            if args.wait:
                logger.info(f"Waiting for collection job {result['job_id']} to complete...")
                result = client.wait_for_job(result["job_id"])
        
        elif args.command == "list-collectors":
            result = client.list_collectors()
        
        elif args.command == "debug-collectors":
            result = client.debug_collectors()
        
        elif args.command == "list-processors":
            result = client.list_processors()
        
        elif args.command == "processor-status":
            result = client.get_processors_status()
        
        elif args.command == "normalize-data":
            data = load_json_data(args.data_file)
            result = client.normalize_data(data)
        
        elif args.command == "extract-features":
            data = load_json_data(args.data_file)
            result = client.extract_features(data)
        
        elif args.command == "list-anomalies":
            result = client.list_anomalies(args.model, args.min_score, args.status, args.severity, args.limit)
        
        elif args.command == "store-anomalies":
            anomalies = load_json_data(args.anomalies_file)
            result = client.store_anomalies(anomalies)
        
        elif args.command == "correlate-anomaly":
            result = client.correlate_anomalies(args.anomaly_id, args.time_window, 
                                              args.min_score, args.max_results)
            if args.wait:
                logger.info(f"Waiting for correlation job {result['job_id']} to complete...")
                result = client.wait_for_job(result["job_id"])
        
        elif args.command == "get-correlations":
            try:
                result = client.get_anomaly_correlations(args.anomaly_id, args.time_window,
                                                       args.min_score, args.max_results)
            except Exception as e:
                logger.error(f"Error getting correlations: {e}")
                sys.exit(1)
        
        elif args.command == "bulk-correlate":
            try:
                result = client.bulk_correlate_anomalies(args.anomaly_ids, args.cross_correlate,
                                                        args.time_window, args.min_score)
            except Exception as e:
                logger.error(f"Error bulk correlating anomalies: {e}")
                sys.exit(1)
        
        elif args.command == "correlation-matrix":
            try:
                result = client.generate_correlation_matrix(args.anomaly_ids, not args.no_metadata)
            except ValueError as e:
                logger.error(f"Invalid input: {e}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error generating correlation matrix: {e}")
                sys.exit(1)
        
        elif args.command == "correlation-stats":
            try:
                result = client.get_correlation_statistics(args.time_window, args.min_score)
            except Exception as e:
                logger.error(f"Error getting correlation statistics: {e}")
                sys.exit(1)
        
        elif args.command == "database-status":
            result = client.check_database_status()
        
        elif args.command == "database-health":
            result = client.check_database_health()
        
        elif args.command == "analyze-with-agents":
            anomalies = load_json_data(args.anomalies_file)
            result = client.analyze_with_agents(anomalies)
            
            if args.wait:
                logger.info(f"Waiting for agent analysis job {result['job_id']} to complete...")
                result = client.wait_for_job(result["job_id"])
                
        elif args.command == "agent-workflow":
            result = client.get_agent_workflow()
        
        elif args.command == "test-agents":
            result = client.test_agents_endpoint()
        
        elif args.command == "agents-status":
            result = client.get_agents_status()
        
        elif args.command == "process-data":
            data = load_json_data(args.data_file)
            result = client.process_data(data)
        
        elif args.command == "store-data":
            data = load_json_data(args.data_file)
            result = client.store_processed_data(data)
        
        elif args.command == "load-data":
            result = client.load_processed_data(args.latest)
        
        elif args.command == "test-alert":
            result = client.test_alert(args.alert_type, args.recipient)
        
        elif args.command == "update-alert-config":
            result = client.update_alert_config(args.enabled, args.threshold, args.channels)
        
        elif args.command == "create-model":
            with open(args.config_file, 'r') as f:
                config = json.load(f)
            # If config is a list with one item, use that item
            if isinstance(config, list) and len(config) > 0:
                config = config[0]
            result = client.create_model(args.model_type, config)
        
        elif args.command == "load-models":
            result = client.load_models_from_storage()
        
        elif args.command == "list-model-files":
            result = client.list_saved_model_files()
        
        elif args.command == "delete-model":
            result = client.delete_model(args.model_name)
        
        elif args.command == "system-status":
            result = client.system_status()
        
        elif args.command == "shutdown-system":
            result = client.shutdown_system()
        
        elif args.command == "cleanup-system":
            result = client.cleanup_system()
        
        elif args.command == "analyze-with-agents-verbose":
            anomalies = load_json_data(args.anomalies_file)
            result = client.analyze_with_agents_verbose(
                anomalies, 
                wait=not args.no_wait,
                poll_interval=args.poll_interval,
                output_format=args.output_format
            )
            
            # Only print the final JSON if not waiting
            if args.no_wait:
                print(json.dumps(result, indent=2))

        elif args.command == "agent-details":
            result = client.get_agent_details(args.agent_name)
            print(json.dumps(result, indent=2))

        elif args.command == "agent-activities":
            result = client.get_agent_activities(args.job_id)
            print(json.dumps(result, indent=2))

        elif args.command == "display-agent-workflow":
            client.display_agent_workflow(show_details=args.details)

        elif args.command == "agent-steps":
            result = client.get_agent_analysis_steps(args.job_id)
            
            # Print summary statistics
            stats = result.get("statistics", {})
            print("\nAgent Analysis Summary:")
            print(f"Job ID: {result.get('job_id')}")
            print(f"Total activities: {stats.get('total_activities', 0)}")
            
            if stats.get("start_time") and stats.get("end_time"):
                start = stats["start_time"]
                end = stats["end_time"]
                print(f"Time range: {start} to {end}")
            
            # Print agent counts
            agent_counts = stats.get("agent_counts", {})
            if agent_counts:
                print("\nActivity by agent:")
                for agent, count in agent_counts.items():
                    print(f"- {agent}: {count} activities")
            
            # Print action counts
            action_counts = stats.get("action_counts", {})
            if action_counts:
                print("\nActivity by action type:")
                for action, count in action_counts.items():
                    print(f"- {action}: {count} activities")
            
            # Print detailed step information if requested
            if args.details:
                print("\nDetailed steps:")
                print(json.dumps(result.get("steps", {}), indent=2))
        elif args.command == "analyze-detailed":
            anomalies = load_json_data(args.anomalies_file)
            result = client.analyze_with_agents_detailed(
                anomalies,
                include_dialogue=not args.no_dialogue,
                include_evidence=not args.no_evidence,
                wait=True
            )
            
            if args.show_dialogue and result.get("status") == "completed":
                # Show dialogue for each anomaly
                detailed_results = result.get("result", {}).get("detailed_results", [])
                for anomaly_result in detailed_results:
                    print(f"\n{'='*60}")
                    print(f"Anomaly: {anomaly_result.get('id', 'Unknown')}")
                    print(f"{'='*60}")
                    
                    dialogue = anomaly_result.get("agent_dialogue", [])
                    client.display_agent_dialogue(dialogue)
        
        elif args.command == "job-results":
            result = client.get_job_results(args.job_id)
        
        elif args.command == "export-anomalies":
            if args.format == "csv":
                csv_data = client.export_anomalies(args.format, args.start_date, args.end_date,
                                                 args.model, args.severity, args.limit)
                if args.output:
                    with open(args.output, 'w') as f:
                        f.write(csv_data)
                    print(f"Exported anomalies to {args.output}")
                else:
                    print(csv_data)
                return  # Exit early for CSV
            else:
                result = client.export_anomalies(args.format, args.start_date, args.end_date,
                                               args.model, args.severity, args.limit)
        
        elif args.command == "split-data":
            result = client.split_data(args)
        
        elif args.command == "generate-data":
            result = client.generate_data(args)
        
        else:
            logger.error(f"Unknown command: {args.command}")
            parser.print_help()
            sys.exit(1)
        
        # Output result for commands that don't have their own formatting
        if args.command not in ["analyze-with-agents-verbose", "agent-details", "agent-activities", 
                                "display-agent-workflow", "agent-steps", "export-anomalies", "split-data", "generate-data"]:
            print(json.dumps(result, indent=2))
        
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()