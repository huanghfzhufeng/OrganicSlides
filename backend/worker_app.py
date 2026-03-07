"""Internal worker service entrypoint."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app_lifecycle import build_lifespan
from worker_runtime import start_worker_job


class WorkerJobRequest(BaseModel):
    session_id: str


app = FastAPI(
    title="MAS-PPT Worker",
    description="Internal worker service for workflow execution",
    version="1.0.0",
    lifespan=build_lifespan("MAS-PPT Worker"),
)


@app.get("/")
async def root():
    return {"service": "worker", "status": "ok"}


@app.post("/internal/jobs/start")
async def start_job(request: WorkerJobRequest):
    try:
        job = await start_worker_job(request.session_id, "start_workflow")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return job


@app.post("/internal/jobs/resume")
async def resume_job(request: WorkerJobRequest):
    try:
        job = await start_worker_job(request.session_id, "resume_workflow")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return job


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("worker_app:app", host="0.0.0.0", port=8001, reload=True)
