"""Correlation analysis routes and background jobs."""
import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Path

from api.state import app_state
from api.schemas import (
    CorrelationRequest,
    BulkCorrelationRequest,
    CorrelationMatrixRequest,
    JobStatus,
)
from api.helpers import (
    parse_timestamp,
    get_anomaly_severity,
    find_correlations,
    calculate_pairwise_correlation,
    build_correlation_matrix,
    store_detection_results,
)

logger = logging.getLogger("api_services")
router = APIRouter()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/anomalies/correlate", tags=["Correlation"], response_model=JobStatus)
async def analyze_anomaly_correlations(
    background_tasks: BackgroundTasks,
    correlation_request: CorrelationRequest
):
    """
    Analyze correlations for a specific anomaly.

    Args:
        background_tasks: FastAPI background tasks
        correlation_request: Correlation analysis request

    Returns:
        Job status information
    """
    job_id = f"correlation_{correlation_request.anomaly_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    current_time = datetime.utcnow().isoformat()

    app_state.background_jobs[job_id] = {
        "job_id": job_id,
        "job_type": "correlation_analysis",
        "status": "pending",
        "start_time": current_time,
        "end_time": None,
        "parameters": {
            "anomaly_id": correlation_request.anomaly_id,
            "time_window_hours": correlation_request.time_window_hours,
            "min_correlation_score": correlation_request.min_correlation_score,
            "max_results": correlation_request.max_results
        },
        "result": None,
        "progress": 0.0,
        "created_at": current_time,
        "updated_at": current_time
    }

    background_tasks.add_task(
        correlation_analysis_job,
        correlation_request.anomaly_id,
        correlation_request.time_window_hours,
        correlation_request.min_correlation_score,
        correlation_request.max_results,
        job_id
    )

    return app_state.background_jobs[job_id]


@router.get("/anomalies/{anomaly_id}/correlations", tags=["Correlation"], response_model=Dict[str, Any])
async def get_anomaly_correlations(
    anomaly_id: str = Path(..., description="ID of the anomaly"),
    time_window_hours: int = Query(24, description="Time window in hours"),
    min_correlation_score: float = Query(0.3, description="Minimum correlation score"),
    max_results: int = Query(50, description="Maximum results")
):
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
    if not app_state.storage_manager:
        raise HTTPException(status_code=503, detail="Storage manager not available")

    target_anomaly = await asyncio.to_thread(app_state.storage_manager.get_anomaly_by_id, anomaly_id)
    if not target_anomaly:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")

    target_time = parse_timestamp(target_anomaly.get('timestamp'))
    if target_time:
        start_time = target_time - timedelta(hours=time_window_hours)
        end_time = target_time + timedelta(hours=time_window_hours)

        all_anomalies = await asyncio.to_thread(app_state.storage_manager.get_anomalies, limit=5000)

        anomalies_in_window = []
        for a in all_anomalies:
            a_time = parse_timestamp(a.get('timestamp'))
            if a_time and start_time <= a_time <= end_time:
                anomalies_in_window.append(a)
    else:
        anomalies_in_window = await asyncio.to_thread(app_state.storage_manager.get_anomalies, limit=500)

    correlations = find_correlations(
        target_anomaly,
        anomalies_in_window,
        time_window_hours,
        min_correlation_score
    )

    if len(correlations) > max_results:
        correlations = correlations[:max_results]

    total_correlations = len(correlations)
    high_correlations = sum(1 for c in correlations if c['score'] > 0.7)
    avg_correlation = sum(c['score'] for c in correlations) / total_correlations if total_correlations > 0 else 0

    return {
        "target_anomaly": target_anomaly,
        "correlations": correlations,
        "statistics": {
            "total_correlations": total_correlations,
            "high_correlations": high_correlations,
            "average_correlation": avg_correlation,
            "anomalies_checked": len(anomalies_in_window),
            "time_window_hours": time_window_hours
        }
    }


@router.post("/anomalies/bulk-correlate", tags=["Correlation"], response_model=Dict[str, Any])
async def bulk_correlate_anomalies(bulk_request: BulkCorrelationRequest):
    """
    Analyze correlations for multiple anomalies.

    Args:
        bulk_request: Bulk correlation request

    Returns:
        Bulk correlation results
    """
    if not app_state.storage_manager:
        raise HTTPException(status_code=503, detail="Storage manager not available")

    results = {}

    target_anomalies = []
    for anomaly_id in bulk_request.anomaly_ids:
        anomaly = await asyncio.to_thread(app_state.storage_manager.get_anomaly_by_id, anomaly_id)
        if anomaly:
            target_anomalies.append(anomaly)

    if not target_anomalies:
        raise HTTPException(status_code=404, detail="No valid anomalies found")

    all_anomalies = await asyncio.to_thread(app_state.storage_manager.get_anomalies, limit=5000)

    for target in target_anomalies:
        correlations = find_correlations(
            target,
            all_anomalies,
            bulk_request.time_window_hours,
            bulk_request.min_correlation_score
        )

        if bulk_request.cross_correlate:
            for other in target_anomalies:
                if other['id'] != target['id']:
                    score = calculate_pairwise_correlation(target, other)
                    if score >= bulk_request.min_correlation_score:
                        found = False
                        for c in correlations:
                            if c['anomaly']['id'] == other['id']:
                                found = True
                                break

                        if not found:
                            reasons = []
                            if target.get('src_ip') == other.get('src_ip') and target.get('src_ip'):
                                reasons.append("Same source IP")
                            if target.get('location') == other.get('location'):
                                reasons.append("Same location")
                            if abs(float(target.get('score', 0)) - float(other.get('score', 0))) < 0.1:
                                reasons.append("Similar anomaly score")

                            correlations.append({
                                'anomaly': other,
                                'score': score,
                                'reasons': reasons or ["Cross-correlation match"]
                            })

        correlations.sort(key=lambda x: x['score'], reverse=True)

        results[target['id']] = {
            'target_anomaly': target,
            'correlations': correlations[:50],
            'correlation_count': len(correlations)
        }

    total_correlations = sum(r['correlation_count'] for r in results.values())

    return {
        "results": results,
        "statistics": {
            "anomalies_analyzed": len(target_anomalies),
            "total_correlations_found": total_correlations,
            "cross_correlations_enabled": bulk_request.cross_correlate
        }
    }


@router.post("/anomalies/correlation-matrix", tags=["Correlation"], response_model=Dict[str, Any])
async def generate_correlation_matrix(matrix_request: CorrelationMatrixRequest):
    """
    Generate a correlation matrix for the specified anomalies.

    Args:
        matrix_request: Correlation matrix request

    Returns:
        Correlation matrix and metadata
    """
    try:
        if not app_state.storage_manager:
            raise HTTPException(status_code=503, detail="Storage manager not available")

        if not matrix_request.anomaly_ids or not isinstance(matrix_request.anomaly_ids, list):
            raise HTTPException(status_code=400, detail="Invalid anomaly_ids: must be a non-empty list")

        if len(matrix_request.anomaly_ids) < 2:
            raise HTTPException(status_code=400, detail="At least 2 anomaly IDs required for matrix")

        if len(matrix_request.anomaly_ids) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 anomalies allowed for matrix")

        anomalies = []
        missing_ids = []

        for anomaly_id in matrix_request.anomaly_ids:
            try:
                anomaly = await asyncio.to_thread(app_state.storage_manager.get_anomaly_by_id, anomaly_id)
                if anomaly:
                    anomalies.append(anomaly)
                else:
                    missing_ids.append(anomaly_id)
            except Exception as e:
                logger.error(f"Error retrieving anomaly {anomaly_id}: {e}")
                missing_ids.append(anomaly_id)

        if len(anomalies) < 2:
            error_msg = f"At least 2 valid anomalies required for matrix. Found {len(anomalies)} valid anomalies."
            if missing_ids:
                error_msg += f" Missing IDs: {missing_ids[:10]}"
            raise HTTPException(status_code=400, detail=error_msg)

        try:
            matrix, labels = build_correlation_matrix(anomalies)
        except Exception as e:
            logger.error(f"Error building correlation matrix: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Error building correlation matrix: {str(e)}")

        if not matrix or not labels:
            raise HTTPException(status_code=500, detail="Failed to build correlation matrix")

        response = {
            "matrix": matrix,
            "labels": labels,
            "anomaly_count": len(anomalies),
            "requested_count": len(matrix_request.anomaly_ids)
        }

        if missing_ids:
            response["warning"] = f"{len(missing_ids)} anomalies not found"
            response["missing_ids"] = missing_ids[:10]

        if matrix_request.include_metadata:
            try:
                metadata = []
                for anomaly in anomalies:
                    try:
                        metadata.append({
                            "id": anomaly.get('id', 'unknown'),
                            "model": anomaly.get('model', 'unknown'),
                            "score": float(anomaly.get('score', 0)),
                            "severity": get_anomaly_severity(anomaly),
                            "timestamp": anomaly.get('timestamp', 'unknown'),
                            "location": anomaly.get('location', 'unknown')
                        })
                    except Exception as e:
                        logger.warning(f"Error adding metadata for anomaly: {e}")
                        metadata.append({
                            "id": anomaly.get('id', 'unknown'),
                            "error": "Failed to extract metadata"
                        })
                response["metadata"] = metadata
            except Exception as e:
                logger.error(f"Error preparing metadata: {e}")
                response["metadata_error"] = str(e)

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_correlation_matrix: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/anomalies/correlation-stats", tags=["Correlation"], response_model=Dict[str, Any])
async def get_correlation_statistics(
    time_window_hours: int = Query(24, description="Time window in hours"),
    min_correlation_score: float = Query(0.3, description="Minimum correlation score")
):
    """
    Get overall correlation statistics for recent anomalies.

    Args:
        time_window_hours: Time window in hours
        min_correlation_score: Minimum correlation score

    Returns:
        Correlation statistics
    """
    if not app_state.storage_manager:
        raise HTTPException(status_code=503, detail="Storage manager not available")

    end_time = datetime.now()
    start_time = end_time - timedelta(hours=time_window_hours)

    all_anomalies = await asyncio.to_thread(app_state.storage_manager.get_anomalies, limit=5000)

    recent_anomalies = []
    for a in all_anomalies:
        a_time = parse_timestamp(a.get('timestamp'))
        if a_time and start_time <= a_time <= end_time:
            recent_anomalies.append(a)

    if not recent_anomalies:
        return {
            "message": "No anomalies found in the specified time window",
            "time_window_hours": time_window_hours,
            "statistics": {}
        }

    total_pairs = 0
    correlated_pairs = 0
    correlation_by_type = {}
    high_correlation_pairs = []

    for i in range(len(recent_anomalies)):
        for j in range(i + 1, len(recent_anomalies)):
            total_pairs += 1

            score = calculate_pairwise_correlation(recent_anomalies[i], recent_anomalies[j])

            if score >= min_correlation_score:
                correlated_pairs += 1

                if recent_anomalies[i].get('src_ip') == recent_anomalies[j].get('src_ip') and recent_anomalies[i].get('src_ip'):
                    correlation_by_type['same_source_ip'] = correlation_by_type.get('same_source_ip', 0) + 1

                if recent_anomalies[i].get('location') == recent_anomalies[j].get('location'):
                    correlation_by_type['same_location'] = correlation_by_type.get('same_location', 0) + 1

                if recent_anomalies[i].get('model') == recent_anomalies[j].get('model'):
                    correlation_by_type['same_model'] = correlation_by_type.get('same_model', 0) + 1

                if score > 0.7:
                    high_correlation_pairs.append({
                        'anomaly1': recent_anomalies[i]['id'],
                        'anomaly2': recent_anomalies[j]['id'],
                        'score': score
                    })

    high_correlation_pairs.sort(key=lambda x: x['score'], reverse=True)

    return {
        "time_window_hours": time_window_hours,
        "anomaly_count": len(recent_anomalies),
        "statistics": {
            "total_pairs_checked": total_pairs,
            "correlated_pairs": correlated_pairs,
            "correlation_percentage": (correlated_pairs / total_pairs * 100) if total_pairs > 0 else 0,
            "correlation_by_type": correlation_by_type,
            "high_correlation_pairs": high_correlation_pairs[:10]
        }
    }


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------

async def correlation_analysis_job(
    anomaly_id: str,
    time_window_hours: int,
    min_score: float,
    max_results: int,
    job_id: str
):
    """
    Background job for analyzing correlations for an anomaly.

    Args:
        anomaly_id: ID of the anomaly to analyze
        time_window_hours: Time window in hours
        min_score: Minimum correlation score
        max_results: Maximum results to return
        job_id: ID of the job
    """
    try:
        logging.info(f"Starting correlation analysis job {job_id} for anomaly {anomaly_id}")
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "running"
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        if not app_state.storage_manager:
            raise ValueError("Storage manager not available")

        target_anomaly = await asyncio.to_thread(app_state.storage_manager.get_anomaly_by_id, anomaly_id)
        if not target_anomaly:
            raise ValueError(f"Anomaly {anomaly_id} not found")

        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["progress"] = 0.2
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        target_time = parse_timestamp(target_anomaly.get('timestamp'))
        if target_time:
            start_time = target_time - timedelta(hours=time_window_hours)
            end_time = target_time + timedelta(hours=time_window_hours)

            all_anomalies = await asyncio.to_thread(app_state.storage_manager.get_anomalies, limit=5000)

            anomalies_in_window = []
            for a in all_anomalies:
                a_time = parse_timestamp(a.get('timestamp'))
                if a_time and start_time <= a_time <= end_time:
                    anomalies_in_window.append(a)
        else:
            anomalies_in_window = await asyncio.to_thread(app_state.storage_manager.get_anomalies, limit=500)

        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["progress"] = 0.5
            app_state.background_jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()

        correlations = find_correlations(
            target_anomaly,
            anomalies_in_window,
            time_window_hours,
            min_score
        )

        if len(correlations) > max_results:
            correlations = correlations[:max_results]

        total_correlations = len(correlations)
        high_correlations = sum(1 for c in correlations if c['score'] > 0.7)
        avg_correlation = sum(c['score'] for c in correlations) / total_correlations if total_correlations > 0 else 0

        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "completed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {
                "target_anomaly": target_anomaly,
                "correlations": correlations,
                "statistics": {
                    "total_correlations": total_correlations,
                    "high_correlations": high_correlations,
                    "average_correlation": avg_correlation,
                    "anomalies_checked": len(anomalies_in_window),
                    "time_window_hours": time_window_hours
                }
            }

        logging.info(f"Completed correlation analysis job {job_id} with {total_correlations} correlations")

        with app_state.background_jobs_lock:
            result_copy = app_state.background_jobs[job_id]["result"].copy()
        await store_detection_results(job_id, result_copy)

    except Exception as e:
        logging.error(f"Error in correlation analysis job {job_id}: {str(e)}")
        logging.error(traceback.format_exc())
        current_time = datetime.utcnow().isoformat()
        with app_state.background_jobs_lock:
            app_state.background_jobs[job_id]["status"] = "failed"
            app_state.background_jobs[job_id]["end_time"] = current_time
            app_state.background_jobs[job_id]["updated_at"] = current_time
            app_state.background_jobs[job_id]["progress"] = 1.0
            app_state.background_jobs[job_id]["result"] = {"error": str(e)}
