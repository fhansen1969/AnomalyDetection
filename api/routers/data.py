"""Data processing, collection, and storage routes."""
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Path

from api.state import app_state
from api.schemas import DataBatch, JobStatus
from api.helpers import store_detection_results

# Import processor classes with try/except
try:
    from anomaly_detection.processors.normalizer import Normalizer
except ImportError:
    Normalizer = None

try:
    from anomaly_detection.processors.feature_extractor import FeatureExtractor as _FE
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

@router.get("/processors", tags=["Processors"], response_model=List[Dict[str, Any]])
async def list_processors():
    """
    List all available processors.

    Returns:
        List of processor information
    """
    if not app_state.processors:
        return []

    result = []
    for name, processor in app_state.processors.items():
        processor_info = {
            "name": name,
            "type": processor.__class__.__name__,
            "config": processor.config,
            "created_at": getattr(processor, 'created_at', datetime.utcnow().isoformat()),
            "updated_at": getattr(processor, 'updated_at', datetime.utcnow().isoformat())
        }
        result.append(processor_info)

    return result


@router.get("/collectors", tags=["Collectors"], response_model=List[Dict[str, Any]])
async def list_collectors():
    """
    List all available collectors.

    Returns:
        List of collector information
    """
    if not app_state.collectors:
        return []

    result = []
    for name, collector in app_state.collectors.items():
        collector_info = {
            "name": name,
            "type": collector.__class__.__name__,
            "status": "active" if hasattr(collector, 'running') and collector.running else "inactive",
            "config": collector.config,
            "created_at": getattr(collector, 'created_at', datetime.utcnow().isoformat()),
            "updated_at": getattr(collector, 'updated_at', datetime.utcnow().isoformat())
        }
        result.append(collector_info)

    return result


@router.post("/collectors/{collector_name}/collect", tags=["Collectors"], response_model=JobStatus)
async def collect_data(
    background_tasks: BackgroundTasks,
    collector_name: str = Path(..., description="Name of the collector to use")
):
    """
    Collect data using a specific collector.

    Args:
        background_tasks: FastAPI background tasks
        collector_name: Name of the collector to use

    Returns:
        Job status information
    """
    try:
        if collector_name not in app_state.collectors:
            available = list(app_state.collectors.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Collector {collector_name} not found. Available collectors: {available}"
            )

        # Debug the collector object
        collector = app_state.collectors[collector_name]
        logging.info(f"Collector found: {collector_name}, type: {type(collector).__name__}")

        # Check if collector has required methods
        required_methods = ['collect', 'collect_async']
        has_methods = [method for method in required_methods if hasattr(collector, method) and callable(getattr(collector, method))]
        if not has_methods:
            raise HTTPException(
                status_code=400,
                detail=f"Collector {collector_name} does not have required methods: {required_methods}"
            )

        # Create a job ID
        job_id = f"collect_{collector_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        current_time = datetime.utcnow().isoformat()

        # Initialize job status
        app_state.background_jobs[job_id] = {
            "job_id": job_id,
            "job_type": "collect_data",
            "status": "pending",
            "start_time": current_time,
            "end_time": None,
            "parameters": {"collector_name": collector_name},
            "result": None,
            "progress": 0.0,
            "created_at": current_time,
            "updated_at": current_time
        }

        # Start collection job in background
        background_tasks.add_task(collect_data_job, collector_name, job_id)

        return app_state.background_jobs[job_id]
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in collect_data endpoint for {collector_name}: {str(e)}")
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error collecting data with {collector_name}: {str(e)}"
        )


@router.get("/debug/collectors", tags=["Debug"])
async def debug_collectors():
    """
    Debug endpoint to show available collectors.

    Returns:
        List of available collectors
    """
    return {
        "available_collectors": list(app_state.collectors.keys()),
        "collector_types": [collector.__class__.__name__ for collector in app_state.collectors.values()],
        "config_collectors": app_state.config.get("collectors", {}).get("enabled", []) if app_state.config else []
    }


@router.post("/data/process", tags=["Data"], response_model=List[Dict[str, Any]])
async def process_data(data_batch: DataBatch):
    """
    Process a batch of data through the entire pipeline.

    Args:
        data_batch: Batch of data items to process

    Returns:
        List of fully processed data items
    """
    try:
        if not app_state.processors:
            logging.warning("No processors available, returning data as-is")
            return data_batch.items

        processed_data = data_batch.items

        if not isinstance(processed_data, list):
            processed_data = [processed_data]

        # Apply normalizers with error handling
        normalizer_count = 0
        for processor_name, processor in app_state.processors.items():
            try:
                if Normalizer and isinstance(processor, Normalizer):
                    processed_data = processor.process(processed_data)
                    normalizer_count += 1
                    logging.info(f"Applied normalizer {processor_name} to data")
            except Exception as e:
                logging.error(f"Error applying normalizer {processor_name}: {str(e)}")

        if normalizer_count == 0:
            logging.info("No normalizers applied to data")

        # Apply feature extractors with error handling
        extractor_count = 0
        for processor_name, processor in app_state.processors.items():
            try:
                if isinstance(processor, FeatureExtractor):
                    processed_data = processor.process(processed_data)
                    extractor_count += 1
                    logging.info(f"Applied feature extractor {processor_name} to data")
            except Exception as e:
                logging.error(f"Error applying feature extractor {processor_name}: {str(e)}")

        if extractor_count == 0:
            logging.info("No feature extractors applied to data")

        return processed_data

    except Exception as e:
        logging.error(f"Error in process_data endpoint: {str(e)}")
        logging.error(traceback.format_exc())
        return data_batch.items


@router.post("/processors/normalize", tags=["Processors"], response_model=List[Dict[str, Any]])
async def normalize_data(data_batch: DataBatch):
    """
    Normalize a batch of data items.

    Args:
        data_batch: Batch of data items to normalize

    Returns:
        List of normalized data items
    """
    try:
        if not app_state.processors:
            logging.warning("No processors available, returning data as-is")
            return data_batch.items

        normalizers = [p for name, p in app_state.processors.items() if Normalizer and isinstance(p, Normalizer)]

        if not normalizers:
            logging.warning("No normalizer processors found, returning data as-is")
            return data_batch.items

        processed_data = data_batch.items

        for i, normalizer in enumerate(normalizers):
            try:
                processed_data = normalizer.process(processed_data)
                logging.info(f"Applied normalizer {i+1} of {len(normalizers)}")
            except Exception as e:
                logging.error(f"Error in normalizer {i+1}: {str(e)}")

        return processed_data

    except Exception as e:
        logging.error(f"Error in normalize_data endpoint: {str(e)}")
        logging.error(traceback.format_exc())
        return data_batch.items


@router.post("/processors/extract_features", tags=["Processors"], response_model=List[Dict[str, Any]])
async def extract_features(data_batch: DataBatch):
    """
    Extract features from a batch of data items.

    Args:
        data_batch: Batch of data items for feature extraction

    Returns:
        List of data items with extracted features
    """
    try:
        if not app_state.processors:
            logging.warning("No processors available, returning data as-is")
            return data_batch.items

        extractors = [p for name, p in app_state.processors.items() if isinstance(p, FeatureExtractor)]

        if not extractors:
            logging.warning("No feature extractor processors found, returning data as-is")
            return data_batch.items

        processed_data = data_batch.items

        for i, extractor in enumerate(extractors):
            try:
                processed_data = extractor.process(processed_data)
                logging.info(f"Applied feature extractor {i+1} of {len(extractors)}")
            except Exception as e:
                logging.error(f"Error in feature extractor {i+1}: {str(e)}")

        return processed_data

    except Exception as e:
        logging.error(f"Error in extract_features endpoint: {str(e)}")
        logging.error(traceback.format_exc())
        return data_batch.items


@router.post("/data/store", tags=["Data"], response_model=Dict[str, Any])
async def store_data(data_batch: DataBatch):
    """
    Store processed data in the storage backend.

    Args:
        data_batch: Batch of data items to store

    Returns:
        Storage status
    """
    if not app_state.storage_manager:
        logging.warning("Storage manager not initialized")
        return {
            "status": "warning",
            "message": "Storage manager not initialized, data not stored",
            "items_stored": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

    try:
        data_items = data_batch.items
        if not isinstance(data_items, list):
            data_items = [data_items]

        try:
            await asyncio.to_thread(lambda: app_state.storage_manager.store_processed_data(data_items))
            stored_count = len(data_items)
        except Exception as e:
            logging.error(f"Error storing data: {str(e)}")
            if hasattr(app_state.storage_manager, 'connect'):
                try:
                    await asyncio.to_thread(lambda: app_state.storage_manager.connect())
                    await asyncio.to_thread(lambda: app_state.storage_manager.store_processed_data(data_items))
                    stored_count = len(data_items)
                except Exception:
                    stored_count = 0
            else:
                stored_count = 0

        return {
            "status": "success" if stored_count > 0 else "error",
            "items_stored": stored_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Error storing data: {str(e)}")
        logging.error(traceback.format_exc())
        return {
            "status": "error",
            "message": f"Error storing data: {str(e)}",
            "items_stored": 0,
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/data/load", tags=["Data"], response_model=List[Dict[str, Any]])
async def load_data(latest: bool = Query(False, description="Whether to load only the latest batch")):
    """
    Load processed data from storage.

    Args:
        latest: Whether to load only the latest batch

    Returns:
        List of processed data items
    """
    if not app_state.storage_manager:
        logging.warning("Storage manager not initialized")
        return []

    try:
        try:
            data = app_state.storage_manager.load_processed_data(latest)
        except Exception as e:
            logging.error(f"Error loading data: {str(e)}")
            if hasattr(app_state.storage_manager, 'connect'):
                try:
                    await asyncio.to_thread(lambda: app_state.storage_manager.connect())
                    data = app_state.storage_manager.load_processed_data(latest)
                except Exception:
                    data = []
            else:
                data = []

        if not isinstance(data, list):
            data = []

        return data
    except Exception as e:
        logging.error(f"Error loading data: {str(e)}")
        logging.error(traceback.format_exc())
        return []


@router.get("/processors/status", tags=["Debug"], response_model=Dict[str, Any])
async def get_processors_status():
    """
    Get detailed status of all processors.

    Returns:
        Processor status information
    """
    status = {
        "total_processors": len(app_state.processors),
        "normalizers": [],
        "feature_extractors": [],
        "other": []
    }

    for name, processor in app_state.processors.items():
        processor_info = {
            "name": name,
            "type": processor.__class__.__name__,
            "config": getattr(processor, 'config', {}),
            "active": True
        }

        if Normalizer and isinstance(processor, Normalizer):
            status["normalizers"].append(processor_info)
        elif isinstance(processor, FeatureExtractor):
            status["feature_extractors"].append(processor_info)
        else:
            status["other"].append(processor_info)

    status["normalizer_count"] = len(status["normalizers"])
    status["feature_extractor_count"] = len(status["feature_extractors"])

    return status


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------

async def collect_data_job(collector_name: str, job_id: str):
    """
    Background job for collecting data.

    Args:
        collector_name: Name of the collector to use
        job_id: ID of the job
    """
    try:
        logging.info(f"Starting collection job {job_id} for collector {collector_name}")
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "running"
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        collector = app_state.collectors.get(collector_name)
        if not collector:
            raise ValueError(f"Collector {collector_name} not found")

        logging.info(f"Collector type: {type(collector).__name__}")

        # Update progress
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["progress"] = 0.1
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        # Collect data - handle both async and sync collectors
        collected_data = []

        if hasattr(collector, 'collect_async') and callable(collector.collect_async):
            logging.info(f"Using async collection method for {collector_name}")
            collected_data = await collector.collect_async()
        elif hasattr(collector, 'collect') and callable(collector.collect):
            logging.info(f"Using sync collection method for {collector_name}")
            collected_data = collector.collect()
        else:
            raise ValueError(f"Collector {collector_name} does not have valid collect or collect_async methods")

        if not collected_data:
            collected_data = []
            logging.warning(f"Collector {collector_name} returned no data")

        if not isinstance(collected_data, list):
            logging.warning(f"Collector {collector_name} returned non-list data: {type(collected_data)}")
            if isinstance(collected_data, dict):
                collected_data = [collected_data]
            else:
                collected_data = []

        # Update progress
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["progress"] = 0.5
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        # Process collected data through processors if any
        processed_data = collected_data

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
            app_state.background_jobs[job_id]["progress"] = 0.8
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        # Store processed data
        if app_state.storage_manager and processed_data:
            await asyncio.to_thread(lambda: app_state.storage_manager.store_processed_data(processed_data))
            logging.info(f"Stored {len(processed_data)} processed data items")

        # Update job status
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "completed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {
                "collector": collector_name,
                "items_collected": len(collected_data),
                "items_processed": len(processed_data)
            }

        logging.info(f"Completed collection job {job_id} with {len(collected_data)} items")

        # Store job results in database
        with app_state.background_jobs_lock:
            result_copy = app_state.background_jobs[job_id]["result"].copy()
        await store_detection_results(job_id, result_copy)

    except Exception as e:
        logging.error(f"Error in collection job {job_id}: {str(e)}")
        logging.error(traceback.format_exc())
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "failed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {"collector": collector_name, "error": str(e)}
