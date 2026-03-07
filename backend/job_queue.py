"""Queue helpers for generation jobs."""

from __future__ import annotations

from database.project_tracking_store import (
    create_generation_job,
    find_active_generation_job,
    find_latest_generation_job,
    record_job_event,
)
from database.workflow_state_store import load_workflow_state


def trigger_already_satisfied(state: dict, trigger: str) -> bool:
    """Return whether the requested workflow phase has already produced its terminal state."""
    status = state.get("current_status", "")
    if trigger == "start_workflow":
        return status == "waiting_for_outline_approval" and bool(state.get("outline"))

    return bool(state.get("pptx_path")) or status in {"render_complete", "completed"}


def _reusable_terminal_statuses(trigger: str) -> set[str]:
    if trigger == "start_workflow":
        return {"waiting_for_outline_approval"}
    return {"completed"}


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

    latest_job = await find_latest_generation_job(session_id, trigger)
    if (
        latest_job is not None
        and latest_job["status"] in _reusable_terminal_statuses(trigger)
        and trigger_already_satisfied(state, trigger)
    ):
        return {
            "job_id": latest_job["job_id"],
            "status": latest_job["status"],
            "trigger": trigger,
        }

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
