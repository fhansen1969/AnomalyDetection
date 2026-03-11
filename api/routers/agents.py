"""Agent analysis routes, VerboseVisualizer, and background jobs."""
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Path, Body

from api.state import app_state
from api.schemas import JobStatus
from api.helpers import get_default_agent_workflow, store_detection_results

logger = logging.getLogger("api_services")
router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: broadcast agent updates to WebSocket clients
# ---------------------------------------------------------------------------

async def broadcast_agent_update(agent_name: str, status: str, details: Dict[str, Any]):
    """
    Broadcast agent status update to all connected WebSocket clients.

    Args:
        agent_name: Name of the agent
        status: Current status of the agent
        details: Additional details about the agent's activity
    """
    agent_name_str = str(agent_name) if agent_name is not None else "unknown"
    status_str = str(status) if status is not None else "unknown"
    details_dict = details if isinstance(details, dict) else {}

    update_data = {
        "type": "agent_update",
        "timestamp": datetime.utcnow().isoformat(),
        "agent_name": agent_name_str,
        "status": status_str,
        "details": details_dict
    }

    # Snapshot connections to avoid RuntimeError if dict changes during iteration
    for client_id, websocket in list(app_state.websocket_connections.items()):
        try:
            await websocket.send_json(update_data)
        except Exception as e:
            logging.error(f"Error sending agent update to WebSocket client {client_id}: {str(e)}")
            logging.error(traceback.format_exc())


# ---------------------------------------------------------------------------
# VerboseVisualizer class
# ---------------------------------------------------------------------------

class VerboseVisualizer:
    """
    Verbose visualizer for agent manager that provides detailed updates.
    """

    def __init__(self, job_id):
        """
        Initialize visualizer with job ID.

        Args:
            job_id: ID of the agent analysis job
        """
        self.job_id = job_id
        self.activities = []
        self.logger = logging.getLogger("verbose_visualizer")

    def log_agent_activity(self, agent_name, action, status, details=None):
        """
        Log agent activity with detailed information.

        Args:
            agent_name: Name of the agent
            action: Action being performed
            status: Current status of the action
            details: Additional details about the activity
        """
        agent_name_str = str(agent_name) if agent_name is not None else "unknown"
        action_str = str(action) if action is not None else "unknown"
        status_str = str(status) if status is not None else "unknown"
        details_dict = details if isinstance(details, dict) else {}

        activity = {
            "timestamp": datetime.utcnow().isoformat(),
            "job_id": self.job_id,
            "agent_name": agent_name_str,
            "action": action_str,
            "status": status_str,
            "details": details_dict
        }

        anomaly_id = None
        if isinstance(details_dict, dict) and "anomaly_id" in details_dict:
            anomaly_id = details_dict.get("anomaly_id")
        activity["anomaly_id"] = anomaly_id

        self.activities.append(activity)

        # Update job progress
        if self.job_id in app_state.background_jobs:
            agents_seen = set(a["agent_name"] for a in self.activities)
            total_agents = 6
            progress = min(0.95, len(agents_seen) / total_agents)
            app_state.background_jobs[self.job_id]["progress"] = progress
            app_state.background_jobs[self.job_id]["updated_at"] = datetime.utcnow().isoformat()

        # Broadcast agent update via WebSocket
        try:
            asyncio.create_task(broadcast_agent_update(agent_name_str, status_str, details_dict or {}))
        except Exception as e:
            self.logger.error(f"Failed to broadcast agent update: {str(e)}")
            self.logger.error(traceback.format_exc())

        # Store activity in database if storage manager is available
        if app_state.storage_manager:
            try:
                if hasattr(app_state.storage_manager, 'check_anomaly_exists') and anomaly_id:
                    anomaly_exists = app_state.storage_manager.check_anomaly_exists(anomaly_id)
                    if not anomaly_exists:
                        self.logger.warning(f"Anomaly {anomaly_id} does not exist in database. Setting anomaly_id to None.")
                        activity["anomaly_id"] = None

                if hasattr(app_state.storage_manager, 'store_agent_activity'):
                    app_state.storage_manager.store_agent_activity(activity)
                else:
                    if hasattr(app_state.storage_manager, 'store_data'):
                        app_state.storage_manager.store_data('agent_activities', activity)
            except Exception as e:
                self.logger.error(f"Failed to store agent activity: {str(e)}")
                self.logger.error(traceback.format_exc())

        self.logger.info(f"Agent {agent_name_str} {action_str}: {status_str}")

    def log_agent_message(self, agent_name, message, anomaly_id=None):
        """
        Log a message from an agent.

        Args:
            agent_name: Name of the agent
            message: Message content
            anomaly_id: Optional ID of related anomaly
        """
        agent_name_str = str(agent_name) if agent_name is not None else "unknown"
        message_str = str(message) if message is not None else ""

        if anomaly_id and app_state.storage_manager and hasattr(app_state.storage_manager, 'check_anomaly_exists'):
            anomaly_exists = app_state.storage_manager.check_anomaly_exists(anomaly_id)
            if not anomaly_exists:
                self.logger.warning(f"Anomaly {anomaly_id} does not exist in database. Setting anomaly_id to None for message.")
                anomaly_id = None

        details = {
            "message": message_str[:500],
            "anomaly_id": anomaly_id
        }

        self.log_agent_activity(agent_name_str, "message", "sent", details)

        if app_state.storage_manager and hasattr(app_state.storage_manager, 'store_agent_message'):
            try:
                message_data = {
                    "agent": agent_name_str,
                    "content": message_str,
                    "anomaly_id": anomaly_id,
                    "job_id": self.job_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
                app_state.storage_manager.store_agent_message(message_data)
            except Exception as e:
                self.logger.error(f"Failed to store agent message: {str(e)}")
                self.logger.error(traceback.format_exc())

    def start_analysis(self, count):
        """Log the start of analysis."""
        count_int = int(count) if isinstance(count, (int, float, str)) else 0
        self.log_agent_activity("agent_manager", "analysis", "started", {"anomaly_count": count_int})

    def update_anomaly_progress(self, current, total, anomaly_id):
        """Update progress of anomaly analysis."""
        current_int = int(current) if isinstance(current, (int, float, str)) else 0
        total_int = int(total) if isinstance(total, (int, float, str)) else 0
        anomaly_id_str = str(anomaly_id) if anomaly_id is not None else None

        self.log_agent_activity(
            "agent_manager", "progress", "updated",
            {"current": current_int, "total": total_int, "anomaly_id": anomaly_id_str}
        )

    def finish_analysis(self, results):
        """Log completion of analysis."""
        result_count = len(results) if isinstance(results, (list, tuple, dict)) else 0
        self.log_agent_activity("agent_manager", "analysis", "completed", {"result_count": result_count})

    def visualize_agent_graph(self, workflow):
        """Log visualization of agent graph."""
        safe_workflow = workflow if isinstance(workflow, dict) else {}
        self.log_agent_activity("visualizer", "graph", "created", {"workflow": safe_workflow})

    def create_agent_timeline(self):
        """Create a timeline of agent activities."""
        self.log_agent_activity("visualizer", "timeline", "created")

    def create_activity_summary(self):
        """Create a summary of agent activities."""
        self.log_agent_activity("visualizer", "summary", "created")

    def display_detailed_analysis(self, results):
        """Display detailed analysis results."""
        result_count = len(results) if isinstance(results, (list, tuple, dict)) else 0
        self.log_agent_activity("visualizer", "detail", "displayed", {"result_count": result_count})

    def log_agent_activity_batch(self, activities):
        """Log multiple agent activities at once."""
        if not isinstance(activities, (list, tuple)):
            self.logger.error("Expected list of activities for batch logging")
            return

        for activity in activities:
            if not isinstance(activity, dict):
                self.logger.warning(f"Skipping non-dict activity in batch: {activity}")
                continue

            self.log_agent_activity(
                activity.get("agent_name", "unknown"),
                activity.get("action", "unknown"),
                activity.get("status", "unknown"),
                activity.get("details", {})
            )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/agents/status", tags=["Agents"], response_model=Dict[str, Any])
async def get_agents_status():
    """
    Get the status of the agent system.

    Returns:
        Agent system status
    """
    logger.info("=== get_agents_status endpoint called ===")
    logger.info(f"agent_manager is: {app_state.agent_manager}")
    logger.info(f"config is: {app_state.config is not None}")

    try:
        enabled = app_state.agent_manager is not None
        logger.info(f"Agent manager enabled: {enabled}")

        configured = False
        if app_state.config is not None:
            agents_config = app_state.config.get("agents", {})
            configured = agents_config.get("enabled", False)
            logger.info(f"Agents configured: {configured}")

        available_agents = []
        workflow = None

        try:
            workflow = get_default_agent_workflow()
            if isinstance(workflow, dict) and "nodes" in workflow:
                available_agents = list(workflow["nodes"])
            logger.info(f"Got workflow with {len(available_agents)} agents")
        except Exception as e:
            logger.warning(f"Error getting default agent workflow: {str(e)}")
            available_agents = ["security_analyst", "threat_intel", "remediation",
                              "code_generator", "security_review", "data_collector"]
            workflow = {
                "nodes": available_agents,
                "edges": [
                    {"from": "security_analyst", "to": "threat_intel"},
                    {"from": "threat_intel", "to": "remediation"},
                    {"from": "remediation", "to": "code_generator"},
                    {"from": "code_generator", "to": "security_review"},
                    {"from": "security_review", "to": "data_collector"}
                ],
                "description": "Multi-agent workflow for comprehensive anomaly analysis"
            }

        response = {
            "enabled": enabled,
            "configured": configured,
            "available_agents": available_agents,
            "workflow": workflow,
            "message": "Agent system is active" if enabled else "Agent system is not initialized. Please check configuration."
        }

        logger.info(f"Returning response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error in get_agents_status: {str(e)}")
        logger.error(traceback.format_exc())

        return {
            "enabled": False,
            "configured": False,
            "available_agents": [],
            "workflow": None,
            "message": f"Error checking agent status: {str(e)}"
        }


@router.get("/agents/test", tags=["Agents"])
async def test_agents_endpoint():
    """Test endpoint to verify agents routing is working."""
    return {
        "status": "ok",
        "message": "Agents test endpoint is working",
        "agent_manager_exists": app_state.agent_manager is not None,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/agents/analyze", tags=["Agents"], response_model=JobStatus)
async def analyze_with_agents(
    background_tasks: BackgroundTasks,
    anomalies: List[Dict[str, Any]] = Body(..., description="Anomalies to analyze")
):
    """
    Analyze anomalies using the agent-based system.

    Args:
        background_tasks: FastAPI background tasks
        anomalies: Anomalies to analyze

    Returns:
        Job status information
    """
    if not app_state.agent_manager:
        raise HTTPException(status_code=404, detail="Agent manager not initialized")

    job_id = f"agent_analysis_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.utcnow().isoformat()

    app_state.background_jobs[job_id] = {
        "job_id": job_id,
        "job_type": "agent_analysis",
        "status": "pending",
        "start_time": current_time,
        "end_time": None,
        "parameters": {"anomaly_count": len(anomalies)},
        "result": None,
        "progress": 0.0,
        "created_at": current_time,
        "updated_at": current_time
    }

    background_tasks.add_task(agent_analysis_job, anomalies, job_id)

    return app_state.background_jobs[job_id]


@router.post("/agents/verbose-analyze", tags=["Agents"], response_model=JobStatus)
async def analyze_with_agents_verbose(
    background_tasks: BackgroundTasks,
    anomalies: List[Dict[str, Any]] = Body(..., description="Anomalies to analyze")
):
    """
    Analyze anomalies using the agent-based system with enhanced verbosity.

    Args:
        background_tasks: FastAPI background tasks
        anomalies: Anomalies to analyze

    Returns:
        Job status information
    """
    if not app_state.agent_manager:
        logger.error("Agent manager not initialized")
        raise HTTPException(
            status_code=503,
            detail="Agent manager not initialized. Please ensure the system is properly initialized with agents enabled in the configuration."
        )

    job_id = f"verbose_agent_analysis_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.utcnow().isoformat()

    app_state.background_jobs[job_id] = {
        "job_id": job_id,
        "job_type": "verbose_agent_analysis",
        "status": "pending",
        "start_time": current_time,
        "end_time": None,
        "parameters": {"anomaly_count": len(anomalies)},
        "result": None,
        "progress": 0.0,
        "created_at": current_time,
        "updated_at": current_time,
        "verbose": True
    }

    background_tasks.add_task(verbose_agent_analysis_job, anomalies, job_id)

    return app_state.background_jobs[job_id]


@router.post("/agents/analyze-detailed", tags=["Agents"], response_model=Dict[str, Any])
async def analyze_with_agents_detailed(
    background_tasks: BackgroundTasks,
    anomalies: List[Dict[str, Any]] = Body(..., description="Anomalies to analyze"),
    include_dialogue: bool = Query(True, description="Include agent dialogue in response"),
    include_evidence: bool = Query(True, description="Include evidence chain in response")
):
    """
    Analyze anomalies using the enhanced agent-based system with detailed results.

    Args:
        background_tasks: FastAPI background tasks
        anomalies: Anomalies to analyze
        include_dialogue: Whether to include agent dialogue
        include_evidence: Whether to include evidence chain

    Returns:
        Detailed analysis results including agent interactions
    """
    if not app_state.agent_manager:
        raise HTTPException(status_code=404, detail="Agent manager not initialized")

    if hasattr(app_state.agent_manager, 'mode') and app_state.agent_manager.mode != "enhanced":
        raise HTTPException(
            status_code=400,
            detail="Enhanced agent mode not enabled. Ensure 'enabled: true' is set in the agents config"
        )

    job_id = f"detailed_agent_analysis_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.utcnow().isoformat()

    app_state.background_jobs[job_id] = {
        "job_id": job_id,
        "job_type": "detailed_agent_analysis",
        "status": "pending",
        "start_time": current_time,
        "end_time": None,
        "parameters": {
            "anomaly_count": len(anomalies),
            "include_dialogue": include_dialogue,
            "include_evidence": include_evidence
        },
        "result": None,
        "progress": 0.0,
        "created_at": current_time,
        "updated_at": current_time
    }

    background_tasks.add_task(
        detailed_agent_analysis_job,
        anomalies,
        job_id,
        include_dialogue,
        include_evidence
    )

    return app_state.background_jobs[job_id]


@router.get("/agents/dialogue/{job_id}/{anomaly_id}", tags=["Agents"])
async def get_agent_dialogue(
    job_id: str = Path(..., description="Job ID"),
    anomaly_id: str = Path(..., description="Anomaly ID")
):
    """
    Get the agent dialogue for a specific anomaly.
    """
    if job_id not in app_state.background_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = app_state.background_jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    results = job.get("result", {}).get("detailed_results", [])
    for result in results:
        if result.get("id") == anomaly_id:
            return {
                "anomaly_id": anomaly_id,
                "dialogue": result.get("agent_dialogue", []),
                "confidence_scores": result.get("confidence_scores", {}),
                "consensus_notes": result.get("analysis", {}).get("consensus_notes", "")
            }

    raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")


@router.get("/agents/workflow", tags=["Agents"], response_model=Dict[str, Any])
async def get_agent_workflow():
    """
    Get the agent workflow configuration.

    Returns:
        Agent workflow configuration
    """
    if not app_state.agent_manager:
        logger.info("Agent manager not initialized, returning default workflow")
        return get_default_agent_workflow()

    try:
        if hasattr(app_state.agent_manager, 'agent_workflow') and app_state.agent_manager.agent_workflow:
            return app_state.agent_manager.agent_workflow
        elif hasattr(app_state.agent_manager, 'config') and 'workflow' in app_state.agent_manager.config:
            return app_state.agent_manager.config['workflow']
        else:
            return get_default_agent_workflow()
    except Exception as e:
        logger.error(f"Error getting agent workflow: {str(e)}")
        return get_default_agent_workflow()


@router.get("/agents/{agent_name}", tags=["Agents"], response_model=Dict[str, Any])
async def get_agent_details(agent_name: str = Path(..., description="Name of the agent")):
    """
    Get detailed information about a specific agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Agent details
    """
    agent_descriptions = {
        "security_analyst": {
            "name": "security_analyst",
            "description": "Analyzes anomalies to determine severity, threat identification, and false positive evaluation.",
            "system_prompt": "You are a security analyst responsible for analyzing anomalies detected in system logs. Your task is to examine the provided anomaly data and determine the severity, potential threat, detailed analysis, and whether it's likely a false positive.",
            "capabilities": ["Severity assessment", "Threat identification", "False positive detection", "Security analysis"]
        },
        "threat_intel": {
            "name": "threat_intel",
            "description": "Correlates anomalies with known threat patterns and adds threat intelligence context.",
            "system_prompt": "You are a threat intelligence expert responsible for correlating anomalies with known threat patterns and indicators.",
            "capabilities": ["Threat correlation", "Pattern matching", "Intelligence gathering", "Context enrichment"]
        },
        "remediation": {
            "name": "remediation",
            "description": "Provides actionable steps to address security anomalies including containment, investigation, remediation, and prevention.",
            "system_prompt": "You are a security remediation expert responsible for providing actionable steps to address security anomalies.",
            "capabilities": ["Containment strategies", "Investigation steps", "Remediation planning", "Prevention measures"]
        },
        "code_generator": {
            "name": "code_generator",
            "description": "Creates secure, efficient code for remediation actions based on remediation plans.",
            "system_prompt": "You are a security code generator responsible for creating secure, efficient code for remediation actions.",
            "capabilities": ["Script generation", "Security patches", "Automation code", "Implementation guides"]
        },
        "security_review": {
            "name": "security_review",
            "description": "Validates security recommendations and ensures completeness of analysis.",
            "system_prompt": "You are a security reviewer responsible for validating security recommendations and implementation.",
            "capabilities": ["Quality assurance", "Validation checks", "Completeness review", "Best practices verification"]
        },
        "data_collector": {
            "name": "data_collector",
            "description": "Identifies additional data needed for thorough investigation of anomalies.",
            "system_prompt": "You are a security data collector responsible for identifying additional data needed for investigation.",
            "capabilities": ["Data requirements analysis", "Collection strategies", "Evidence gathering", "Monitoring recommendations"]
        }
    }

    if not app_state.agent_manager:
        logger.info("Agent manager not initialized, returning default agent description")
        if agent_name in agent_descriptions:
            return agent_descriptions[agent_name]
        else:
            raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")

    try:
        if agent_name in agent_descriptions:
            agent_details = agent_descriptions[agent_name]

            if hasattr(app_state.agent_manager, 'default_prompts') and agent_name in app_state.agent_manager.default_prompts:
                agent_details["system_prompt"] = app_state.agent_manager.default_prompts.get(agent_name, agent_details["system_prompt"])

            if hasattr(app_state.agent_manager, 'config'):
                custom_prompt = app_state.agent_manager.config.get(f"{agent_name}_agent", {}).get("system_prompt")
                if custom_prompt:
                    agent_details["custom_prompt"] = custom_prompt

            return agent_details
        else:
            raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent details: {str(e)}")
        if agent_name in agent_descriptions:
            return agent_descriptions[agent_name]
        else:
            raise HTTPException(status_code=500, detail=f"Error getting agent details: {str(e)}")


@router.get("/agents/activities/{job_id}", tags=["Agents"], response_model=List[Dict[str, Any]])
async def get_agent_activities(job_id: str = Path(..., description="ID of the agent analysis job")):
    """
    Get detailed activities of agents for a specific analysis job.

    Args:
        job_id: ID of the agent analysis job

    Returns:
        List of agent activities with timestamps and details
    """
    if job_id not in app_state.background_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if not app_state.agent_manager:
        logger.warning("Agent manager not initialized, returning empty activities list")
        return []

    try:
        if app_state.storage_manager and hasattr(app_state.storage_manager, 'get_agent_activities'):
            activities = app_state.storage_manager.get_agent_activities(job_id)
            return activities
        elif app_state.storage_manager and hasattr(app_state.storage_manager, 'query_data'):
            activities = app_state.storage_manager.query_data('agent_activities', {'job_id': job_id})
            return activities
        else:
            return []
    except Exception as e:
        logging.error(f"Error retrieving agent activities: {str(e)}")
        return []


@router.get("/agents/steps/{job_id}", tags=["Agents"], response_model=Dict[str, Any])
async def get_agent_analysis_steps(job_id: str = Path(..., description="ID of the agent analysis job")):
    """
    Get detailed steps of the agent analysis process for a specific job.

    Args:
        job_id: ID of the agent analysis job

    Returns:
        Dictionary with steps and statistics
    """
    if job_id not in app_state.background_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if not app_state.agent_manager:
        logger.warning("Agent manager not initialized, returning minimal steps data")
        return {
            "job_id": job_id,
            "steps": {},
            "statistics": {
                "agent_counts": {},
                "action_counts": {},
                "status_counts": {},
                "total_activities": 0,
                "start_time": None,
                "end_time": None
            }
        }

    activities = []
    try:
        if app_state.storage_manager and hasattr(app_state.storage_manager, 'get_agent_activities'):
            activities = app_state.storage_manager.get_agent_activities(job_id)
        elif app_state.storage_manager and hasattr(app_state.storage_manager, 'query_data'):
            activities = app_state.storage_manager.query_data('agent_activities', {'job_id': job_id})
    except Exception as e:
        logging.error(f"Error retrieving agent activities: {str(e)}")

    steps = {}
    stats = {
        "agent_counts": {},
        "action_counts": {},
        "status_counts": {},
        "total_activities": len(activities),
        "start_time": None,
        "end_time": None
    }

    for activity in activities:
        agent_name = activity.get("agent_name", "unknown")
        action = activity.get("action", "unknown")
        status = activity.get("status", "unknown")
        timestamp = activity.get("timestamp")

        stats["agent_counts"][agent_name] = stats["agent_counts"].get(agent_name, 0) + 1
        stats["action_counts"][action] = stats["action_counts"].get(action, 0) + 1
        stats["status_counts"][status] = stats["status_counts"].get(status, 0) + 1

        if timestamp:
            if stats["start_time"] is None or timestamp < stats["start_time"]:
                stats["start_time"] = timestamp
            if stats["end_time"] is None or timestamp > stats["end_time"]:
                stats["end_time"] = timestamp

        if agent_name not in steps:
            steps[agent_name] = {}

        if action not in steps[agent_name]:
            steps[agent_name][action] = []

        steps[agent_name][action].append(activity)

    return {
        "job_id": job_id,
        "steps": steps,
        "statistics": stats
    }


# ---------------------------------------------------------------------------
# Background jobs
# ---------------------------------------------------------------------------

async def agent_analysis_job(anomalies: List[Dict[str, Any]], job_id: str):
    """
    Background job for analyzing anomalies with agents.

    Args:
        anomalies: Anomalies to analyze
        job_id: ID of the job
    """
    try:
        logging.info(f"Starting agent analysis job {job_id} for {len(anomalies)} anomalies")
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "running"
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
            app_state.background_jobs[job_id]["progress"] = 0.1

        analyzed_anomalies = app_state.agent_manager.analyze_anomalies(anomalies)

        if app_state.storage_manager:
            await asyncio.to_thread(lambda: app_state.storage_manager.store_analysis(analyzed_anomalies))
            logging.info(f"Stored analysis for {len(analyzed_anomalies)} anomalies")

        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "completed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {
                "anomalies_analyzed": len(analyzed_anomalies)
            }

        logging.info(f"Completed agent analysis job {job_id}")

        with app_state.background_jobs_lock:
            result_copy = app_state.background_jobs[job_id]["result"].copy()
        await store_detection_results(job_id, result_copy)

    except Exception as e:
        logging.error(f"Error in agent analysis job {job_id}: {str(e)}")
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "failed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {"error": str(e)}


async def verbose_agent_analysis_job(anomalies: List[Dict[str, Any]], job_id: str):
    """
    Background job for analyzing anomalies with enhanced verbosity.

    Args:
        anomalies: Anomalies to analyze
        job_id: ID of the job
    """
    try:
        logging.info(f"Starting verbose agent analysis job {job_id} for {len(anomalies)} anomalies")
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "running"
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        visualizer = VerboseVisualizer(job_id)

        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["progress"] = 0.1
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        # Swap visualizer with try/finally to prevent race condition
        original_visualizer = app_state.agent_manager.visualizer
        app_state.agent_manager.visualizer = visualizer
        try:
            analyzed_anomalies = app_state.agent_manager.analyze_anomalies(anomalies)
        finally:
            app_state.agent_manager.visualizer = original_visualizer

        if app_state.storage_manager:
            if hasattr(app_state.storage_manager, 'store_analysis'):
                await asyncio.to_thread(lambda: app_state.storage_manager.store_analysis(analyzed_anomalies))
            elif hasattr(app_state.storage_manager, 'store_data'):
                await asyncio.to_thread(lambda: app_state.storage_manager.store_data('analysis_results', analyzed_anomalies))
            logging.info(f"Stored analysis for {len(analyzed_anomalies)} anomalies")

        severity_counts = {
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0,
            "Unknown": 0
        }

        false_positives = 0

        for anomaly in analyzed_anomalies:
            analysis = anomaly.get("analysis", {})
            if isinstance(analysis, dict):
                severity = analysis.get("severity", "Unknown")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

                if analysis.get("false_positive", False):
                    false_positives += 1
            elif isinstance(analysis, str):
                severity = "Unknown"
                for sev in ["Critical", "High", "Medium", "Low"]:
                    if sev.lower() in analysis.lower():
                        severity = sev
                        break
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "completed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {
                "anomalies_analyzed": len(analyzed_anomalies),
                "agent_activities_count": len(visualizer.activities),
                "severity_counts": severity_counts,
                "false_positives": false_positives
            }

        logging.info(f"Completed verbose agent analysis job {job_id}")

        with app_state.background_jobs_lock:
            result_copy = app_state.background_jobs[job_id]["result"].copy()
        await store_detection_results(job_id, result_copy)

    except Exception as e:
        logging.error(f"Error in verbose agent analysis job {job_id}: {str(e)}")
        logging.error(traceback.format_exc())
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "failed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {"error": str(e)}


async def detailed_agent_analysis_job(
    anomalies: List[Dict[str, Any]],
    job_id: str,
    include_dialogue: bool,
    include_evidence: bool
):
    """
    Background job for detailed agent analysis.
    """
    try:
        logging.info(f"Starting detailed agent analysis job {job_id}")
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "running"
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        enhanced_visualizer = VerboseVisualizer(job_id)

        # Swap visualizer with try/finally to prevent race condition
        original_visualizer = app_state.agent_manager.visualizer
        app_state.agent_manager.visualizer = enhanced_visualizer
        try:
            analyzed_anomalies = app_state.agent_manager.analyze_anomalies(anomalies)
        finally:
            app_state.agent_manager.visualizer = original_visualizer

        for anomaly in analyzed_anomalies:
            if not include_dialogue:
                anomaly.pop("agent_dialogue", None)
            if not include_evidence:
                anomaly.pop("evidence_chain", None)

        total_dialogues = sum(len(a.get("agent_dialogue", [])) for a in analyzed_anomalies)
        avg_confidence = {
            agent: sum(a.get("confidence_scores", {}).get(agent, 0) for a in analyzed_anomalies) / len(analyzed_anomalies)
            for agent in ["security_analyst", "threat_intel", "remediation"]
        }

        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "completed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {
                "anomalies_analyzed": len(analyzed_anomalies),
                "total_agent_dialogues": total_dialogues,
                "average_confidence_scores": avg_confidence,
                "detailed_results": analyzed_anomalies
            }

        logging.info(f"Completed detailed agent analysis job {job_id}")

    except Exception as e:
        logging.error(f"Error in detailed agent analysis job {job_id}: {str(e)}")
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "failed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["result"] = {"error": str(e)}
