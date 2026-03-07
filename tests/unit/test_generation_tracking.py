"""Unit tests for queued generation orchestration and worker consumption."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import event_stream
import main
import worker_app
import worker_runtime


def _decode_sse_payloads(chunks):
    payloads = []
    for chunk in chunks:
        assert chunk.startswith("data: ")
        payload = chunk.replace("data: ", "", 1).strip()
        payloads.append(json.loads(payload))
    return payloads


class FakeMainApp:
    async def astream(self, state, config):
        yield {
            "planner": {
                "current_status": "planning",
                "current_agent": "planner",
                "messages": [{"content": "大纲规划完成"}],
                "outline": [{"id": "1", "title": "Test assertion"}],
            }
        }
        yield {
            "wait_for_approval": {
                "current_status": "waiting_for_outline_approval",
                "current_agent": "hitl",
                "messages": [{"content": "等待用户确认大纲..."}],
                "outline": [{"id": "1", "title": "Test assertion"}],
            }
        }


class FakeResumeApp:
    async def astream(self, state, config):
        yield {
            "renderer": {
                "current_status": "render_complete",
                "current_agent": "renderer",
                "messages": [{"content": "渲染完成"}],
                "pptx_path": "/tmp/demo.pptx",
                "render_progress_events": [
                    {
                        "type": "render_progress",
                        "slide_number": 1,
                        "total_slides": 1,
                        "render_path": "path_a",
                        "status": "complete",
                    }
                ],
            }
        }


class FakeErrorResumeApp:
    async def astream(self, state, config):
        yield {
            "writer": {
                "current_status": "writer_error",
                "current_agent": "writer",
                "error": "writer parse failed",
                "messages": [{"content": "Writer failed"}],
            }
        }
        yield {
            "error": {
                "current_status": "error",
                "current_agent": "error_handler",
                "error": "writer parse failed",
                "messages": [{"content": "工作流错误: writer parse failed"}],
            }
        }


@pytest.mark.unit
class TestApiQueueProxy:
    @pytest.mark.asyncio
    async def test_generate_sse_events_streams_job_events(self, monkeypatch):
        async def fake_stream(job_id):
            assert job_id == "job-1"
            yield "data: {\"type\":\"status\",\"status\":\"queued\"}\n\n"
            yield "data: {\"type\":\"hitl\",\"status\":\"waiting_for_approval\"}\n\n"

        monkeypatch.setattr(main, "stream_job_events", fake_stream)

        chunks = [chunk async for chunk in main.generate_sse_events("job-1")]
        payloads = _decode_sse_payloads(chunks)

        assert [payload["type"] for payload in payloads] == ["status", "hitl"]

    @pytest.mark.asyncio
    async def test_generate_resume_sse_events_streams_job_events(self, monkeypatch):
        async def fake_stream(job_id):
            assert job_id == "job-2"
            yield "data: {\"type\":\"status\",\"status\":\"running\"}\n\n"
            yield "data: {\"type\":\"complete\",\"status\":\"done\"}\n\n"

        monkeypatch.setattr(main, "stream_job_events", fake_stream)

        chunks = [chunk async for chunk in main.generate_resume_sse_events("job-2")]
        payloads = _decode_sse_payloads(chunks)

        assert [payload["type"] for payload in payloads] == ["status", "complete"]

    @pytest.mark.asyncio
    async def test_enqueue_worker_job_returns_queued_job(self, monkeypatch):
        enqueue = AsyncMock(
            return_value={
                "job_id": "job-queue",
                "status": "queued",
                "trigger": "start_workflow",
            }
        )
        monkeypatch.setattr(main, "enqueue_generation_job", enqueue)

        result = await main._enqueue_worker_job("session-1", "start_workflow")

        assert result["job_id"] == "job-queue"
        enqueue.assert_awaited_once_with("session-1", "start_workflow", source="api")

    @pytest.mark.asyncio
    async def test_enqueue_worker_job_maps_missing_session_to_404(self, monkeypatch):
        enqueue = AsyncMock(side_effect=ValueError("Session not found"))
        monkeypatch.setattr(main, "enqueue_generation_job", enqueue)

        with pytest.raises(HTTPException) as exc:
            await main._enqueue_worker_job("missing-session", "start_workflow")

        assert exc.value.status_code == 404
        assert exc.value.detail == "Session not found"


@pytest.mark.unit
class TestQueueConsumerAndWorkerRuntime:
    @pytest.mark.asyncio
    async def test_consume_generation_queue_claims_and_executes_jobs(self, monkeypatch):
        stop_event = worker_runtime.asyncio.Event()
        execute = AsyncMock(side_effect=lambda *args, **kwargs: stop_event.set())
        claim = AsyncMock(
            side_effect=[
                {
                    "job_id": "job-1",
                    "session_id": "session-1",
                    "trigger": "start_workflow",
                    "status": "starting",
                }
            ]
        )
        record_event = AsyncMock()

        monkeypatch.setattr(worker_runtime, "claim_next_generation_job", claim)
        monkeypatch.setattr(worker_runtime, "record_job_event", record_event)
        monkeypatch.setattr(worker_runtime, "execute_generation_job", execute)
        monkeypatch.setattr(worker_runtime.asyncio, "sleep", AsyncMock(return_value=None))

        await worker_runtime.consume_generation_queue(stop_event)

        execute.assert_awaited_once_with("session-1", "job-1", "start_workflow")
        record_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_generation_job_tracks_outline_revision(self, monkeypatch):
        initial_state = {
            "session_id": "session-1",
            "current_status": "initialized",
            "current_agent": "",
            "outline": [],
            "messages": [],
        }
        planner_state = {
            **initial_state,
            "current_status": "planning",
            "current_agent": "planner",
            "outline": [{"id": "1", "title": "Test assertion"}],
        }
        final_state = {
            "session_id": "session-1",
            "current_status": "waiting_for_outline_approval",
            "current_agent": "hitl",
            "outline": [{"id": "1", "title": "Test assertion"}],
        }

        update_job = AsyncMock()
        record_event = AsyncMock()
        create_revision = AsyncMock()
        merge_state = AsyncMock(side_effect=[planner_state, final_state])
        load_state = AsyncMock(side_effect=[dict(initial_state), final_state])

        monkeypatch.setattr(worker_runtime, "get_main_app", lambda: FakeMainApp())
        monkeypatch.setattr(worker_runtime, "update_generation_job", update_job)
        monkeypatch.setattr(worker_runtime, "record_job_event", record_event)
        monkeypatch.setattr(worker_runtime, "create_project_revision", create_revision)
        monkeypatch.setattr(worker_runtime, "_merge_session_state", merge_state)
        monkeypatch.setattr(worker_runtime, "_load_session_state", load_state)
        monkeypatch.setattr(worker_runtime.asyncio, "sleep", AsyncMock(return_value=None))

        await worker_runtime.execute_generation_job("session-1", "job-1", "start_workflow")

        assert record_event.await_count == 3
        update_job.assert_any_await("job-1", state=dict(initial_state), status="running")
        update_job.assert_any_await(
            "job-1",
            state=final_state,
            status="waiting_for_outline_approval",
        )
        create_revision.assert_awaited_once_with(
            "session-1",
            "outline_generated",
            final_state,
        )

    @pytest.mark.asyncio
    async def test_execute_resume_generation_tracks_completion_and_render_events(self, monkeypatch):
        initial_state = {
            "session_id": "session-2",
            "current_status": "waiting_for_outline_approval",
            "current_agent": "hitl",
            "outline_approved": False,
            "messages": [],
        }
        final_state = {
            "session_id": "session-2",
            "current_status": "render_complete",
            "current_agent": "renderer",
            "pptx_path": "/tmp/demo.pptx",
        }

        update_job = AsyncMock()
        record_event = AsyncMock()
        create_revision = AsyncMock()
        save_state = AsyncMock()
        merge_state = AsyncMock(return_value=final_state)
        load_state = AsyncMock(side_effect=[dict(initial_state), final_state])

        monkeypatch.setattr(worker_runtime, "get_resume_app", lambda: FakeResumeApp())
        monkeypatch.setattr(worker_runtime, "update_generation_job", update_job)
        monkeypatch.setattr(worker_runtime, "record_job_event", record_event)
        monkeypatch.setattr(worker_runtime, "create_project_revision", create_revision)
        monkeypatch.setattr(worker_runtime, "_save_session_state", save_state)
        monkeypatch.setattr(worker_runtime, "_merge_session_state", merge_state)
        monkeypatch.setattr(worker_runtime, "_load_session_state", load_state)
        monkeypatch.setattr(worker_runtime.asyncio, "sleep", AsyncMock(return_value=None))

        await worker_runtime.execute_generation_job("session-2", "job-2", "resume_workflow")

        assert save_state.await_args.args[1]["outline_approved"] is True
        assert record_event.await_count == 3
        update_job.assert_any_await("job-2", state=final_state, status="completed")
        create_revision.assert_awaited_once_with(
            "session-2",
            "generation_completed",
            final_state,
        )

    @pytest.mark.asyncio
    async def test_execute_resume_generation_tracks_error_state(self, monkeypatch):
        initial_state = {
            "session_id": "session-3",
            "current_status": "waiting_for_outline_approval",
            "current_agent": "hitl",
            "outline_approved": False,
            "messages": [],
        }
        writer_error_state = {
            "session_id": "session-3",
            "current_status": "writer_error",
            "current_agent": "writer",
            "error": "writer parse failed",
        }
        final_state = {
            "session_id": "session-3",
            "current_status": "error",
            "current_agent": "error_handler",
            "error": "writer parse failed",
        }

        update_job = AsyncMock()
        record_event = AsyncMock()
        create_revision = AsyncMock()
        save_state = AsyncMock()
        merge_state = AsyncMock(side_effect=[writer_error_state, final_state])
        load_state = AsyncMock(side_effect=[dict(initial_state), final_state])

        monkeypatch.setattr(worker_runtime, "get_resume_app", lambda: FakeErrorResumeApp())
        monkeypatch.setattr(worker_runtime, "update_generation_job", update_job)
        monkeypatch.setattr(worker_runtime, "record_job_event", record_event)
        monkeypatch.setattr(worker_runtime, "create_project_revision", create_revision)
        monkeypatch.setattr(worker_runtime, "_save_session_state", save_state)
        monkeypatch.setattr(worker_runtime, "_merge_session_state", merge_state)
        monkeypatch.setattr(worker_runtime, "_load_session_state", load_state)
        monkeypatch.setattr(worker_runtime.asyncio, "sleep", AsyncMock(return_value=None))

        await worker_runtime.execute_generation_job("session-3", "job-3", "resume_workflow")

        assert record_event.await_count == 3
        update_job.assert_any_await(
            "job-3",
            state=final_state,
            status="error",
            error_message="writer parse failed",
        )
        create_revision.assert_awaited_once_with(
            "session-3",
            "generation_failed",
            final_state,
        )


@pytest.mark.unit
class TestWorkerServiceAndEventStream:
    @pytest.mark.asyncio
    async def test_worker_start_endpoint_enqueues_job(self, monkeypatch):
        enqueue = AsyncMock(
            return_value={
                "job_id": "job-start",
                "status": "queued",
                "trigger": "start_workflow",
            }
        )
        monkeypatch.setattr(worker_app, "enqueue_generation_job", enqueue)

        response = await worker_app.start_job(worker_app.WorkerJobRequest(session_id="session-1"))

        assert response["job_id"] == "job-start"
        enqueue.assert_awaited_once_with("session-1", "start_workflow", source="worker_api")

    @pytest.mark.asyncio
    async def test_worker_resume_endpoint_raises_404_for_missing_session(self, monkeypatch):
        enqueue = AsyncMock(side_effect=ValueError("Session not found"))
        monkeypatch.setattr(worker_app, "enqueue_generation_job", enqueue)

        with pytest.raises(HTTPException) as exc:
            await worker_app.resume_job(worker_app.WorkerJobRequest(session_id="missing"))

        assert exc.value.status_code == 404
        assert exc.value.detail == "Session not found"

    @pytest.mark.asyncio
    async def test_stream_job_events_emits_fallback_complete_event(self, monkeypatch):
        list_events = AsyncMock(
            side_effect=[
                [
                    {
                        "event_id": "event-1",
                        "event_type": "status",
                        "payload": {
                            "type": "status",
                            "status": "queued",
                            "message": "queued",
                        },
                    }
                ],
                [
                    {
                        "event_id": "event-1",
                        "event_type": "status",
                        "payload": {
                            "type": "status",
                            "status": "queued",
                            "message": "queued",
                        },
                    }
                ],
            ]
        )
        get_job = AsyncMock(
            side_effect=[
                {"job_id": "job-1", "status": "running", "pptx_path": ""},
                {"job_id": "job-1", "status": "completed", "pptx_path": "/tmp/demo.pptx"},
            ]
        )

        monkeypatch.setattr(event_stream, "list_job_events", list_events)
        monkeypatch.setattr(event_stream, "get_generation_job", get_job)
        monkeypatch.setattr(event_stream.asyncio, "sleep", AsyncMock(return_value=None))

        chunks = [chunk async for chunk in event_stream.stream_job_events("job-1")]
        payloads = _decode_sse_payloads(chunks)

        assert [payload["type"] for payload in payloads] == ["status", "complete"]
        assert payloads[-1]["pptx_path"] == "/tmp/demo.pptx"
