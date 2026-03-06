"""Unit tests for durable workflow state helpers."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import main


@pytest.mark.unit
class TestWorkflowStateHelpers:
    """Validate durable-state helper behavior."""

    @pytest.mark.asyncio
    async def test_load_session_state_prefers_durable_store_and_refreshes_cache(self, monkeypatch):
        state = {"current_status": "initialized", "current_agent": "planner"}
        load_state = AsyncMock(return_value=state)
        redis_get = AsyncMock(return_value={"current_status": "stale"})
        refresh_cache = AsyncMock()

        monkeypatch.setattr(main, "load_workflow_state", load_state)
        monkeypatch.setattr(main.redis_client, "get_session", redis_get)
        monkeypatch.setattr(main, "_cache_session_state", refresh_cache)

        result = await main._load_session_state("session-1")

        assert result == state
        load_state.assert_awaited_once_with("session-1")
        redis_get.assert_not_awaited()
        refresh_cache.assert_awaited_once_with("session-1", state)

    @pytest.mark.asyncio
    async def test_load_session_state_falls_back_to_redis_when_db_read_fails(self, monkeypatch):
        state = {"current_status": "waiting_for_outline_approval"}
        load_state = AsyncMock(side_effect=RuntimeError("db unavailable"))
        redis_get = AsyncMock(return_value=state)

        monkeypatch.setattr(main, "load_workflow_state", load_state)
        monkeypatch.setattr(main.redis_client, "get_session", redis_get)

        result = await main._load_session_state("session-2")

        assert result == state
        load_state.assert_awaited_once_with("session-2")
        redis_get.assert_awaited_once_with("session-2")

    @pytest.mark.asyncio
    async def test_load_session_state_falls_back_to_redis_when_db_has_no_record(self, monkeypatch):
        state = {"current_status": "initialized"}
        load_state = AsyncMock(return_value=None)
        redis_get = AsyncMock(return_value=state)
        refresh_cache = AsyncMock()

        monkeypatch.setattr(main, "load_workflow_state", load_state)
        monkeypatch.setattr(main.redis_client, "get_session", redis_get)
        monkeypatch.setattr(main, "_cache_session_state", refresh_cache)

        result = await main._load_session_state("session-3")

        assert result == state
        load_state.assert_awaited_once_with("session-3")
        redis_get.assert_awaited_once_with("session-3")
        refresh_cache.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_save_session_state_persists_before_refreshing_cache(self, monkeypatch):
        state = {"current_status": "created"}
        persist_state = AsyncMock(return_value=state)
        sync_project = AsyncMock()
        refresh_cache = AsyncMock()

        monkeypatch.setattr(main, "save_workflow_state", persist_state)
        monkeypatch.setattr(main, "sync_project_state", sync_project)
        monkeypatch.setattr(main, "_cache_session_state", refresh_cache)

        result = await main._save_session_state("session-4", state, project_id="11111111-1111-1111-1111-111111111111")

        assert result == state
        persist_state.assert_awaited_once_with(
            "session-4",
            state,
            project_id="11111111-1111-1111-1111-111111111111",
        )
        sync_project.assert_awaited_once_with("session-4", state)
        refresh_cache.assert_awaited_once_with("session-4", state)

    @pytest.mark.asyncio
    async def test_merge_session_state_refreshes_cache_with_persisted_result(self, monkeypatch):
        updates = {"current_status": "rendering"}
        merged = {"current_status": "rendering", "current_agent": "renderer"}
        update_state = AsyncMock(return_value=merged)
        sync_project = AsyncMock()
        refresh_cache = AsyncMock()

        monkeypatch.setattr(main, "update_workflow_state", update_state)
        monkeypatch.setattr(main, "sync_project_state", sync_project)
        monkeypatch.setattr(main, "_cache_session_state", refresh_cache)

        result = await main._merge_session_state("session-5", updates)

        assert result == merged
        update_state.assert_awaited_once_with("session-5", updates)
        sync_project.assert_awaited_once_with("session-5", merged)
        refresh_cache.assert_awaited_once_with("session-5", merged)

    @pytest.mark.asyncio
    async def test_merge_session_state_returns_none_for_missing_session(self, monkeypatch):
        update_state = AsyncMock(return_value=None)
        refresh_cache = AsyncMock()

        monkeypatch.setattr(main, "update_workflow_state", update_state)
        monkeypatch.setattr(main, "_cache_session_state", refresh_cache)

        result = await main._merge_session_state("missing-session", {"current_status": "done"})

        assert result is None
        update_state.assert_awaited_once_with("missing-session", {"current_status": "done"})
        refresh_cache.assert_not_awaited()
