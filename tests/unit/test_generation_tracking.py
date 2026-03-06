"""Unit tests for generation job and event tracking orchestration."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import main


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


@pytest.mark.unit
class TestGenerationTracking:
    @pytest.mark.asyncio
    async def test_generate_sse_events_tracks_job_events_and_outline_revision(self, monkeypatch):
        initial_state = {
            "session_id": "session-1",
            "current_status": "initialized",
            "current_agent": "",
            "outline": [],
            "messages": [],
        }
        final_state = {
            "session_id": "session-1",
            "current_status": "waiting_for_outline_approval",
            "current_agent": "hitl",
            "outline": [{"id": "1", "title": "Test assertion"}],
        }

        create_job = AsyncMock(return_value={"job_id": "job-1"})
        update_job = AsyncMock()
        record_event = AsyncMock()
        create_revision = AsyncMock()
        merge_state = AsyncMock(side_effect=[
            {
                **initial_state,
                "current_status": "planning",
                "current_agent": "planner",
                "outline": [{"id": "1", "title": "Test assertion"}],
            },
            final_state,
        ])
        load_state = AsyncMock(return_value=final_state)

        monkeypatch.setattr(main, "get_main_app", lambda: FakeMainApp())
        monkeypatch.setattr(main, "create_generation_job", create_job)
        monkeypatch.setattr(main, "update_generation_job", update_job)
        monkeypatch.setattr(main, "record_job_event", record_event)
        monkeypatch.setattr(main, "create_project_revision", create_revision)
        monkeypatch.setattr(main, "_merge_session_state", merge_state)
        monkeypatch.setattr(main, "_load_session_state", load_state)

        chunks = [chunk async for chunk in main.generate_sse_events("session-1", initial_state)]
        payloads = _decode_sse_payloads(chunks)

        assert [payload["type"] for payload in payloads] == ["status", "status", "hitl"]
        create_job.assert_awaited_once_with("session-1", "start_workflow", dict(initial_state))
        assert record_event.await_count == 3
        update_job.assert_any_await(
            "job-1",
            state=final_state,
            status="waiting_for_outline_approval",
        )
        create_revision.assert_awaited_once_with("session-1", "outline_generated", final_state)

    @pytest.mark.asyncio
    async def test_generate_resume_sse_events_tracks_completion_and_render_events(self, monkeypatch):
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

        create_job = AsyncMock(return_value={"job_id": "job-2"})
        update_job = AsyncMock()
        record_event = AsyncMock()
        create_revision = AsyncMock()
        save_state = AsyncMock()
        merge_state = AsyncMock(return_value=final_state)
        load_state = AsyncMock(side_effect=[dict(initial_state), final_state])

        monkeypatch.setattr(main, "get_resume_app", lambda: FakeResumeApp())
        monkeypatch.setattr(main, "create_generation_job", create_job)
        monkeypatch.setattr(main, "update_generation_job", update_job)
        monkeypatch.setattr(main, "record_job_event", record_event)
        monkeypatch.setattr(main, "create_project_revision", create_revision)
        monkeypatch.setattr(main, "_save_session_state", save_state)
        monkeypatch.setattr(main, "_merge_session_state", merge_state)
        monkeypatch.setattr(main, "_load_session_state", load_state)

        chunks = [chunk async for chunk in main.generate_resume_sse_events("session-2")]
        payloads = _decode_sse_payloads(chunks)

        assert [payload["type"] for payload in payloads] == [
            "status",
            "render_progress",
            "complete",
        ]
        assert save_state.await_args.args[1]["outline_approved"] is True
        create_job.assert_awaited_once()
        assert record_event.await_count == 3
        update_job.assert_any_await("job-2", state=final_state, status="completed")
        create_revision.assert_awaited_once_with("session-2", "generation_completed", final_state)
