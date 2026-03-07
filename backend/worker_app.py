"""Internal worker service entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app_lifecycle import build_lifespan
from job_queue import enqueue_generation_job
from worker_runtime import consume_generation_queue


class WorkerJobRequest(BaseModel):
    session_id: str


_shared_lifespan = build_lifespan("MAS-PPT Worker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    async with _shared_lifespan(app):
        consumer_task = asyncio.create_task(consume_generation_queue(stop_event))
        app.state.consumer_task = consumer_task
        app.state.stop_event = stop_event
        try:
            yield
        finally:
            stop_event.set()
            consumer_task.cancel()
            await asyncio.gather(consumer_task, return_exceptions=True)


app = FastAPI(
    title="MAS-PPT Worker",
    description="Internal worker service for workflow execution",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {"service": "worker", "status": "ok", "mode": "queue-consumer"}


@app.post("/internal/jobs/start")
async def start_job(request: WorkerJobRequest):
    try:
        job = await enqueue_generation_job(request.session_id, "start_workflow", source="worker_api")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return job


@app.post("/internal/jobs/resume")
async def resume_job(request: WorkerJobRequest):
    try:
        job = await enqueue_generation_job(request.session_id, "resume_workflow", source="worker_api")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return job


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("worker_app:app", host="0.0.0.0", port=8001, reload=True)
