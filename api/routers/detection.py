"""Anomaly detection routes and background jobs."""
import asyncio
import logging
import traceback
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Path, Body

from api.state import app_state
from api.schemas import DetectionRequest, BulkDetectionRequest, DataBatch, JobStatus
from api.helpers import store_detection_results

# Import processor classes with try/except
try:
    from anomaly_detection.processors.normalizer import Normalizer
except ImportError:
    Normalizer = None

try:
    from anomaly_detection.processors.feature_extractor import FeatureExtractor as _FE
    # Use concrete fallback if the class is abstract (avoid test instantiation side-effect)
    if getattr(_FE, '__abstractmethods__', None):
        from api.extractors import ConcreteFeatureExtractor as FeatureExtractor
    else:
        FeatureExtractor = _FE
except ImportError:
    from api.extractors import ConcreteFeatureExtractor as FeatureExtractor

logger = logging.getLogger("api_services")
router = APIRouter()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/detect", tags=["Detection"], response_model=JobStatus)
async def detect_anomalies_simplified(
    background_tasks: BackgroundTasks,
    detection_request: DetectionRequest
):
    """
    Simplified endpoint for anomaly detection.

    Args:
        background_tasks: FastAPI background tasks
        detection_request: Detection request with model, data, and optional threshold

    Returns:
        Job status information
    """
    model_name = detection_request.model_name
    data = detection_request.data
    threshold = detection_request.threshold

    if model_name not in app_state.models:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")

    # Create a job ID
    job_id = f"detect_{model_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.utcnow().isoformat()

    # Initialize job status
    app_state.background_jobs[job_id] = {
        "job_id": job_id,
        "job_type": "detect_anomalies",
        "status": "pending",
        "start_time": current_time,
        "end_time": None,
        "parameters": {
            "model_name": model_name,
            "data_count": len(data),
            "threshold": threshold
        },
        "result": None,
        "progress": 0.0,
        "created_at": current_time,
        "updated_at": current_time
    }

    # Start detection job in background
    background_tasks.add_task(detect_anomalies_job, model_name, data, job_id, threshold)

    return app_state.background_jobs[job_id]


@router.post("/models/{model_name}/detect", tags=["Models"], response_model=JobStatus)
async def detect_anomalies(
    background_tasks: BackgroundTasks,
    model_name: str = Path(..., description="Name of the model to use for detection"),
    data_batch: DataBatch = Body(..., description="Batch of data items for anomaly detection"),
    threshold: Optional[float] = Query(None, description="Optional detection threshold override")
):
    """
    Detect anomalies in the provided data.

    Args:
        background_tasks: FastAPI background tasks
        model_name: Name of the model to use
        data_batch: Batch of data items for detection
        threshold: Optional detection threshold override

    Returns:
        Job status information
    """
    if model_name not in app_state.models:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")

    # Create a job ID
    job_id = f"detect_{model_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.utcnow().isoformat()

    # Initialize job status
    app_state.background_jobs[job_id] = {
        "job_id": job_id,
        "job_type": "detect_anomalies",
        "status": "pending",
        "start_time": current_time,
        "end_time": None,
        "parameters": {
            "model_name": model_name,
            "data_count": len(data_batch.items),
            "threshold": threshold
        },
        "result": None,
        "progress": 0.0,
        "created_at": current_time,
        "updated_at": current_time
    }

    # Start detection job in background
    background_tasks.add_task(detect_anomalies_job, model_name, data_batch.items, job_id, threshold)

    return app_state.background_jobs[job_id]


@router.post("/bulk-detect", tags=["Detection"], response_model=JobStatus)
async def bulk_detect_anomalies(
    background_tasks: BackgroundTasks,
    bulk_request: BulkDetectionRequest
):
    """
    Detect anomalies using multiple models at once.

    Args:
        background_tasks: FastAPI background tasks
        bulk_request: Bulk detection request with models and data

    Returns:
        Job status information
    """
    model_names = bulk_request.models
    data = bulk_request.data

    # Validate models exist
    valid_models = [model for model in model_names if model in app_state.models]
    if not valid_models:
        raise HTTPException(status_code=404, detail="None of the specified models were found")

    # Create a job ID
    model_count = len(valid_models)
    job_id = f"bulk_detect_{model_count}_models_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.utcnow().isoformat()

    # Initialize job status
    app_state.background_jobs[job_id] = {
        "job_id": job_id,
        "job_type": "bulk_detect_anomalies",
        "status": "pending",
        "start_time": current_time,
        "end_time": None,
        "parameters": {
            "models": valid_models,
            "data_count": len(data)
        },
        "result": None,
        "progress": 0.0,
        "created_at": current_time,
        "updated_at": current_time
    }

    # Start bulk detection job in background
    background_tasks.add_task(bulk_detect_anomalies_job, valid_models, data, job_id)

    return app_state.background_jobs[job_id]


# ---------------------------------------------------------------------------
# Background jobs
# ---------------------------------------------------------------------------

async def detect_anomalies_job(model_name: str, data_items: List[Dict[str, Any]], job_id: str, threshold: Optional[float] = None):
    """
    Background job for detecting anomalies in the provided data.

    Args:
        model_name: Name of the model to use
        data_items: List of data items for detection
        job_id: ID of the job
        threshold: Optional custom threshold for detection
    """
    try:
        logging.info(f"Starting detection job {job_id} for model {model_name}")
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "running"
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        # Get the model
        if model_name not in app_state.models:
            raise ValueError(f"Model {model_name} not found")

        model = app_state.models[model_name]

        # Check if the model is trained using multiple methods for robustness
        model_trained = False

        if hasattr(model, 'is_trained') and model.is_trained:
            model_trained = True
        elif hasattr(model, 'model') and model.model is not None:
            model_trained = True
        elif hasattr(model, 'model_state') and model.model_state:
            if isinstance(model.model_state, dict) and len(model.model_state) > 0:
                if hasattr(model, 'feature_stats') and model.feature_stats:
                    model_trained = True
                elif 'feature_stats' in model.model_state or model.model_state.get('is_trained', False):
                    model_trained = True
                elif any(key in model.model_state for key in ['state', 'feature_stats', 'weights', 'model']):
                    model_trained = True

        if not model_trained:
            raise ValueError(f"Model {model_name} is not trained yet. Train the model before using it for detection.")

        # Apply custom threshold if provided
        original_threshold = None
        if threshold is not None:
            original_threshold = model.threshold
            model.threshold = threshold
            logging.info(f"Using custom threshold of {threshold} for model {model_name}")

        # Normalize and extract features from data
        processed_data = data_items

        # Apply normalizers
        for processor_name, processor in app_state.processors.items():
            if Normalizer and isinstance(processor, Normalizer):
                processed_data = processor.process(processed_data)
                logging.info(f"Applied normalizer {processor_name} to data")

        # Apply feature extractors
        for processor_name, processor in app_state.processors.items():
            if isinstance(processor, FeatureExtractor):
                processed_data = processor.process(processed_data)
                logging.info(f"Applied feature extractor {processor_name} to data")

        # Update progress
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["progress"] = 0.5
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        # Check for ensemble model handling
        if model_name == "ensemble_model":
            models_dict = {name: m for name, m in app_state.models.items() if name != "ensemble_model"}
            anomalies = model.detect(processed_data, models=models_dict)
        else:
            anomalies = model.detect(processed_data)

        # Ensure all required fields are present in anomalies
        for anomaly in anomalies:
            if "model" not in anomaly or not anomaly["model"]:
                anomaly["model"] = model_name

            score = anomaly.get("score", 0)
            if "severity" not in anomaly:
                if score >= 0.9:
                    anomaly["severity"] = "Critical"
                elif score >= 0.8:
                    anomaly["severity"] = "High"
                elif score >= 0.6:
                    anomaly["severity"] = "Medium"
                else:
                    anomaly["severity"] = "Low"

            if "location" not in anomaly or not anomaly["location"]:
                original_data = anomaly.get("original_data", {})
                if isinstance(original_data, dict):
                    location_candidates = ["location", "host", "hostname", "device", "server", "instance"]
                    for field in location_candidates:
                        if field in original_data and original_data[field]:
                            anomaly["location"] = str(original_data[field])
                            break

                    if "location" not in anomaly:
                        ip_candidates = ["ip", "ip_address", "source_ip", "dest_ip", "host_ip"]
                        for field in ip_candidates:
                            if field in original_data and original_data[field]:
                                anomaly["location"] = f"ip-{original_data[field]}"
                                break

                if "location" not in anomaly or not anomaly["location"]:
                    anomaly["location"] = "unknown"

            if "detection_time" not in anomaly:
                anomaly["detection_time"] = datetime.utcnow().isoformat()

            if "id" not in anomaly:
                anomaly["id"] = str(uuid.uuid4())

            if "timestamp" not in anomaly:
                anomaly["timestamp"] = datetime.utcnow().isoformat()

            if "original_data" in anomaly and "data" not in anomaly:
                anomaly["data"] = anomaly["original_data"]

        # Store detected anomalies
        if app_state.storage_manager and anomalies:
            await asyncio.to_thread(lambda: app_state.storage_manager.store_anomalies(anomalies))
            logging.info(f"Stored {len(anomalies)} detected anomalies")

            if app_state.alert_manager:
                for anomaly in anomalies:
                    await app_state.alert_manager.send_alert(anomaly)
        elif not app_state.storage_manager:
            logging.error("Storage manager not available. Cannot store anomalies.")
        elif not anomalies:
            logging.info("No anomalies detected to store.")

        # Update job status
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "completed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {
                "model": model_name,
                "anomalies_detected": len(anomalies) if anomalies else 0,
                "threshold": threshold if threshold is not None else model.threshold,
                "sample_anomalies": anomalies[:5] if anomalies else []
            }

        # Restore original threshold if it was changed
        if original_threshold is not None:
            model.threshold = original_threshold

        logging.info(f"Completed detection job {job_id} with {len(anomalies) if anomalies else 0} anomalies")

        # Store job results in database
        with app_state.background_jobs_lock:
            result_copy = app_state.background_jobs[job_id]["result"].copy()
        await store_detection_results(job_id, result_copy)

    except Exception as e:
        logging.error(f"Error in detection job {job_id}: {str(e)}")
        logging.error(traceback.format_exc())
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "failed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {"model": model_name, "error": str(e)}


async def bulk_detect_anomalies_job(model_names: List[str], data_items: List[Dict[str, Any]], job_id: str):
    """
    Background job for detecting anomalies across multiple models with enhanced field validation.

    Args:
        model_names: List of model names to use
        data_items: List of data items for detection
        job_id: ID of the job
    """
    try:
        logging.info(f"Starting bulk detection job {job_id} across {len(model_names)} models")
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "running"
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        # Normalize and extract features from data (only once)
        processed_data = data_items

        # Apply normalizers
        for processor_name, processor in app_state.processors.items():
            if Normalizer and isinstance(processor, Normalizer):
                processed_data = processor.process(processed_data)
                logging.info(f"Applied normalizer {processor_name} to data")

        # Apply feature extractors
        for processor_name, processor in app_state.processors.items():
            if isinstance(processor, FeatureExtractor):
                processed_data = processor.process(processed_data)
                logging.info(f"Applied feature extractor {processor_name} to data")

        # Run detection on each model
        all_anomalies = []
        failed_models = []

        for i, model_name in enumerate(model_names):
            try:
                if model_name not in app_state.models:
                    logging.warning(f"Model {model_name} not found, skipping")
                    failed_models.append({"model": model_name, "error": "Model not found"})
                    continue

                model = app_state.models[model_name]

                # Update progress
                progress = (i + 0.5) / len(model_names)
                with app_state.background_jobs_lock:
                    app_state.background_jobs[job_id]["progress"] = progress
                    app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

                if model_name == "ensemble_model":
                    models_dict = {name: m for name, m in app_state.models.items() if name != "ensemble_model"}
                    model_anomalies = model.detect(processed_data, models=models_dict)
                else:
                    model_anomalies = model.detect(processed_data)

                # Ensure all required fields are present
                for anomaly in model_anomalies:
                    if "model" not in anomaly or not anomaly["model"]:
                        anomaly["model"] = model_name

                    score = anomaly.get("score", 0)
                    if "severity" not in anomaly:
                        if score >= 0.9:
                            anomaly["severity"] = "Critical"
                        elif score >= 0.8:
                            anomaly["severity"] = "High"
                        elif score >= 0.6:
                            anomaly["severity"] = "Medium"
                        else:
                            anomaly["severity"] = "Low"

                    if "location" not in anomaly or not anomaly["location"]:
                        original_data = anomaly.get("original_data", {})
                        if isinstance(original_data, dict):
                            location_candidates = ["location", "host", "hostname", "device", "server", "instance"]
                            for field in location_candidates:
                                if field in original_data and original_data[field]:
                                    anomaly["location"] = str(original_data[field])
                                    break

                            if "location" not in anomaly:
                                ip_candidates = ["ip", "ip_address", "source_ip", "dest_ip", "src_ip", "dst_ip"]
                                for field in ip_candidates:
                                    if field in original_data and original_data[field]:
                                        anomaly["location"] = f"ip-{original_data[field]}"
                                        break

                        if "location" not in anomaly or not anomaly["location"]:
                            if anomaly.get("src_ip"):
                                anomaly["location"] = f"src-{anomaly['src_ip']}"
                            elif anomaly.get("dst_ip"):
                                anomaly["location"] = f"dst-{anomaly['dst_ip']}"
                            else:
                                anomaly["location"] = "unknown"

                    if "detection_time" not in anomaly:
                        anomaly["detection_time"] = datetime.utcnow().isoformat()

                    if "id" not in anomaly:
                        anomaly["id"] = str(uuid.uuid4())

                    if "timestamp" not in anomaly:
                        anomaly["timestamp"] = datetime.utcnow().isoformat()

                    if "original_data" in anomaly and "data" not in anomaly:
                        anomaly["data"] = anomaly["original_data"]

                all_anomalies.extend(model_anomalies)
                logging.info(f"Detected {len(model_anomalies)} anomalies with model {model_name}")
            except Exception as e:
                logging.error(f"Error detecting anomalies with model {model_name}: {str(e)}")
                failed_models.append({"model": model_name, "error": str(e)})

        # Store all detected anomalies
        if app_state.storage_manager and all_anomalies:
            await asyncio.to_thread(lambda: app_state.storage_manager.store_anomalies(all_anomalies))
            logging.info(f"Stored {len(all_anomalies)} detected anomalies")

            if app_state.alert_manager:
                for anomaly in all_anomalies:
                    await app_state.alert_manager.send_alert(anomaly)

        # Update job status
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "completed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {
                "models": model_names,
                "models_processed": len(model_names) - len(failed_models),
                "failed_models": failed_models,
                "anomalies_detected": len(all_anomalies),
                "sample_anomalies": all_anomalies[:5] if all_anomalies else []
            }

        logging.info(f"Completed bulk detection job {job_id} with {len(all_anomalies)} anomalies across {len(model_names)} models")

        # Store job results in database
        with app_state.background_jobs_lock:
            result_copy = app_state.background_jobs[job_id]["result"].copy()
        await store_detection_results(job_id, result_copy)

    except Exception as e:
        logging.error(f"Error in bulk detection job {job_id}: {str(e)}")
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "failed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {"error": str(e)}
