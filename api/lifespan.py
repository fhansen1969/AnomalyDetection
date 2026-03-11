"""
Lifespan context manager for FastAPI startup/shutdown.
Contains initialize_system(), _init_database_sync(), and sync_jobs_to_database().
Extracted from api_services.py.
"""
import asyncio
import json
import logging
import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path as PathLib
from typing import Dict, List, Any

from fastapi import FastAPI

from api.state import app_state
from api.helpers import load_config

logger = logging.getLogger("api_services")

# ---------------------------------------------------------------------------
# Module-level imports with fallbacks (mirrored from api_services.py)
# ---------------------------------------------------------------------------
try:
    from anomaly_detection.storage.storage_manager import StorageManager
except ImportError:
    StorageManager = None

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

# FeatureExtractor with ConcreteFeatureExtractor fallback
try:
    from anomaly_detection.processors.feature_extractor import FeatureExtractor
    try:
        test_fe = FeatureExtractor("test", {})
    except TypeError:
        logger.warning("FeatureExtractor is abstract, using ConcreteFeatureExtractor")
        from api.extractors import ConcreteFeatureExtractor
        FeatureExtractor = ConcreteFeatureExtractor
except ImportError:
    logger.warning("Could not import FeatureExtractor, using ConcreteFeatureExtractor")
    from api.extractors import ConcreteFeatureExtractor
    FeatureExtractor = ConcreteFeatureExtractor

try:
    from anomaly_detection.collectors.file_collector import FileCollector
except ImportError:
    FileCollector = None

try:
    from anomaly_detection.collectors.kafka_collector import KafkaCollector
except ImportError:
    KafkaCollector = None

try:
    from anomaly_detection.collectors.sql_collector import SQLCollector
except ImportError:
    SQLCollector = None

try:
    from anomaly_detection.collectors.rest_api_collector import RestApiCollector
except ImportError:
    RestApiCollector = None

try:
    from anomaly_detection.agents.agent_manager import AgentManager
except ImportError:
    AgentManager = None


# ---------------------------------------------------------------------------
# System initialization
# ---------------------------------------------------------------------------

def initialize_system(config_dict: Dict[str, Any]):
    """
    Initialize system components based on configuration.
    Writes results to app_state instead of globals.

    Args:
        config_dict: Configuration dictionary
    """
    app_state.config = config_dict

    # Initialize storage manager
    try:
        storage_config = config_dict.get("database", {})
        if StorageManager:
            app_state.storage_manager = StorageManager(storage_config)
            logging.info("Storage manager initialized (connection deferred to async startup)")
        else:
            logging.warning("StorageManager not available")
            app_state.storage_manager = None
    except Exception as e:
        logging.error(f"Error initializing storage manager: {str(e)}")
        app_state.storage_manager = None

    # Initialize models
    models_config = config_dict.get("models", {})
    enabled_models = models_config.get("enabled", [])

    model_classes = {
        "isolation_forest": IsolationForestModel,
        "one_class_svm": OneClassSVMModel,
        "autoencoder": AutoencoderModel,
        "gan": GANAnomalyDetector,
        "ensemble": EnsembleModel,
        "statistical": StatisticalModel,
    }

    for model_type in enabled_models:
        if model_type in models_config:
            model_config = models_config[model_type]
            model_name = f"{model_type}_model"
            model_cls = model_classes.get(model_type)

            try:
                if model_cls is None:
                    raise ImportError(f"{model_type} model class not available")
                app_state.models[model_name] = model_cls(model_name, model_config)

                # Try to load saved model state
                if app_state.storage_manager:
                    model_state_data = app_state.storage_manager.load_model(model_name)
                    if model_state_data:
                        if isinstance(model_state_data, dict):
                            app_state.models[model_name].set_state(model_state_data)
                            logging.info(f"Loaded model state for {model_name}")
                        elif hasattr(model_state_data, 'model_state'):
                            # load_model returned a full model object, use it directly
                            app_state.models[model_name] = model_state_data
                            logging.info(f"Loaded model object for {model_name}")
            except Exception as e:
                logging.error(f"Error initializing model {model_type}: {str(e)}")

    # Auto-load saved models from storage/models directory
    try:
        models_dir = PathLib("storage/models")
        if models_dir.exists():
            logging.info("Checking for additional saved models in storage/models...")
            model_files = list(models_dir.glob("*.pkl")) + list(models_dir.glob("*.joblib"))

            for model_file in model_files:
                model_name = model_file.stem
                if model_name in app_state.models:
                    logging.info(f"Model {model_name} already loaded, skipping")
                    continue

                try:
                    model_type = None
                    for mtype in ["isolation_forest", "one_class_svm", "autoencoder", "gan", "statistical", "ensemble"]:
                        if mtype in model_name.lower():
                            model_type = mtype
                            break

                    # Check for metadata file
                    metadata_file = models_dir / f"{model_name}_metadata.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            model_type = metadata.get("type", model_type)

                    if model_type:
                        model_cls = model_classes.get(model_type)
                        if model_cls is None:
                            logging.warning(f"{model_type} model class not available, skipping {model_name}")
                            continue

                        model = model_cls(model_name, models_config.get(model_type, {}))

                        if app_state.storage_manager:
                            model_state_data = app_state.storage_manager.load_model(model_name)
                            if model_state_data:
                                model.set_state(model_state_data)
                                app_state.models[model_name] = model
                                logging.info(f"Auto-loaded saved model: {model_name} (type: {model_type})")
                        else:
                            # Try direct file loading
                            import joblib
                            import pickle

                            try:
                                if model_file.suffix == '.joblib':
                                    model_obj = joblib.load(model_file)
                                    model.model = model_obj
                                    model.is_trained = True
                                    if not model.model_state:
                                        model.model_state = {"loaded_from_file": True}
                                    app_state.models[model_name] = model
                                    logging.info(f"Auto-loaded saved model from file: {model_name} (type: {model_type})")
                                elif model_file.suffix == '.pkl':
                                    with open(model_file, 'rb') as f:
                                        model_obj = pickle.load(f)

                                    if hasattr(model_obj, 'is_trained') and hasattr(model_obj, 'model_state'):
                                        app_state.models[model_name] = model_obj
                                        logging.info(f"Auto-loaded complete model from pickle: {model_name}")
                                    else:
                                        model.model = model_obj
                                        model.is_trained = True
                                        if not model.model_state:
                                            model.model_state = {"loaded_from_file": True}
                                        app_state.models[model_name] = model
                                        logging.info(f"Auto-loaded saved model from file: {model_name}")
                            except Exception as e:
                                logging.error(f"Failed to load model file {model_file}: {str(e)}")
                                logging.error(traceback.format_exc())
                    else:
                        logging.warning(f"Could not determine model type for {model_name}")

                except Exception as e:
                    logging.error(f"Failed to auto-load model {model_name}: {str(e)}")
                    logging.error(traceback.format_exc())

            logging.info(f"Auto-loading complete. Total models loaded: {len(app_state.models)}")
    except Exception as e:
        logging.error(f"Error auto-loading saved models: {str(e)}")
        logging.error(traceback.format_exc())

    # Initialize processors
    processors_config = config_dict.get("processors", {})
    normalizers_config = processors_config.get("normalizers", [])
    feature_extractors_config = processors_config.get("feature_extractors", [])

    for norm_config in normalizers_config:
        name = norm_config.get("name", "generic_normalizer")
        try:
            if Normalizer:
                app_state.processors[name] = Normalizer(name, norm_config, app_state.storage_manager)
            else:
                logging.warning(f"Normalizer class not available, skipping {name}")
        except Exception as e:
            logging.error(f"Error initializing normalizer {name}: {str(e)}")

    for feat_config in feature_extractors_config:
        name = feat_config.get("name", "basic_features")
        try:
            app_state.processors[name] = FeatureExtractor(name, feat_config, app_state.storage_manager)
            logging.info(f"Successfully initialized feature extractor: {name}")
        except Exception as e:
            logging.error(f"Error initializing feature extractor {name}: {str(e)}")
            logging.error(traceback.format_exc())

    # Initialize collectors
    collectors_config = config_dict.get("collectors", {})
    enabled_collectors = collectors_config.get("enabled", [])
    logging.info(f"Collectors config: {collectors_config}")
    logging.info(f"Enabled collectors: {enabled_collectors}")

    collector_classes = {
        "file": FileCollector,
        "kafka": KafkaCollector,
        "sql": SQLCollector,
        "rest_api": RestApiCollector,
    }

    for collector_type in enabled_collectors:
        if collector_type in collectors_config:
            collector_config = collectors_config[collector_type]
            collector_name = f"{collector_type}_collector"

            try:
                logging.info(f"Initializing collector: {collector_name} of type {collector_type}")
                collector_cls = collector_classes.get(collector_type)
                if collector_cls is None:
                    logging.warning(f"Unknown or unavailable collector type: {collector_type}")
                    continue
                app_state.collectors[collector_name] = collector_cls(
                    collector_name, collector_config, app_state.storage_manager
                )
                logging.info(f"Created {collector_type} collector: {collector_name}")
            except Exception as e:
                logging.error(f"Error initializing collector {collector_type}: {str(e)}")
                logging.error(traceback.format_exc())

    logging.info(f"Available collectors after initialization: {list(app_state.collectors.keys())}")

    # Initialize agent manager
    agents_config = config_dict.get("agents", {})
    logging.info(f"Agent configuration: enabled={agents_config.get('enabled', False)}")
    if agents_config.get("enabled", False) and AgentManager:
        try:
            mode = "enhanced"
            logging.info(f"Initializing AgentManager with mode: {mode}")
            app_state.agent_manager = AgentManager(agents_config, app_state.storage_manager, visualizer=None, mode=mode)
            logging.info("Initialized agent manager in enhanced mode")
        except Exception as e:
            logging.error(f"Error initializing agent manager: {str(e)}")
            logging.error(traceback.format_exc())
            app_state.agent_manager = None

    # Initialize alert manager
    alerts_config = config_dict.get("alerts", {})
    if alerts_config.get("enabled", False):
        try:
            from api.routers.alerts import AlertManager
            app_state.alert_manager = AlertManager(alerts_config)
            logging.info("Initialized alert manager")
        except Exception as e:
            logging.error(f"Error initializing alert manager: {str(e)}")
            app_state.alert_manager = None

    logging.info("System initialization completed")
    logging.info(
        f"Initialized components: {len(app_state.models)} models, "
        f"{len(app_state.processors)} processors, "
        f"{len(app_state.collectors)} collectors"
    )


def _init_database_sync():
    """
    Synchronous helper to initialize database connection and tables.
    Runs in thread executor during async startup to avoid mutex deadlock.
    """
    if not app_state.storage_manager:
        return

    try:
        if hasattr(app_state.storage_manager, 'initialize_connection_pool'):
            if app_state.storage_manager.initialize_connection_pool():
                logging.info("Connection pool initialized successfully")
            else:
                logging.error("Connection pool initialization failed")
                return
        else:
            logging.warning("Using legacy initialization method")
            if hasattr(app_state.storage_manager, 'connect'):
                app_state.storage_manager.connect()
                logging.info("Storage manager connected")

        if hasattr(app_state.storage_manager, 'create_tables'):
            app_state.storage_manager.create_tables()
            logging.info("Database tables verified/created")

        if hasattr(app_state.storage_manager, 'check_connection'):
            if app_state.storage_manager.check_connection():
                logging.info("Database connection verified")
            else:
                logging.warning("Database connection check failed")
    except Exception as e:
        logging.error(f"Database initialization failed: {str(e)}")
        logging.error(traceback.format_exc())
        raise


def _sync_job_to_db_sync(job_id: str, job_data: Dict[str, Any]):
    """
    Synchronous helper to sync a single job to database.
    Runs in thread executor to avoid blocking the async event loop.
    """
    try:
        import psycopg2.extras
    except ImportError:
        logging.error("psycopg2 not available for job sync")
        return

    try:
        prepared_result = app_state.storage_manager._prepare_for_json_field(job_data.get("result", {}))

        with app_state.storage_manager.get_connection() as conn:
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO jobs (job_id, job_type, status, progress, result, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (job_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        progress = EXCLUDED.progress,
                        result = EXCLUDED.result,
                        updated_at = EXCLUDED.updated_at
                """, (
                    job_id,
                    job_data.get("job_type", "unknown"),
                    job_data["status"],
                    job_data.get("progress", 1.0),
                    psycopg2.extras.Json(prepared_result),
                    job_data.get("created_at", datetime.utcnow().isoformat()),
                    job_data.get("updated_at", datetime.utcnow().isoformat())
                ))
                conn.commit()
                logging.debug(f"Successfully synced job {job_id} to database")
    except Exception as e:
        logging.error(f"Error syncing job {job_id} to database: {str(e)}")
        logging.error(traceback.format_exc())


async def sync_jobs_to_database():
    """
    Periodically sync in-memory jobs to database for persistence.
    Runs synchronous database operations in thread executor to avoid mutex deadlock.
    """
    if not app_state.storage_manager:
        logging.warning("Storage manager not initialized, job sync disabled")
        return

    logging.info("Job sync background task started")
    logging.info("Waiting for initial system stabilization...")
    await asyncio.sleep(5)
    logging.info("Starting periodic job synchronization")

    while True:
        try:
            with app_state.background_jobs_lock:
                jobs_to_sync = [
                    (job_id, job_data.copy())
                    for job_id, job_data in app_state.background_jobs.items()
                    if job_data.get("status") in ["completed", "failed"]
                ]

            for job_id, job_data in jobs_to_sync:
                try:
                    await asyncio.to_thread(_sync_job_to_db_sync, job_id, job_data)
                except Exception as e:
                    logging.error(f"Failed to sync job {job_id}: {str(e)}")

            if jobs_to_sync:
                logging.info(f"Synced {len(jobs_to_sync)} jobs to database")

        except Exception as e:
            logging.error(f"Error in job sync loop: {str(e)}")
            logging.error(traceback.format_exc())

        await asyncio.sleep(30)


# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler — startup and shutdown."""
    logger.info("Server starting up in async context...")

    # Fallback: Load config if not already loaded (handles uvicorn reload mode)
    if app_state.config is None:
        try:
            config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")
            if os.path.exists(config_path):
                logger.info(f"Loading configuration from {config_path} (fallback)")
                app_state.config = load_config(config_path)
            else:
                logger.warning(f"Config file not found at {config_path}, checking alternate paths")
                for alt_path in ["config.yaml", "../config/config.yaml", "/mnt/user-data/uploads/config.yaml"]:
                    if os.path.exists(alt_path):
                        logger.info(f"Loading configuration from {alt_path} (fallback)")
                        app_state.config = load_config(alt_path)
                        break
        except Exception as e:
            logger.error(f"Failed to load config in lifespan: {str(e)}")

    if app_state.config:
        logger.info("Initializing system components in async context...")
        try:
            await asyncio.to_thread(initialize_system, app_state.config)
            logger.info("System components initialized successfully")
        except Exception as e:
            logger.error(f"System initialization failed: {str(e)}")
            logger.error(traceback.format_exc())
            logger.warning("Server will continue with limited functionality")
    else:
        logger.warning("No configuration available, skipping system initialization")

    # Initialize database connection pool in async context
    if app_state.storage_manager:
        logger.info("Initializing database connection pool...")
        try:
            await asyncio.to_thread(_init_database_sync)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            logger.warning("Server will continue with limited database functionality")
    else:
        logger.warning("Storage manager not available, database functionality disabled")

    # Wait a moment for everything to stabilize
    await asyncio.sleep(1)

    # Start background tasks
    logger.info("Starting background job sync task...")
    sync_task = asyncio.create_task(sync_jobs_to_database())

    # Yield control to FastAPI
    yield

    # Shutdown code
    logger.info("Server shutting down...")

    # Cancel background tasks
    sync_task.cancel()

    # Close any open WebSocket connections (snapshot to avoid dict-changed-size error)
    for client_id, websocket in list(app_state.websocket_connections.items()):
        try:
            await websocket.close()
        except Exception:
            pass

    # Close database connections
    if app_state.storage_manager:
        await asyncio.to_thread(lambda: app_state.storage_manager.close())
