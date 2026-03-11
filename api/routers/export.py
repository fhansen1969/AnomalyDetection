"""Data export routes."""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.state import app_state

logger = logging.getLogger("api_services")
router = APIRouter()


def _export_anomalies_sync(
    start_date: Optional[str],
    end_date: Optional[str],
    model: Optional[str],
    severity: Optional[str],
    limit: int
) -> List[Dict[str, Any]]:
    """
    Synchronous helper to export anomalies from database.
    Runs in thread executor to avoid blocking async event loop.
    """
    # Lazy import to avoid mutex.cc warnings
    try:
        import psycopg2.extras
    except ImportError:
        logging.error("psycopg2 not available for export")
        return []

    anomalies = []

    try:
        with app_state.storage_manager.get_connection() as conn:
            if conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

                query = "SELECT * FROM anomalies WHERE 1=1"
                params = []

                if start_date:
                    query += " AND detection_time >= %s"
                    params.append(start_date)

                if end_date:
                    query += " AND detection_time <= %s"
                    params.append(end_date)

                if model:
                    query += " AND model = %s"
                    params.append(model)

                if severity:
                    query += " AND severity = %s"
                    params.append(severity)

                query += " ORDER BY detection_time DESC LIMIT %s"
                params.append(limit)

                cursor.execute(query, params)

                # Fetch results
                for row in cursor:
                    anomaly = dict(row)
                    # Convert timestamps
                    for field in ['timestamp', 'detection_time', 'created_at', 'updated_at']:
                        if field in anomaly and anomaly[field]:
                            anomaly[field] = anomaly[field].isoformat()
                    anomalies.append(anomaly)

                cursor.close()
    except Exception as e:
        logging.error(f"Error exporting anomalies: {str(e)}")
        raise

    return anomalies


@router.get("/export/anomalies", tags=["Export"])
async def export_anomalies(
    format: str = Query("json", description="Export format (json, csv)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    model: Optional[str] = Query(None, description="Filter by model"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(5000, description="Maximum records to export")
):
    """
    Export anomalies from database with filters.
    FIXED: Uses thread executor for synchronous database operations.

    Returns:
        Exported data in requested format
    """
    if not app_state.storage_manager:
        raise HTTPException(status_code=503, detail="Storage manager not available")

    try:
        # Get anomalies using thread executor
        anomalies = await asyncio.to_thread(
            _export_anomalies_sync,
            start_date,
            end_date,
            model,
            severity,
            limit
        )

        # Format output
        if format == "csv":
            import csv
            import io

            output = io.StringIO()
            if anomalies:
                writer = csv.DictWriter(output, fieldnames=anomalies[0].keys())
                writer.writeheader()
                writer.writerows(anomalies)

            return StreamingResponse(
                io.StringIO(output.getvalue()),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=anomalies_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                }
            )
        else:
            return {
                "export_time": datetime.utcnow().isoformat(),
                "count": len(anomalies),
                "filters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "model": model,
                    "severity": severity
                },
                "data": anomalies
            }
    except Exception as e:
        logging.error(f"Error exporting anomalies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting anomalies: {str(e)}")
