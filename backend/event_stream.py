"""SSE helpers for streaming persisted generation job events."""

from __future__ import annotations

import asyncio
import json

from database.project_tracking_store import get_generation_job, list_job_events


_TERMINAL_JOB_STATUSES = {"completed", "error"}


async def stream_job_events(job_id: str):
    """Yield SSE chunks by polling persisted job events for a generation job."""
    seen_event_ids: set[str] = set()
    emitted_terminal_event = False

    while True:
        events = await list_job_events(job_id)
        for event in events:
            event_id = event["event_id"]
            if event_id in seen_event_ids:
                continue

            seen_event_ids.add(event_id)
            payload = dict(event.get("payload") or {})
            if "type" not in payload:
                payload["type"] = event.get("event_type", "status")

            if payload.get("type") in {"complete", "error", "hitl"}:
                emitted_terminal_event = True

            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        job = await get_generation_job(job_id)
        if job and job["status"] in _TERMINAL_JOB_STATUSES:
            if not emitted_terminal_event:
                fallback_payload = _fallback_terminal_payload(job)
                yield f"data: {json.dumps(fallback_payload, ensure_ascii=False)}\n\n"
            break

        await asyncio.sleep(0.1)


def _fallback_terminal_payload(job: dict) -> dict:
    if job["status"] == "error":
        return {
            "type": "error",
            "status": "error",
            "message": job.get("error_message") or "Worker job failed",
        }
    payload = {"type": "complete", "status": "done"}
    if job.get("pptx_path"):
        payload["pptx_path"] = job["pptx_path"]
    return payload
