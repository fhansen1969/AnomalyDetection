"""Model management routes and background jobs."""
import asyncio
import json
import logging
import time
import threading
import traceback
from datetime import datetime
from pathlib import Path as PathLib
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Path, Body

from api.state import app_state
from api.schemas import ModelInfo, ModelConfig, DataBatch, JobStatus
from api.helpers import store_detection_results

# Import model classes with try/except
try:
    from anomaly_detection.models.isolation_forest import IsolationForestModel
except ImportError:
    try:
        from anomaly_detection.models.isolation_forest import ImprovedIsolationForestModel as IsolationForestModel
    except ImportError:
        IsolationForestModel = None

try:
    from anomaly_detection.models.statistical import StatisticalModel
except ImportError:
    try:
        from anomaly_detection.models.statistical import ImprovedStatisticalModel as StatisticalModel
    except ImportError:
        StatisticalModel = None

try:
    from anomaly_detection.models.one_class_svm import OneClassSVMModel
except ImportError:
    OneClassSVMModel = None

try:
    from anomaly_detection.models.autoencoder import AutoencoderModel
except ImportError:
    AutoencoderModel = None

try:
    from anomaly_detection.models.ganbased import GANAnomalyDetector
except ImportError:
    GANAnomalyDetector = None

try:
    from anomaly_detection.models.ensemble import EnsembleModel
except ImportError:
    EnsembleModel = None

try:
    from anomaly_detection.processors.normalizer import Normalizer
except ImportError:
    Normalizer = None

try:
    from anomaly_detection.processors.feature_extractor import FeatureExtractor
    # Test if it's an abstract class
    try:
        test_fe = FeatureExtractor("test", {})
    except TypeError:
        from api.extractors import ConcreteFeatureExtractor
        FeatureExtractor = ConcreteFeatureExtractor
except ImportError:
    from api.extractors import ConcreteFeatureExtractor
    FeatureExtractor = ConcreteFeatureExtractor

logger = logging.getLogger("api_services")
router = APIRouter()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/models", tags=["Models"], response_model=List[ModelInfo])
async def list_models():
    """
    List all available models.

    Returns:
        List of model information
    """
    if not app_state.models:
        return []

    result = []
    for name, model in app_state.models.items():
        # Check if model is trained using multiple methods for robustness
        is_trained = False
        if hasattr(model, 'is_trained') and model.is_trained:
            is_trained = True
        elif hasattr(model, 'model') and model.model is not None:
            is_trained = True
        elif hasattr(model, 'model_state') and model.model_state:
            if isinstance(model.model_state, dict) and len(model.model_state) > 0:
                if hasattr(model, 'feature_stats') and model.feature_stats:
                    is_trained = True
                elif 'feature_stats' in model.model_state or 'state' in model.model_state:
                    is_trained = True
                elif model.model_state.get('is_trained', False) or model.model_state.get('trained', False):
                    is_trained = True

        model_info = {
            "id": getattr(model, 'id', None),
            "name": name,
            "type": model.__class__.__name__,
            "status": "trained" if is_trained else "not_trained",
            "config": model.config,
            "performance": getattr(model, 'performance', {}),
            "training_time": getattr(model, 'training_time', None),
            "sample_count": len(app_state.last_training_data.get(name, [])),
            "created_at": getattr(model, 'created_at', datetime.utcnow().isoformat()),
            "updated_at": getattr(model, 'updated_at', datetime.utcnow().isoformat())
        }
        result.append(model_info)

    return result


@router.delete("/models/{model_name}", tags=["Models"], response_model=Dict[str, Any])
async def delete_model(model_name: str = Path(..., description="Name of the model to delete")):
    """
    Delete a model.

    Args:
        model_name: Name of the model to delete

    Returns:
        Deletion status
    """
    if model_name not in app_state.models:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")

    try:
        # Remove from models dictionary
        del app_state.models[model_name]

        # Remove from storage if available
        if app_state.storage_manager:
            # TODO: Implement model deletion in storage manager
            pass

        return {
            "status": "success",
            "model_name": model_name,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Error deleting model {model_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting model: {str(e)}")


@router.post("/models/{model_name}/train", tags=["Models"], response_model=JobStatus)
async def train_model(
    background_tasks: BackgroundTasks,
    model_name: str = Path(..., description="Name of the model to train"),
    data_batch: DataBatch = Body(..., description="Batch of data items for training")
):
    """
    Train a model with the provided data.

    Args:
        background_tasks: FastAPI background tasks
        model_name: Name of the model to train
        data_batch: Batch of data items for training

    Returns:
        Job status information
    """
    logger.info(f"[DEBUG] ==================== TRAIN REQUEST ====================")
    logger.info(f"[DEBUG] Model: {model_name}")
    logger.info(f"[DEBUG] Data batch items: {len(data_batch.items)}")
    logger.info(f"[DEBUG] Available models: {list(app_state.models.keys())}")
    logger.info(f"[DEBUG] Background tasks: {background_tasks}")

    if model_name not in app_state.models:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")

    # Create a job ID
    job_id = f"train_{model_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.utcnow().isoformat()

    # Initialize job status
    app_state.background_jobs[job_id] = {
        "job_id": job_id,
        "job_type": "train_model",
        "status": "pending",
        "start_time": current_time,
        "end_time": None,
        "parameters": {"model_name": model_name, "data_count": len(data_batch.items)},
        "result": None,
        "progress": 0.0,
        "created_at": current_time,
        "updated_at": current_time
    }

    # Start training job in background
    background_tasks.add_task(train_model_job, model_name, data_batch.items, job_id)

    return app_state.background_jobs[job_id]


@router.post("/models/create", tags=["Models"], response_model=Dict[str, Any])
async def create_model(
    model_config: ModelConfig = Body(..., description="Model configuration")
):
    """
    Create a new model with the specified configuration.

    Args:
        model_config: Model configuration

    Returns:
        Creation status
    """
    if app_state.config is None:
        raise HTTPException(status_code=404, detail="System not initialized")

    model_type = model_config.type
    model_config_dict = model_config.config

    # Generate a unique model name
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    model_name = f"{model_type}_model_{timestamp}"

    # Create the model
    try:
        model_class_map = {
            "isolation_forest": IsolationForestModel,
            "one_class_svm": OneClassSVMModel,
            "autoencoder": AutoencoderModel,
            "gan": GANAnomalyDetector,
            "statistical": StatisticalModel,
            "ensemble": EnsembleModel,
        }

        if model_type not in model_class_map:
            raise HTTPException(status_code=400, detail=f"Unsupported model type: {model_type}")

        model_cls = model_class_map[model_type]
        if model_cls is None:
            raise HTTPException(status_code=400, detail=f"{model_type} model class not available (import failed)")

        app_state.models[model_name] = model_cls(model_name, model_config_dict)

        logging.info(f"Created new model: {model_name} of type {model_type}")

        return {
            "status": "success",
            "model_name": model_name,
            "model_type": model_type,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Error creating model: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating model: {str(e)}")


@router.post("/models/load-from-storage", tags=["Models"], response_model=Dict[str, Any])
async def load_models_from_storage():
    """
    Load all saved models from the storage/models directory.

    Returns:
        Status of loaded models
    """
    models_dir = PathLib("storage/models")
    loaded_models = []
    failed_models = []

    if not models_dir.exists():
        return {
            "status": "warning",
            "message": "Models directory does not exist",
            "loaded": [],
            "failed": []
        }

    # Find all model files
    model_files = list(models_dir.glob("*.pkl")) + list(models_dir.glob("*.joblib")) + list(models_dir.glob("*.json"))

    for model_file in model_files:
        try:
            model_name = model_file.stem

            # Determine model type from filename
            model_type = None
            for mtype in ["isolation_forest", "one_class_svm", "autoencoder", "gan", "statistical", "ensemble"]:
                if mtype in model_name.lower():
                    model_type = mtype
                    break

            if not model_type:
                # Try to load metadata
                metadata_file = models_dir / f"{model_name}_metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        model_type = metadata.get("type", "unknown")

            # Load the model
            if app_state.storage_manager:
                model_state = await asyncio.to_thread(app_state.storage_manager.load_model, model_name)

                if model_state:
                    # Create model instance based on type
                    if model_type == "isolation_forest":
                        if IsolationForestModel is None:
                            logging.warning(f"IsolationForestModel not available, skipping {model_name}")
                            continue
                        model = IsolationForestModel(model_name, {})
                    elif model_type == "one_class_svm":
                        model = OneClassSVMModel(model_name, {})
                    elif model_type == "autoencoder":
                        model = AutoencoderModel(model_name, {})
                    elif model_type == "gan":
                        model = GANAnomalyDetector(model_name, {})
                    elif model_type == "statistical":
                        if StatisticalModel is None:
                            logging.warning(f"StatisticalModel not available, skipping {model_name}")
                            continue
                        model = StatisticalModel(model_name, {})
                    elif model_type == "ensemble":
                        model = EnsembleModel(model_name, {})
                    else:
                        logging.warning(f"Unknown model type for {model_name}")
                        continue

                    # Set the loaded state
                    model.set_state(model_state)
                    app_state.models[model_name] = model
                    loaded_models.append({
                        "name": model_name,
                        "type": model_type,
                        "file": str(model_file)
                    })
                    logging.info(f"Loaded model {model_name} from storage")
            else:
                # Direct file loading if storage manager not available
                import joblib
                import pickle

                if model_file.suffix == '.joblib':
                    model_obj = joblib.load(model_file)
                elif model_file.suffix == '.pkl':
                    with open(model_file, 'rb') as f:
                        model_obj = pickle.load(f)
                else:
                    continue

                # Wrap the loaded model
                if model_type and model_type != "unknown":
                    loaded_models.append({
                        "name": model_name,
                        "type": model_type,
                        "file": str(model_file)
                    })

        except Exception as e:
            logging.error(f"Failed to load model {model_file}: {str(e)}")
            failed_models.append({
                "file": str(model_file),
                "error": str(e)
            })

    return {
        "status": "success",
        "loaded": loaded_models,
        "failed": failed_models,
        "total_loaded": len(loaded_models),
        "total_failed": len(failed_models)
    }


@router.get("/models/saved-files", tags=["Models"], response_model=Dict[str, Any])
async def list_saved_model_files():
    """
    List all saved model files in the storage directory.

    Returns:
        List of saved model files
    """
    models_dir = PathLib("storage/models")

    if not models_dir.exists():
        return {
            "status": "warning",
            "message": "Models directory does not exist",
            "files": []
        }

    model_files = []

    # Find all potential model files
    for ext in ['*.pkl', '*.joblib', '*.json', '*.h5', '*.pt', '*.pth']:
        for file_path in models_dir.glob(ext):
            file_info = {
                "name": file_path.name,
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                "type": file_path.suffix[1:],
                "path": str(file_path)
            }

            # Try to get metadata
            metadata_file = models_dir / f"{file_path.stem}_metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        file_info["metadata"] = metadata
                except Exception:
                    pass

            model_files.append(file_info)

    return {
        "status": "success",
        "files": model_files,
        "total": len(model_files),
        "directory": str(models_dir)
    }


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------

async def train_model_job(model_name: str, data: List[Dict[str, Any]], job_id: str):
    """
    Background job for training a model - ENHANCED WITH DEBUG LOGGING.

    Args:
        model_name: Name of the model to train
        data: Training data
        job_id: ID of the job
    """
    logger.info(f"[DEBUG] ==================== TRAIN JOB START ====================")
    logger.info(f"[DEBUG] Job ID: {job_id}")
    logger.info(f"[DEBUG] Model: {model_name}")
    logger.info(f"[DEBUG] Data samples: {len(data)}")
    logger.info(f"[DEBUG] Thread: {threading.current_thread().name}")

    try:
        logger.info(f"[DEBUG] Updating job status to 'running'")
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "running"
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        logger.info(f"[DEBUG] Job status updated")

        # Get the model
        logger.info(f"[DEBUG] Getting model instance")
        if model_name not in app_state.models:
            raise ValueError(f"Model {model_name} not found. Available: {list(app_state.models.keys())}")

        model = app_state.models[model_name]
        logger.info(f"[DEBUG] Model type: {type(model).__name__}")

        # Save training data for future reference
        app_state.last_training_data[model_name] = data
        logger.info(f"[DEBUG] Saved training data reference")

        # Normalize and extract features from data
        logger.info(f"[DEBUG] Processing data...")
        processed_data = data

        # Apply normalizers
        normalizer_count = 0
        for processor_name, processor in app_state.processors.items():
            if Normalizer and isinstance(processor, Normalizer):
                processed_data = processor.process(processed_data)
                normalizer_count += 1
                logger.info(f"[DEBUG] Applied normalizer {processor_name}")
        logger.info(f"[DEBUG] Applied {normalizer_count} normalizers")

        # Apply feature extractors
        feature_extractor_count = 0
        for processor_name, processor in app_state.processors.items():
            if isinstance(processor, FeatureExtractor):
                processed_data = processor.process(processed_data)
                feature_extractor_count += 1
                logger.info(f"[DEBUG] Applied feature extractor {processor_name}")
        logger.info(f"[DEBUG] Applied {feature_extractor_count} feature extractors")

        # Update progress
        logger.info(f"[DEBUG] Updating progress to 50%")
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["progress"] = 0.5
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        # Train the model (with timing)
        logger.info(f"[DEBUG] Starting model training...")
        start_time = time.time()

        try:
            model.train(processed_data)
            training_time = time.time() - start_time
            logger.info(f"[DEBUG] Training completed in {training_time:.2f} seconds")
        except Exception as train_error:
            logger.error(f"[DEBUG] Training failed: {type(train_error).__name__}: {str(train_error)}")
            raise

        # Save model state
        logger.info(f"[DEBUG] Saving model state...")
        if app_state.storage_manager:
            try:
                await asyncio.to_thread(lambda: app_state.storage_manager.save_model(model))
                logger.info(f"[DEBUG] Model state saved via storage_manager")
            except Exception as e:
                logger.error(f"[DEBUG] Storage manager save failed: {e}")

        # ============================================================
        # EMERGENCY FIX: Manually save model files to disk
        # ============================================================
        logger.info(f"[DEBUG] Starting emergency model save...")
        try:
            import pickle
            import joblib
            from pathlib import Path as _Path

            models_dir = _Path("storage/models")
            models_dir.mkdir(parents=True, exist_ok=True)

            # Save underlying sklearn model using joblib (if exists)
            if hasattr(model, 'model') and model.model is not None:
                joblib_file = models_dir / f"{model_name}.joblib"
                joblib.dump(model.model, joblib_file)
                file_size_kb = joblib_file.stat().st_size / 1024
                logger.info(f"[DEBUG] [FIX] Saved underlying model: {joblib_file.name} ({file_size_kb:.2f} KB)")
            else:
                logger.info(f"[DEBUG] [FIX] Model has no underlying sklearn model to save with joblib")

            # Save complete model using pickle
            pkl_file = models_dir / f"{model_name}.pkl"
            with open(pkl_file, 'wb') as f:
                pickle.dump(model, f)
            file_size_kb = pkl_file.stat().st_size / 1024
            logger.info(f"[DEBUG] [FIX] Saved complete model: {pkl_file.name} ({file_size_kb:.2f} KB)")

            # Verify file size
            if file_size_kb < 1:
                logger.error(f"[DEBUG] [FIX] WARNING: Model file is suspiciously small ({file_size_kb:.2f} KB)")
            else:
                logger.info(f"[DEBUG] [FIX] Model file size looks good")

            # Save metadata
            metadata_file = models_dir / f"{model_name}_metadata.json"
            metadata = {
                'name': model_name,
                'type': getattr(model, 'type', type(model).__name__),
                'status': 'trained',
                'trained': True,
                'emergency_save': True,
                'emergency_save_timestamp': datetime.utcnow().isoformat(),
                'training_time_seconds': round(training_time, 2),
                'samples_trained': len(data),
                'file_size_kb': round(file_size_kb, 2),
                'files': {
                    'pkl': str(pkl_file.name),
                    'joblib': f"{model_name}.joblib" if hasattr(model, 'model') and model.model is not None else None,
                    'metadata': str(metadata_file.name)
                }
            }

            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"[DEBUG] [FIX] Metadata saved: {metadata_file.name}")

            # Verify files
            if pkl_file.exists():
                logger.info(f"[DEBUG] [FIX] SUCCESS: Model {model_name} saved to disk")
            else:
                logger.error(f"[DEBUG] [FIX] FAILED: Model file not created")

        except Exception as e:
            logger.error(f"[DEBUG] [FIX] Emergency save failed: {type(e).__name__}: {str(e)}")
            logger.error(f"[DEBUG] Traceback: {traceback.format_exc()}")
        # ============================================================

        # Update job status to completed
        logger.info(f"[DEBUG] Updating job to completed")
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "completed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {
                "model": model_name,
                "samples_trained": len(data),
                "training_time": round(training_time, 2),
                "status": "success"
            }

        logger.info(f"[DEBUG] ==================== TRAIN JOB SUCCESS ====================")

        # Store job results in database
        await store_detection_results(job_id, app_state.background_jobs[job_id]["result"])

    except Exception as e:
        logger.error(f"[DEBUG] ==================== TRAIN JOB FAILED ====================")
        logger.error(f"[DEBUG] Exception: {type(e).__name__}: {str(e)}")
        logger.error(f"[DEBUG] Full traceback:", exc_info=True)

        # Update job status to failed
        with app_state.background_jobs_lock:
            if job_id in app_state.background_jobs:
                app_state.background_jobs[job_id]["status"] = "failed"
                app_state.background_jobs[job_id]["end_time"] = datetime.utcnow().isoformat()
                app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
                app_state.background_jobs[job_id]["error"] = str(e)
                app_state.background_jobs[job_id]["error_type"] = type(e).__name__

        raise
