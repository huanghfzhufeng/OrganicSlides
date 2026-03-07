"""Unit tests for durable workflow state helpers."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import app_lifecycle
import main


@pytest.mark.unit
class TestWorkflowStateHelpers:
    """Validate durable-state helper behavior."""

    @pytest.mark.asyncio
    async def test_load_session_state_uses_durable_store_only(self, monkeypatch):
        state = {"current_status": "initialized", "current_agent": "planner"}
        load_state = AsyncMock(return_value=state)

        monkeypatch.setattr(main, "load_workflow_state", load_state)

        result = await main._load_session_state("session-1")

        assert result == state
        load_state.assert_awaited_once_with("session-1")

    @pytest.mark.asyncio
    async def test_load_session_state_returns_none_when_no_db_record_exists(self, monkeypatch):
        load_state = AsyncMock(return_value=None)

        monkeypatch.setattr(main, "load_workflow_state", load_state)

        result = await main._load_session_state("session-2")

        assert result is None
        load_state.assert_awaited_once_with("session-2")

    @pytest.mark.asyncio
    async def test_save_session_state_persists_and_syncs_project(self, monkeypatch):
        state = {"current_status": "created"}
        persist_state = AsyncMock(return_value=state)
        sync_project = AsyncMock()

        monkeypatch.setattr(main, "save_workflow_state", persist_state)
        monkeypatch.setattr(main, "sync_project_state", sync_project)

        result = await main._save_session_state("session-4", state, project_id="11111111-1111-1111-1111-111111111111")

        assert result == state
        persist_state.assert_awaited_once_with(
            "session-4",
            state,
            project_id="11111111-1111-1111-1111-111111111111",
        )
        sync_project.assert_awaited_once_with("session-4", state)

    @pytest.mark.asyncio
    async def test_merge_session_state_persists_updates_and_syncs_project(self, monkeypatch):
        updates = {"current_status": "rendering"}
        merged = {"current_status": "rendering", "current_agent": "renderer"}
        update_state = AsyncMock(return_value=merged)
        sync_project = AsyncMock()

        monkeypatch.setattr(main, "update_workflow_state", update_state)
        monkeypatch.setattr(main, "sync_project_state", sync_project)

        result = await main._merge_session_state("session-5", updates)

        assert result == merged
        update_state.assert_awaited_once_with("session-5", updates)
        sync_project.assert_awaited_once_with("session-5", merged)

    @pytest.mark.asyncio
    async def test_merge_session_state_returns_none_for_missing_session(self, monkeypatch):
        update_state = AsyncMock(return_value=None)

        monkeypatch.setattr(main, "update_workflow_state", update_state)

        result = await main._merge_session_state("missing-session", {"current_status": "done"})

        assert result is None
        update_state.assert_awaited_once_with("missing-session", {"current_status": "done"})

    @pytest.mark.asyncio
    async def test_connect_optional_redis_returns_false_when_unavailable(self, monkeypatch):
        connect = AsyncMock(side_effect=RuntimeError("redis down"))

        monkeypatch.setattr(app_lifecycle.redis_client, "connect", connect)

        result = await app_lifecycle._connect_optional_redis()

        assert result is False
        connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_optional_redis_swallow_errors(self, monkeypatch):
        disconnect = AsyncMock(side_effect=RuntimeError("redis down"))

        monkeypatch.setattr(app_lifecycle.redis_client, "disconnect", disconnect)

        await app_lifecycle._disconnect_optional_redis()

        disconnect.assert_awaited_once()
