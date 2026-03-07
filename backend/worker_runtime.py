"""Background workflow execution for the dedicated worker service."""

from __future__ import annotations

import asyncio
from typing import Optional

from config import settings
from database.project_tracking_store import (
    claim_next_generation_job,
    create_project_revision,
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


def _workflow_failed(state: Optional[dict]) -> bool:
    if not state:
        return False

    status = state.get("current_status", "")
    if state.get("error"):
        return True
    return status == "error" or status.endswith("_error") or status.endswith("_failed")


def _infer_error_type(message: str, failure_stage: str) -> str:
    lowered = message.lower()
    if "timeout" in lowered:
        return "timeout"
    if "validation" in lowered or "schema" in lowered or "parse" in lowered:
        return "validation_error"
    if "session not found" in lowered:
        return "session_not_found"
    if "redis" in lowered or "postgres" in lowered or "connection" in lowered:
        return "dependency_unavailable"
    if failure_stage and failure_stage not in {"workflow", "worker"}:
        return f"{failure_stage}_failed"
    return "generation_failed"


def _build_failure_payload(
    message: str,
    trigger: str,
    state: Optional[dict] = None,
    *,
    recoverable: bool = True,
    retry_available: bool = True,
    user_message: Optional[str] = None,
) -> dict:
    state = state or {}
    failure_stage = state.get("current_agent") or "workflow"
    workflow_status = state.get("current_status") or "error"
    if user_message is None:
        if failure_stage and failure_stage not in {"workflow", "worker"}:
            user_message = f"{failure_stage} 阶段失败，请修正后重试"
        else:
            user_message = "生成失败，请重试"

    details = {
        "agent": failure_stage,
        "workflow_status": workflow_status,
    }
    if state.get("current_status"):
        details["current_status"] = state["current_status"]
    if state.get("last_restored_revision_number") is not None:
        details["last_restored_revision_number"] = state["last_restored_revision_number"]

    return {
        "type": "error",
        "status": "error",
        "message": message,
        "user_message": user_message,
        "error_type": _infer_error_type(message, failure_stage),
        "failure_stage": failure_stage,
        "recoverable": recoverable,
        "retry_available": retry_available,
        "retry_trigger": trigger if retry_available else None,
        "details": details,
    }


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


async def _job_heartbeat(
    job_id: str,
    status_ref: dict,
    stop_event: asyncio.Event,
) -> None:
    """Keep active jobs fresh so only abandoned work is reclaimed."""
    while not stop_event.is_set():
        await asyncio.sleep(settings.WORKER_JOB_HEARTBEAT_SECONDS)
        if stop_event.is_set():
            break

        status = status_ref.get("status", "running")
        if status in {"completed", "error", "waiting_for_outline_approval"}:
            break

        await update_generation_job(job_id, status=status)


async def consume_generation_queue(stop_event: Optional[asyncio.Event] = None) -> None:
    """Continuously claim queued jobs and execute them inside the worker process."""
    while stop_event is None or not stop_event.is_set():
        job = await claim_next_generation_job()
        if job is None:
            await asyncio.sleep(settings.WORKER_QUEUE_POLL_INTERVAL_SECONDS)
            continue

        await record_job_event(
            job["session_id"],
            "status",
            {
                "type": "status",
                "agent": "worker",
                "status": "starting",
                "message": f"Worker claimed queued job for {job['trigger']}",
            },
            job_id=job["job_id"],
        )
        await execute_generation_job(
            job["session_id"],
            job["job_id"],
            job["trigger"],
        )


async def execute_generation_job(session_id: str, job_id: str, trigger: str) -> None:
    """Run a generation workflow inside the worker service and persist events."""
    state = await _load_session_state(session_id)
    if not state:
        error_data = _build_failure_payload(
            "Session not found",
            trigger,
            {"current_agent": "worker", "current_status": "error"},
            recoverable=False,
            retry_available=False,
            user_message="会话不存在，无法继续重试",
        )
        await update_generation_job(job_id, status="error", error_message="Session not found")
        await record_job_event(session_id, "error", error_data, job_id=job_id)
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
    heartbeat_status = {"status": "running"}
    heartbeat_stop = asyncio.Event()
    heartbeat_task = asyncio.create_task(
        _job_heartbeat(job_id, heartbeat_status, heartbeat_stop)
    )

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
                heartbeat_status["status"] = status
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
        heartbeat_status["status"] = final_state.get("current_status", "completed")
        await _finalize_generation_job(session_id, job_id, trigger, final_state)
    except asyncio.CancelledError:
        current_state = await _load_session_state(session_id) or dict(state)
        await record_job_event(
            session_id,
            "status",
            {
                "type": "status",
                "agent": "worker",
                "status": "interrupted",
                "message": "Worker interrupted; job will be recovered from durable state",
            },
            job_id=job_id,
        )
        raise
    except Exception as exc:
        current_state = await _load_session_state(session_id) or dict(state)
        heartbeat_status["status"] = "error"
        error_data = _build_failure_payload(str(exc), trigger, current_state)
        await update_generation_job(
            job_id,
            state=current_state,
            status="error",
            error_message=str(exc),
        )
        await record_job_event(session_id, "error", error_data, job_id=job_id)
        await create_project_revision(session_id, "generation_failed", current_state)
    finally:
        heartbeat_stop.set()
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)


async def _finalize_generation_job(
    session_id: str,
    job_id: str,
    trigger: str,
    final_state: dict,
) -> None:
    if _workflow_failed(final_state):
        error_message = final_state.get("error", "Workflow failed")
        error_data = _build_failure_payload(error_message, trigger, final_state)
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
