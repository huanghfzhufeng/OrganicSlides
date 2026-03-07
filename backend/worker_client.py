"""API-side client for dispatching jobs to the worker service."""

from __future__ import annotations

import httpx

from config import settings


async def dispatch_worker_job(session_id: str, trigger: str) -> dict:
    """Tell the worker service to start or resume a workflow job."""
    endpoint = "start" if trigger == "start_workflow" else "resume"
    timeout = settings.WORKER_REQUEST_TIMEOUT_SECONDS

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.WORKER_BASE_URL}/internal/jobs/{endpoint}",
            json={"session_id": session_id},
        )
        response.raise_for_status()
        return response.json()
