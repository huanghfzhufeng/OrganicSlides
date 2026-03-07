"""Background workflow execution for the dedicated worker service."""

from __future__ import annotations

import asyncio
from typing import Optional

from database.project_tracking_store import (
    create_generation_job,
    create_project_revision,
    find_active_generation_job,
    record_job_event,
    sync_project_state,
    update_generation_job,
)
from database.workflow_state_store import (
    load_workflow_state,
    save_workflow_state,
    update_workflow_state,
)
from graph import get_main_app, get_resume_app


_ACTIVE_TASKS: set[asyncio.Task] = set()


def _workflow_failed(state: Optional[dict]) -> bool:
    if not state:
        return False

    status = state.get("current_status", "")
    if state.get("error"):
        return True
    return status == "error" or status.endswith("_error") or status.endswith("_failed")


async def _load_session_state(session_id: str) -> Optional[dict]:
    return await load_workflow_state(session_id)


async def _save_session_state(
    session_id: str,
    state: dict,
    project_id: Optional[str] = None,
) -> dict:
    persisted = await save_workflow_state(session_id, state, project_id=project_id)
    await sync_project_state(session_id, persisted)
    return persisted


async def _merge_session_state(session_id: str, updates: dict) -> Optional[dict]:
    persisted = await update_workflow_state(session_id, updates)
    if persisted is None:
        return None

    await sync_project_state(session_id, persisted)
    return persisted


async def start_worker_job(session_id: str, trigger: str) -> dict:
    """Create a worker-owned generation job and schedule it asynchronously."""
    active_job = await find_active_generation_job(session_id, trigger)
    if active_job is not None:
        return {
            "job_id": active_job["job_id"],
            "status": "already_running",
            "trigger": trigger,
        }

    state = await _load_session_state(session_id)
    if not state:
        raise ValueError("Session not found")

    job = await create_generation_job(session_id, trigger, dict(state))
    await update_generation_job(job["job_id"], state=state, status="queued")
    await record_job_event(
        session_id,
        "status",
        {
            "type": "status",
            "agent": "worker",
            "status": "queued",
            "message": f"Worker accepted job for {trigger}",
        },
        job_id=job["job_id"],
    )

    task = asyncio.create_task(execute_generation_job(session_id, job["job_id"], trigger))
    _ACTIVE_TASKS.add(task)
    task.add_done_callback(_ACTIVE_TASKS.discard)

    return {
        "job_id": job["job_id"],
        "status": "queued",
        "trigger": trigger,
    }


async def execute_generation_job(session_id: str, job_id: str, trigger: str) -> None:
    """Run a generation workflow inside the worker service and persist events."""
    state = await _load_session_state(session_id)
    if not state:
        await update_generation_job(job_id, status="error", error_message="Session not found")
        await record_job_event(
            session_id,
            "error",
            {
                "type": "error",
                "status": "error",
                "message": "Session not found",
            },
            job_id=job_id,
        )
        return

    if trigger == "resume_workflow":
        state["outline_approved"] = True
        await _save_session_state(session_id, state)
        workflow_app = get_resume_app()
        config = {"configurable": {"thread_id": f"{session_id}_resume"}}
    else:
        workflow_app = get_main_app()
        config = {"configurable": {"thread_id": session_id}}

    await update_generation_job(job_id, state=state, status="running")

    try:
        async for event in workflow_app.astream(dict(state), config):
            for node_name, node_output in event.items():
                if node_name == "__end__":
                    continue

                status = node_output.get("current_status", "processing")
                agent = node_output.get("current_agent", node_name)
                messages = node_output.get("messages", [])

                data = {
                    "type": "status",
                    "agent": agent,
                    "status": status,
                    "message": messages[-1]["content"] if messages else "",
                }
                persisted_state = await _merge_session_state(session_id, node_output) or dict(state)
                state = persisted_state

                await update_generation_job(job_id, state=persisted_state, status=status)
                await record_job_event(session_id, data["type"], data, job_id=job_id)

                for render_event in node_output.get("render_progress_events", []):
                    await record_job_event(
                        session_id,
                        render_event.get("type", "render_progress"),
                        render_event,
                        job_id=job_id,
                    )

                await asyncio.sleep(0.1)

        final_state = await _load_session_state(session_id) or {}
        await _finalize_generation_job(session_id, job_id, trigger, final_state)
    except Exception as exc:
        current_state = await _load_session_state(session_id) or dict(state)
        await update_generation_job(
            job_id,
            state=current_state,
            status="error",
            error_message=str(exc),
        )
        await record_job_event(
            session_id,
            "error",
            {
                "type": "error",
                "status": "error",
                "message": str(exc),
            },
            job_id=job_id,
        )
        await create_project_revision(session_id, "generation_failed", current_state)


async def _finalize_generation_job(
    session_id: str,
    job_id: str,
    trigger: str,
    final_state: dict,
) -> None:
    if _workflow_failed(final_state):
        error_message = final_state.get("error", "Workflow failed")
        error_data = {
            "type": "error",
            "status": "error",
            "message": error_message,
        }
        await update_generation_job(
            job_id,
            state=final_state,
            status="error",
            error_message=error_message,
        )
        await record_job_event(session_id, error_data["type"], error_data, job_id=job_id)
        await create_project_revision(session_id, "generation_failed", final_state)
        return

    if trigger == "start_workflow" and final_state.get("current_status") == "waiting_for_outline_approval":
        hitl_data = {
            "type": "hitl",
            "status": "waiting_for_approval",
            "outline": final_state.get("outline", []),
        }
        await update_generation_job(
            job_id,
            state=final_state,
            status="waiting_for_outline_approval",
        )
        await record_job_event(session_id, hitl_data["type"], hitl_data, job_id=job_id)
        await create_project_revision(session_id, "outline_generated", final_state)
        return

    complete_data = {
        "type": "complete",
        "status": "done",
    }
    if final_state.get("pptx_path"):
        complete_data["pptx_path"] = final_state["pptx_path"]

    await update_generation_job(job_id, state=final_state, status="completed")
    await record_job_event(session_id, complete_data["type"], complete_data, job_id=job_id)
    await create_project_revision(session_id, "generation_completed", final_state)
