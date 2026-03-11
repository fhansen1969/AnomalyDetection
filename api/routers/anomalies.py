"""Anomaly management routes."""
import asyncio
import json
import logging
import traceback
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Query, Body

from api.state import app_state
from api.schemas import AnomalyModel

logger = logging.getLogger("api_services")
router = APIRouter()


@router.get("/anomalies", tags=["Anomalies"], response_model=List[AnomalyModel])
async def list_anomalies(
    model: Optional[str] = Query(None, description="Filter anomalies by model"),
    min_score: float = Query(0.0, description="Minimum anomaly score"),
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity (Critical, High, Medium, Low)"),
    limit: int = Query(5000, description="Maximum number of anomalies to return")
):
    """List detected anomalies with enhanced field validation."""
    if app_state.storage_manager is None:
        logging.warning("Storage manager not initialized, returning empty list")
        return []

    try:
        try:
            filters = {}
            if model:
                filters['model_name'] = model

            anomalies = await asyncio.to_thread(
                app_state.storage_manager.get_anomalies,
                limit=limit,
                filters=filters if filters else None
            )

            if min_score > 0:
                anomalies = [a for a in anomalies if a.get('score', 0) >= min_score]

        except Exception as e:
            logging.error(f"Error loading anomalies from storage: {str(e)}")
            try:
                if hasattr(app_state.storage_manager, 'connect'):
                    await asyncio.to_thread(lambda: app_state.storage_manager.connect())
                    filters = {}
                    if model:
                        filters['model_name'] = model
                    anomalies = await asyncio.to_thread(
                        app_state.storage_manager.get_anomalies,
                        limit=limit,
                        filters=filters if filters else None
                    )
                    if min_score > 0:
                        anomalies = [a for a in anomalies if a.get('score', 0) >= min_score]
                else:
                    anomalies = []
            except Exception:
                anomalies = []

        if not isinstance(anomalies, list):
            anomalies = []

        if status:
            anomalies = [a for a in anomalies if a.get('status') == status]

        if severity:
            anomalies = [a for a in anomalies if a.get('severity', '').lower() == severity.lower()]

        result = []
        for anomaly in anomalies:
            try:
                model_name = anomaly.get("model")
                if not model_name or model_name == "unknown":
                    if "model_type" in anomaly and anomaly["model_type"]:
                        model_name = anomaly["model_type"]
                    else:
                        model_name = f"unnamed_model_{anomaly.get('id', '')[:8]}"

                severity_val = anomaly.get('severity')
                if not severity_val:
                    if isinstance(anomaly.get("analysis"), dict):
                        severity_val = anomaly["analysis"].get("severity")
                    if not severity_val:
                        score = float(anomaly.get("score", 0))
                        if score >= 0.9:
                            severity_val = "Critical"
                        elif score >= 0.8:
                            severity_val = "High"
                        elif score >= 0.6:
                            severity_val = "Medium"
                        else:
                            severity_val = "Low"

                location = anomaly.get("location")
                if not location:
                    original_data = anomaly.get("data", anomaly.get("original_data", {}))
                    if isinstance(original_data, dict):
                        for field in ["location", "host", "hostname", "server"]:
                            if field in original_data and original_data[field]:
                                location = str(original_data[field])
                                break
                    if not location:
                        if anomaly.get("src_ip"):
                            location = f"src-{anomaly['src_ip']}"
                        elif anomaly.get("dst_ip"):
                            location = f"dst-{anomaly['dst_ip']}"
                        else:
                            location = "unknown"

                features = anomaly.get("features", [])
                if not isinstance(features, list):
                    if isinstance(features, dict):
                        features = [{"name": k, "value": v} for k, v in features.items()]
                    else:
                        features = []

                anomaly_id = anomaly.get("id", str(uuid.uuid4()))
                timestamp = anomaly.get("timestamp", datetime.utcnow().isoformat())
                detection_time = anomaly.get("detection_time", timestamp)
                score = float(anomaly.get("score", 0.5))
                threshold = float(anomaly.get("threshold", 0.5))

                analysis = anomaly.get("analysis", {})
                if not analysis:
                    analysis = {"severity": severity_val, "auto_generated": True}
                elif isinstance(analysis, str):
                    analysis = {"content": analysis, "severity": severity_val, "auto_generated": True}
                elif isinstance(analysis, dict) and "severity" not in analysis:
                    analysis["severity"] = severity_val

                anomaly_model = {
                    "id": anomaly_id,
                    "timestamp": timestamp,
                    "detection_time": detection_time,
                    "model": model_name,
                    "model_id": anomaly.get("model_id"),
                    "score": score,
                    "threshold": threshold,
                    "original_data": anomaly.get("data", anomaly.get("original_data", {})),
                    "details": anomaly.get("details", {}),
                    "analysis": analysis,
                    "features": features,
                    "location": location,
                    "src_ip": anomaly.get("src_ip"),
                    "dst_ip": anomaly.get("dst_ip"),
                    "status": anomaly.get("status", "new"),
                    "severity": severity_val,
                    "created_at": anomaly.get("created_at"),
                    "updated_at": anomaly.get("updated_at")
                }
                result.append(anomaly_model)
            except Exception as e:
                logging.error(f"Error processing anomaly: {str(e)}")
                logging.error(traceback.format_exc())
                continue

        return result

    except Exception as e:
        logging.error(f"Error in list_anomalies endpoint: {str(e)}")
        logging.error(traceback.format_exc())
        return []


@router.post("/anomalies/store", tags=["Anomalies"], response_model=Dict[str, Any])
async def store_anomalies_endpoint(
    anomalies: List[Dict[str, Any]] = Body(..., description="Anomalies to store")
):
    """Explicitly store anomalies in the database with validation."""
    if not app_state.storage_manager:
        raise HTTPException(status_code=503, detail="Storage manager not available")

    for anomaly in anomalies:
        if "id" not in anomaly:
            anomaly["id"] = str(uuid.uuid4())
        if "timestamp" not in anomaly:
            anomaly["timestamp"] = datetime.utcnow().isoformat()
        if "detection_time" not in anomaly:
            anomaly["detection_time"] = anomaly["timestamp"]
        if "model" not in anomaly or not anomaly["model"]:
            anomaly["model"] = "manual_entry"
        if "severity" not in anomaly:
            score = anomaly.get("score", 0.5)
            if score >= 0.9:
                anomaly["severity"] = "Critical"
            elif score >= 0.8:
                anomaly["severity"] = "High"
            elif score >= 0.6:
                anomaly["severity"] = "Medium"
            else:
                anomaly["severity"] = "Low"

    try:
        await asyncio.to_thread(lambda: app_state.storage_manager.store_anomalies(anomalies))

        if app_state.alert_manager:
            for anomaly in anomalies:
                if anomaly.get("score", 0) >= app_state.alert_manager.threshold_score:
                    await app_state.alert_manager.send_alert(anomaly)

        return {
            "status": "success",
            "stored_count": len(anomalies),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Error storing anomalies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error storing anomalies: {str(e)}")
