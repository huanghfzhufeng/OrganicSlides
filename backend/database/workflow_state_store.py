"""
Workflow state persistence helpers.

This module persists the latest workflow state in PostgreSQL so generation can
survive API process restarts. Redis may still be used as a cache, but the
database is the durable source for the latest session state.
"""

import uuid
from typing import Optional, Union

from sqlalchemy import select

from database.models import WorkflowSession
from database.postgres import AsyncSessionLocal


async def load_workflow_state(session_id: str) -> Optional[dict]:
    """Load the latest persisted workflow state for a session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkflowSession).where(WorkflowSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        return dict(session.state) if session else None


async def save_workflow_state(
    session_id: str,
    state: dict,
    project_id: Optional[Union[str, uuid.UUID]] = None,
) -> dict:
    """Insert or replace the latest persisted workflow state for a session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkflowSession).where(WorkflowSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()

        if session is None:
            session = WorkflowSession(session_id=session_id)
            db.add(session)

        if project_id and session.project_id is None:
            session.project_id = uuid.UUID(str(project_id))

        session.status = state.get("current_status", "initialized")
        session.current_agent = state.get("current_agent", "")
        session.state = dict(state)

        await db.commit()
        return dict(session.state)


async def update_workflow_state(session_id: str, updates: dict) -> Optional[dict]:
    """Merge updates into the latest persisted workflow state."""
    current = await load_workflow_state(session_id)
    if current is None:
        return None

    current.update(updates)
    return await save_workflow_state(session_id, current)
