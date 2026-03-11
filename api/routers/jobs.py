"""Job management routes."""
import logging
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from api.state import app_state
from api.schemas import JobStatus

logger = logging.getLogger("api_services")
router = APIRouter()


@router.get("/jobs/{job_id}", tags=["Jobs"], response_model=JobStatus)
async def get_job_status(job_id: str = Path(..., description="ID of the job to check")):
    """Get the status of a background job."""
    if job_id not in app_state.background_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return app_state.background_jobs[job_id]


@router.get("/jobs", tags=["Jobs"], response_model=List[JobStatus])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter jobs by status"),
    job_type: Optional[str] = Query(None, description="Filter jobs by type"),
    limit: int = Query(10, description="Maximum number of jobs to return")
):
    """List background jobs."""
    result = []

    for job_id, job_info in sorted(
        app_state.background_jobs.items(),
        key=lambda x: x[1]["start_time"],
        reverse=True
    ):
        if (status is None or job_info["status"] == status) and \
           (job_type is None or job_info.get("job_type") == job_type):
            result.append(job_info)

            if len(result) >= limit:
                break

    return result


@router.get("/results/{job_id}", tags=["Results"], response_model=Dict[str, Any])
async def get_job_results(job_id: str = Path(..., description="Job ID to retrieve results for")):
    """Get detailed results for a job from the database."""
    import asyncio

    # Check in-memory jobs first
    if job_id in app_state.background_jobs:
        return app_state.background_jobs[job_id]

    # Check database for historical results
    if app_state.storage_manager:
        job_data = await asyncio.to_thread(_get_job_from_db_sync, job_id)
        if job_data:
            return job_data

    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


def _get_job_from_db_sync(job_id: str) -> Optional[Dict[str, Any]]:
    """Synchronous helper to get job from database."""
    try:
        import psycopg2.extras
    except ImportError:
        logging.error("psycopg2 not available")
        return None

    try:
        with app_state.storage_manager.get_connection() as conn:
            if conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))

                result = cursor.fetchone()
                if result:
                    job_data = dict(result)
                    for field in ['created_at', 'updated_at']:
                        if field in job_data and job_data[field]:
                            job_data[field] = job_data[field].isoformat()
                    return job_data
    except Exception as e:
        logging.error(f"Error retrieving job results: {str(e)}")

    return None
