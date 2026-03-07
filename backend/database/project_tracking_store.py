"""Project, revision, job, and event persistence helpers."""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Union

from sqlalchemy import and_, func, or_, select

from config import settings
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


def _serialize_revision(revision: ProjectRevision, include_snapshot: bool = False) -> dict:
    snapshot = dict(revision.state_snapshot or {})
    payload = {
        "revision_id": str(revision.id),
        "project_id": str(revision.project_id) if revision.project_id else None,
        "session_id": revision.session_id,
        "revision_number": revision.revision_number,
        "revision_type": revision.revision_type,
        "status": revision.status,
        "theme": revision.theme,
        "outline": list(revision.outline or []),
        "outline_count": len(revision.outline or []),
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
        "restored_from_revision_number": snapshot.get("last_restored_revision_number"),
    }
    if include_snapshot:
        payload["state_snapshot"] = snapshot
    return payload


async def list_project_revisions(session_id: str, limit: int = 20) -> list[dict]:
    """List project revisions for a workflow session in reverse chronological order."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProjectRevision)
            .where(ProjectRevision.session_id == session_id)
            .order_by(ProjectRevision.revision_number.desc())
            .limit(limit)
        )
        revisions = result.scalars().all()
        return [_serialize_revision(revision) for revision in revisions]


async def count_project_revisions(session_id: str) -> int:
    """Count all persisted revisions for a workflow session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count(ProjectRevision.id)).where(ProjectRevision.session_id == session_id)
        )
        return int(result.scalar() or 0)


async def get_project_revision(
    session_id: str,
    revision_number: Optional[int] = None,
    revision_id: Identifier = None,
) -> Optional[dict]:
    """Fetch a single revision by revision number or revision id."""
    async with AsyncSessionLocal() as db:
        filters = [ProjectRevision.session_id == session_id]
        if revision_id is not None:
            filters.append(ProjectRevision.id == _as_uuid(revision_id))
        elif revision_number is not None:
            filters.append(ProjectRevision.revision_number == revision_number)
        else:
            raise ValueError("revision_number or revision_id is required")

        result = await db.execute(select(ProjectRevision).where(*filters))
        revision = result.scalar_one_or_none()
        if revision is None:
            return None
        return _serialize_revision(revision, include_snapshot=True)


async def restore_project_revision(
    session_id: str,
    revision_number: Optional[int] = None,
    revision_id: Identifier = None,
) -> Optional[dict]:
    """Restore the latest workflow state from a historical revision snapshot."""
    revision = await get_project_revision(
        session_id,
        revision_number=revision_number,
        revision_id=revision_id,
    )
    if revision is None:
        return None

    from database.workflow_state_store import save_workflow_state

    restored_state = dict(revision["state_snapshot"])
    restored_state["session_id"] = session_id
    restored_state["current_status"] = restored_state.get("current_status", revision["status"])
    restored_state["last_restored_revision_id"] = revision["revision_id"]
    restored_state["last_restored_revision_number"] = revision["revision_number"]
    restored_state.pop("error", None)

    persisted_state = await save_workflow_state(
        session_id,
        restored_state,
        project_id=revision["project_id"],
    )
    await sync_project_state(session_id, persisted_state)
    restoration_revision = await create_project_revision(
        session_id,
        "revision_restored",
        persisted_state,
        project_id=revision["project_id"],
    )

    return {
        "restored_revision": revision,
        "restoration_revision": restoration_revision,
        "state": persisted_state,
    }


async def create_generation_job(
    session_id: str,
    trigger: str,
    state: dict,
    project_id: Identifier = None,
    status: Optional[str] = None,
) -> dict:
    """Create a generation job record for a workflow run."""
    async with AsyncSessionLocal() as db:
        resolved_project_id = await _get_project_id(db, session_id, project_id=project_id)
        job = GenerationJob(
            project_id=resolved_project_id,
            session_id=session_id,
            trigger=trigger,
            status=status or state.get("current_status", "created"),
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


async def get_generation_job(job_id: Union[str, uuid.UUID]) -> Optional[dict]:
    """Fetch a single generation job record."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GenerationJob).where(GenerationJob.id == _as_uuid(job_id))
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None

        return {
            "job_id": str(job.id),
            "session_id": job.session_id,
            "project_id": str(job.project_id) if job.project_id else None,
            "trigger": job.trigger,
            "status": job.status,
            "current_agent": job.current_agent,
            "error_message": job.error_message,
            "pptx_path": job.pptx_path or "",
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }


async def find_active_generation_job(session_id: str, trigger: str) -> Optional[dict]:
    """Return the most recent non-terminal job for a session/trigger pair."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GenerationJob)
            .where(
                GenerationJob.session_id == session_id,
                GenerationJob.trigger == trigger,
                GenerationJob.status.notin_(["completed", "error"]),
            )
            .order_by(GenerationJob.created_at.desc())
        )
        job = result.scalars().first()
        if job is None:
            return None

        return {
            "job_id": str(job.id),
            "status": job.status,
            "trigger": job.trigger,
            "current_agent": job.current_agent,
        }


async def find_latest_generation_job(session_id: str, trigger: str) -> Optional[dict]:
    """Return the most recent job for a session/trigger pair."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GenerationJob)
            .where(
                GenerationJob.session_id == session_id,
                GenerationJob.trigger == trigger,
            )
            .order_by(GenerationJob.created_at.desc())
            .limit(1)
        )
        job = result.scalars().first()
        if job is None:
            return None

        return {
            "job_id": str(job.id),
            "session_id": job.session_id,
            "project_id": str(job.project_id) if job.project_id else None,
            "trigger": job.trigger,
            "status": job.status,
            "current_agent": job.current_agent,
            "error_message": job.error_message,
            "pptx_path": job.pptx_path or "",
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }


async def find_session_active_generation_job(session_id: str) -> Optional[dict]:
    """Return the most recent in-flight job for a workflow session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GenerationJob)
            .where(
                GenerationJob.session_id == session_id,
                GenerationJob.status.notin_(["completed", "error"]),
            )
            .order_by(GenerationJob.created_at.desc())
            .limit(1)
        )
        job = result.scalars().first()
        if job is None:
            return None

        return {
            "job_id": str(job.id),
            "session_id": job.session_id,
            "project_id": str(job.project_id) if job.project_id else None,
            "trigger": job.trigger,
            "status": job.status,
            "current_agent": job.current_agent,
            "error_message": job.error_message,
            "pptx_path": job.pptx_path or "",
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }


async def get_latest_failed_generation_job(session_id: str) -> Optional[dict]:
    """Return the most recent failed generation job for a workflow session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GenerationJob)
            .where(
                GenerationJob.session_id == session_id,
                GenerationJob.status == "error",
            )
            .order_by(GenerationJob.updated_at.desc(), GenerationJob.created_at.desc())
            .limit(1)
        )
        job = result.scalars().first()
        if job is None:
            return None

        return {
            "job_id": str(job.id),
            "session_id": job.session_id,
            "project_id": str(job.project_id) if job.project_id else None,
            "trigger": job.trigger,
            "status": job.status,
            "current_agent": job.current_agent,
            "error_message": job.error_message,
            "pptx_path": job.pptx_path or "",
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }


async def claim_next_generation_job() -> Optional[dict]:
    """Claim the next queued or stale in-flight job using row-level locking."""
    async with AsyncSessionLocal() as db:
        stale_before = datetime.utcnow() - timedelta(seconds=settings.WORKER_JOB_STALE_SECONDS)
        result = await db.execute(
            select(GenerationJob)
            .where(
                or_(
                    GenerationJob.status == "queued",
                    and_(
                        GenerationJob.status.in_(["starting", "running"]),
                        GenerationJob.updated_at <= stale_before,
                    ),
                )
            )
            .order_by(GenerationJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = result.scalars().first()
        if job is None:
            return None

        job.status = "starting"
        job.started_at = datetime.utcnow()
        job.error_message = None
        await db.commit()

        return {
            "job_id": str(job.id),
            "session_id": job.session_id,
            "project_id": str(job.project_id) if job.project_id else None,
            "trigger": job.trigger,
            "status": job.status,
            "current_agent": job.current_agent,
        }


async def list_job_events(job_id: Union[str, uuid.UUID]) -> list[dict]:
    """List all persisted events for a job ordered by creation time."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobEvent)
            .where(JobEvent.job_id == _as_uuid(job_id))
            .order_by(JobEvent.created_at.asc(), JobEvent.id.asc())
        )
        events = result.scalars().all()
        return [
            {
                "event_id": str(event.id),
                "job_id": str(event.job_id) if event.job_id else None,
                "session_id": event.session_id,
                "event_type": event.event_type,
                "agent": event.agent,
                "status": event.status,
                "message": event.message,
                "payload": dict(event.payload or {}),
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]


async def get_generation_failure(session_id: str) -> Optional[dict]:
    """Build a user-facing failure summary from the latest failed job and its error event."""
    failed_job = await get_latest_failed_generation_job(session_id)
    if failed_job is None:
        return None

    events = await list_job_events(failed_job["job_id"])
    error_event = next(
        (
            event
            for event in reversed(events)
            if event["event_type"] == "error" or (event.get("payload") or {}).get("type") == "error"
        ),
        None,
    )
    payload = dict(error_event.get("payload") or {}) if error_event else {}

    return {
        "job_id": failed_job["job_id"],
        "session_id": session_id,
        "trigger": payload.get("retry_trigger") or failed_job["trigger"],
        "status": failed_job["status"],
        "current_agent": failed_job["current_agent"],
        "error_type": payload.get("error_type", "generation_failed"),
        "failure_stage": payload.get("failure_stage") or failed_job["current_agent"] or "workflow",
        "message": payload.get("user_message")
        or payload.get("message")
        or failed_job.get("error_message")
        or "Generation failed",
        "technical_message": payload.get("message")
        or failed_job.get("error_message")
        or "Generation failed",
        "recoverable": payload.get("recoverable", True),
        "retry_available": payload.get("retry_available", True),
        "retry_trigger": payload.get("retry_trigger") or failed_job["trigger"],
        "details": payload.get("details", {}),
        "failed_at": error_event["created_at"] if error_event else failed_job["updated_at"],
    }
