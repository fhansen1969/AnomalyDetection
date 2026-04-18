"""Triage API router — entity-grouped anomaly views and analyst feedback."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi import Body
from pydantic import BaseModel, Field

from api.state import app_state

logger = logging.getLogger("api_services")
router = APIRouter()

# Default reason codes; overridden by config triage.reason_codes if present.
_DEFAULT_REASON_CODES = [
    "true_threat",
    "expected_behavior",
    "stale_data",
    "known_false_positive",
    "investigating",
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FeedbackPayload(BaseModel):
    status: str = Field(..., description="Analyst verdict: 'TP' or 'FP'")
    reason_code: str = Field(..., description="Short reason code (see /triage/reason-codes)")
    notes: Optional[str] = Field(None, description="Free-text analyst notes")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _reason_codes() -> List[str]:
    try:
        cfg = app_state.config or {}
        return cfg.get("triage", {}).get("reason_codes", _DEFAULT_REASON_CODES)
    except Exception:
        return _DEFAULT_REASON_CODES


def _load_anomalies(limit: int) -> List[Dict[str, Any]]:
    if app_state.storage_manager is None:
        return []
    try:
        return app_state.storage_manager.get_anomalies(limit=limit) or []
    except Exception as exc:
        logger.error("Failed to load anomalies for triage: %s", exc)
        return []


def _persist_feedback(anomaly_id: str, new_status: str, feedback_doc: Dict) -> bool:
    sm = app_state.storage_manager
    if sm is None:
        return False
    try:
        with sm.get_connection() as conn:
            if not conn:
                return False
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE anomalies
                SET status     = %s,
                    analysis   = COALESCE(analysis, '{}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (new_status, json.dumps({"feedback": feedback_doc}), anomaly_id),
            )
            conn.commit()
            rows = cur.rowcount
            cur.close()
            return rows > 0
    except Exception as exc:
        logger.error("Feedback persist error for %s: %s", anomaly_id, exc)
        return False


# ---------------------------------------------------------------------------
# GET /anomalies/groups
# ---------------------------------------------------------------------------

@router.get("/anomalies/groups", tags=["Triage"])
async def list_anomaly_groups(
    entity_keys: str = Query(
        "computerName",
        description="Comma-separated entity fields to group by (e.g. 'computerName,src_ip')",
    ),
    dedup: bool = Query(True, description="Apply dedup window before grouping"),
    window_seconds: int = Query(300, description="Dedup window in seconds"),
    limit: int = Query(5000, description="Max anomalies to consider"),
):
    """Return anomalies grouped by entity (Sentinel/Chronicle-style incident view).

    Each group contains: entity, count, first_seen, last_seen, top_severity, alert_ids.
    Full alerts are omitted — fetch them via /anomalies/groups/{entity_id}.
    """
    from anomaly_detection.triage.grouping import group_by_entity, dedup_window

    keys = [k.strip() for k in entity_keys.split(",") if k.strip()] or ["computerName"]
    anomalies = await asyncio.to_thread(_load_anomalies, limit)

    if dedup:
        anomalies = await asyncio.to_thread(dedup_window, anomalies, window_seconds, keys)

    groups = await asyncio.to_thread(group_by_entity, anomalies, keys)

    # Return slim view (no nested alert objects)
    return [
        {k: v for k, v in g.items() if k != "alerts"}
        for g in groups
    ]


# ---------------------------------------------------------------------------
# GET /anomalies/groups/{entity_id}
# ---------------------------------------------------------------------------

@router.get("/anomalies/groups/{entity_id:path}", tags=["Triage"])
async def get_anomaly_group(
    entity_id: str = Path(..., description="Entity ID returned by /anomalies/groups"),
    entity_keys: str = Query("computerName"),
    limit: int = Query(5000),
):
    """Return one entity group with the full list of member alerts."""
    from anomaly_detection.triage.grouping import group_by_entity

    keys = [k.strip() for k in entity_keys.split(",") if k.strip()] or ["computerName"]
    anomalies = await asyncio.to_thread(_load_anomalies, limit)
    groups = await asyncio.to_thread(group_by_entity, anomalies, keys)

    for group in groups:
        if group["entity"] == entity_id:
            return group

    raise HTTPException(status_code=404, detail=f"Entity group '{entity_id}' not found")


# ---------------------------------------------------------------------------
# POST /anomalies/{id}/feedback
# ---------------------------------------------------------------------------

@router.post("/anomalies/{anomaly_id}/feedback", tags=["Triage"])
async def submit_feedback(
    anomaly_id: str = Path(..., description="Anomaly ID"),
    payload: FeedbackPayload = Body(...),
):
    """Persist analyst TP/FP verdict and reason code for an anomaly.

    Maps TP → status 'resolved', FP → status 'false_positive'.
    Writes a structured feedback sub-document into the analysis JSONB field.
    """
    if payload.status not in ("TP", "FP"):
        raise HTTPException(status_code=422, detail="status must be 'TP' or 'FP'")

    valid_codes = _reason_codes()
    if payload.reason_code not in valid_codes:
        raise HTTPException(
            status_code=422,
            detail=f"reason_code must be one of: {valid_codes}",
        )

    new_status = "resolved" if payload.status == "TP" else "false_positive"
    feedback_doc = {
        "verdict": payload.status,
        "reason_code": payload.reason_code,
        "notes": payload.notes or "",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    ok = await asyncio.to_thread(_persist_feedback, anomaly_id, new_status, feedback_doc)
    if not ok:
        raise HTTPException(status_code=404, detail="Anomaly not found or update failed")

    return {
        "anomaly_id": anomaly_id,
        "status": new_status,
        "feedback": feedback_doc,
    }


# ---------------------------------------------------------------------------
# GET /triage/reason-codes
# ---------------------------------------------------------------------------

@router.get("/triage/reason-codes", tags=["Triage"])
async def list_reason_codes():
    """Return the configured set of TP/FP reason codes."""
    return {"reason_codes": _reason_codes()}
