"""
Pydantic request/response models for the API.
Extracted from api_services.py lines 534-778.
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class ConfigModel(BaseModel):
    """Configuration model."""
    config_path: str = Field(..., description="Path to configuration file")
    auto_init: bool = Field(False, description="Automatically initialize system")


class AnomalyModel(BaseModel):
    """Anomaly model for detection results."""
    id: str
    timestamp: str
    detection_time: str
    model: str
    model_id: Optional[int] = None
    model_type: Optional[str] = None
    model_version: Optional[str] = None
    score: float
    threshold: float = 0.5
    original_data: Dict[str, Any]
    details: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    features: Optional[List[Any]] = Field(default_factory=list)
    location: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    status: str = "new"
    severity: Optional[str] = None
    # Calibration fields — populated by ScoreCalibrator after detection.
    # Coexist with `severity` (raw-score-derived); these are probability-based.
    ecdf_rank: Optional[float] = None
    calibrated_prob: Optional[float] = None
    severity_tier: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    top_features: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "timestamp": "2025-05-10T10:15:30Z",
                "detection_time": "2025-05-10T10:15:40Z",
                "model": "isolation_forest_model",
                "score": 0.92,
                "threshold": 0.7,
                "original_data": {"cpu_usage": 95, "memory_usage": 85},
                "details": {"anomaly_reason": "CPU usage exceeds normal pattern"},
                "features": [],
                "severity": "High",
                "status": "new",
                "top_features": [
                    {"name": "cpu_usage", "contribution": 0.42},
                    {"name": "memory_usage", "contribution": 0.31}
                ]
            }
        }
    )


class CorrelationRequest(BaseModel):
    """Request for anomaly correlation analysis."""
    anomaly_id: str = Field(..., description="ID of the anomaly to analyze correlations for")
    time_window_hours: Optional[int] = Field(24, description="Time window in hours to search for correlations")
    min_correlation_score: Optional[float] = Field(0.3, description="Minimum correlation score to include")
    max_results: Optional[int] = Field(50, description="Maximum number of correlated anomalies to return")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "anomaly_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "time_window_hours": 24,
                "min_correlation_score": 0.3,
                "max_results": 50
            }
        }
    )


class CorrelationResponse(BaseModel):
    """Response for anomaly correlation analysis."""
    target_anomaly: AnomalyModel
    correlations: List[Dict[str, Any]]
    statistics: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_anomaly": {
                    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "timestamp": "2025-05-10T10:15:30Z",
                    "model": "isolation_forest_model",
                    "score": 0.92
                },
                "correlations": [
                    {
                        "anomaly": {"id": "abc123", "score": 0.85},
                        "correlation_score": 0.75,
                        "reasons": ["Same source IP", "Time proximity"]
                    }
                ],
                "statistics": {
                    "total_correlations": 10,
                    "high_correlations": 3,
                    "average_correlation": 0.65
                }
            }
        }
    )


class BulkCorrelationRequest(BaseModel):
    """Request for bulk anomaly correlation analysis."""
    anomaly_ids: List[str] = Field(..., description="List of anomaly IDs to analyze")
    cross_correlate: bool = Field(False, description="Whether to cross-correlate between provided anomalies")
    time_window_hours: Optional[int] = Field(24, description="Time window in hours")
    min_correlation_score: Optional[float] = Field(0.3, description="Minimum correlation score")


class CorrelationMatrixRequest(BaseModel):
    """Request for correlation matrix generation."""
    anomaly_ids: List[str] = Field(..., description="List of anomaly IDs for matrix", min_length=2, max_length=50)
    include_metadata: bool = Field(True, description="Include anomaly metadata in response")


class DataItem(BaseModel):
    """Data item for detection or training."""
    data: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": {
                    "timestamp": "2025-05-10T10:15:30Z",
                    "cpu_usage": 95,
                    "memory_usage": 85,
                    "network_in": 50000,
                    "network_out": 20000
                }
            }
        }
    )


class DataBatch(BaseModel):
    """Batch of data items for detection or training."""
    items: List[Dict[str, Any]]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "timestamp": "2025-05-10T10:15:30Z",
                        "cpu_usage": 95,
                        "memory_usage": 85,
                        "network_in": 50000,
                        "network_out": 20000
                    },
                    {
                        "timestamp": "2025-05-10T10:16:30Z",
                        "cpu_usage": 97,
                        "memory_usage": 90,
                        "network_in": 60000,
                        "network_out": 25000
                    }
                ]
            }
        }
    )


class ModelConfig(BaseModel):
    """Configuration for a model."""
    type: str
    config: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "isolation_forest",
                "config": {
                    "n_estimators": 100,
                    "contamination": 0.05,
                    "random_state": 42
                }
            }
        }
    )


class ModelInfo(BaseModel):
    """Information about a trained model."""
    id: Optional[int] = None
    name: str
    type: str
    status: str
    config: Dict[str, Any]
    performance: Optional[Dict[str, Any]] = None
    training_time: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    sample_count: Optional[int] = None


class JobStatus(BaseModel):
    """Status of a background job."""
    job_id: str
    job_type: str
    status: str
    start_time: str
    end_time: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    progress: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AlertConfig(BaseModel):
    """Alert configuration."""
    enabled: bool = True
    threshold_score: float = 0.8
    email: Optional[Dict[str, Any]] = None
    webhook: Optional[Dict[str, Any]] = None
    file: Optional[Dict[str, Any]] = None
    channels: List[str] = ["console"]


class DetectionRequest(BaseModel):
    """Request for anomaly detection."""
    model_name: str
    data: List[Dict[str, Any]]
    threshold: Optional[float] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model_name": "isolation_forest_model",
                "data": [
                    {
                        "timestamp": "2025-05-10T10:15:30Z",
                        "cpu_usage": 95,
                        "memory_usage": 85,
                        "network_in": 50000,
                        "network_out": 20000
                    }
                ],
                "threshold": 0.75
            }
        }
    )


class BulkDetectionRequest(BaseModel):
    """Request for bulk anomaly detection across multiple models."""
    models: List[str]
    data: List[Dict[str, Any]]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "models": ["isolation_forest_model", "statistical_model"],
                "data": [
                    {
                        "timestamp": "2025-05-10T10:15:30Z",
                        "cpu_usage": 95,
                        "memory_usage": 85
                    }
                ]
            }
        }
    )
