"""Project, revision, job, and event persistence helpers."""

import uuid
from datetime import datetime
from typing import Optional, Union

from sqlalchemy import func, select

from database.models import (
    GenerationJob,
    JobEvent,
    Project,
    ProjectRevision,
    WorkflowSession,
)
from database.postgres import AsyncSessionLocal


Identifier = Optional[Union[str, uuid.UUID]]


def _as_uuid(value: Identifier) -> Optional[uuid.UUID]:
    if value is None:
        return None
    return uuid.UUID(str(value))


def _extract_theme(state: dict) -> Optional[str]:
    theme_config = state.get("theme_config", {}) or {}
    if theme_config.get("style_id"):
        return theme_config["style_id"]
    if theme_config.get("style"):
        return theme_config["style"]
    if state.get("style_id"):
        return state["style_id"]
    return None


async def _get_workflow_session(db, session_id: str) -> Optional[WorkflowSession]:
    result = await db.execute(
        select(WorkflowSession).where(WorkflowSession.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def _get_project_id(db, session_id: str, project_id: Identifier = None) -> Optional[uuid.UUID]:
    if project_id is not None:
        return _as_uuid(project_id)

    workflow_session = await _get_workflow_session(db, session_id)
    if workflow_session is None:
        return None
    return workflow_session.project_id


async def sync_project_state(session_id: str, state: dict) -> Optional[dict]:
    """Synchronize the latest workflow snapshot into the Project record."""
    async with AsyncSessionLocal() as db:
        project_id = await _get_project_id(db, session_id)
        if project_id is None:
            return None

        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            return None

        project.user_intent = state.get("user_intent", project.user_intent)
        theme = _extract_theme(state)
        if theme:
            project.theme = theme
        project.outline = state.get("outline", project.outline or [])
        project.status = state.get("current_status", project.status)
        if state.get("pptx_path"):
            project.pptx_path = state["pptx_path"]

        await db.commit()
        return {
            "project_id": str(project.id),
            "status": project.status,
            "theme": project.theme,
            "pptx_path": project.pptx_path or "",
        }


async def create_project_revision(
    session_id: str,
    revision_type: str,
    state: dict,
    project_id: Identifier = None,
) -> dict:
    """Persist a point-in-time project/session snapshot."""
    async with AsyncSessionLocal() as db:
        resolved_project_id = await _get_project_id(db, session_id, project_id=project_id)
        result = await db.execute(
            select(func.max(ProjectRevision.revision_number)).where(
                ProjectRevision.session_id == session_id
            )
        )
        next_revision_number = (result.scalar() or 0) + 1

        revision = ProjectRevision(
            project_id=resolved_project_id,
            session_id=session_id,
            revision_number=next_revision_number,
            revision_type=revision_type,
            status=state.get("current_status", "unknown"),
            theme=_extract_theme(state),
            outline=state.get("outline", []),
            state_snapshot=dict(state),
        )
        db.add(revision)
        await db.commit()

        return {
            "revision_id": str(revision.id),
            "revision_number": revision.revision_number,
            "revision_type": revision.revision_type,
        }


async def create_generation_job(
    session_id: str,
    trigger: str,
    state: dict,
    project_id: Identifier = None,
) -> dict:
    """Create a generation job record for a workflow run."""
    async with AsyncSessionLocal() as db:
        resolved_project_id = await _get_project_id(db, session_id, project_id=project_id)
        job = GenerationJob(
            project_id=resolved_project_id,
            session_id=session_id,
            trigger=trigger,
            status=state.get("current_status", "created"),
            current_agent=state.get("current_agent", ""),
            pptx_path=state.get("pptx_path") or None,
        )
        db.add(job)
        await db.commit()

        return {
            "job_id": str(job.id),
            "status": job.status,
            "trigger": job.trigger,
        }


async def update_generation_job(
    job_id: Union[str, uuid.UUID],
    state: Optional[dict] = None,
    status: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Optional[dict]:
    """Update the latest state of a generation job."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GenerationJob).where(GenerationJob.id == _as_uuid(job_id))
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None

        if state:
            job.current_agent = state.get("current_agent", job.current_agent)
            if state.get("pptx_path"):
                job.pptx_path = state["pptx_path"]

        if status:
            job.status = status
        elif state and state.get("current_status"):
            job.status = state["current_status"]

        if error_message is not None:
            job.error_message = error_message

        if job.status in {"completed", "error"}:
            job.completed_at = datetime.utcnow()

        await db.commit()
        return {
            "job_id": str(job.id),
            "status": job.status,
            "current_agent": job.current_agent,
            "pptx_path": job.pptx_path or "",
            "error_message": job.error_message,
        }


async def record_job_event(
    session_id: str,
    event_type: str,
    payload: dict,
    job_id: Identifier = None,
    project_id: Identifier = None,
) -> dict:
    """Persist a workflow event emitted during generation."""
    async with AsyncSessionLocal() as db:
        resolved_project_id = await _get_project_id(db, session_id, project_id=project_id)
        event = JobEvent(
            job_id=_as_uuid(job_id),
            project_id=resolved_project_id,
            session_id=session_id,
            event_type=event_type,
            agent=payload.get("agent", ""),
            status=payload.get("status", ""),
            message=payload.get("message", ""),
            payload=dict(payload),
        )
        db.add(event)
        await db.commit()

        return {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "status": event.status,
        }
