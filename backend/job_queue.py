"""Queue helpers for generation jobs."""

from __future__ import annotations

from database.project_tracking_store import (
    create_generation_job,
    find_active_generation_job,
    record_job_event,
)
from database.workflow_state_store import load_workflow_state


async def enqueue_generation_job(session_id: str, trigger: str, source: str = "api") -> dict:
    """Create or reuse a queued generation job for worker consumption."""
    active_job = await find_active_generation_job(session_id, trigger)
    if active_job is not None:
        return {
            "job_id": active_job["job_id"],
            "status": active_job["status"],
            "trigger": trigger,
        }

    state = await load_workflow_state(session_id)
    if not state:
        raise ValueError("Session not found")

    job = await create_generation_job(
        session_id,
        trigger,
        dict(state),
        status="queued",
    )
    await record_job_event(
        session_id,
        "status",
        {
            "type": "status",
            "agent": source,
            "status": "queued",
            "message": f"Generation job queued for {trigger}",
        },
        job_id=job["job_id"],
    )
    return job
