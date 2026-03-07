"""Unit tests for stored-asset metadata and cleanup jobs."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import asset_jobs
from agents.renderer import agent as renderer_agent
from agents.renderer.paths import SlideRenderResult
from services.object_storage import StoredObject


@pytest.mark.unit
class TestAssetCleanupJobs:
    @pytest.mark.asyncio
    async def test_cleanup_expired_assets_deletes_and_marks_assets(self, monkeypatch):
        stop_event = asyncio.Event()
        deleted_keys: list[str] = []

        async def fake_sleep(_seconds):
            stop_event.set()

        class FakeStorage:
            def delete_object(self, key: str):
                deleted_keys.append(key)

        monkeypatch.setattr(
            asset_jobs,
            "list_expired_assets",
            AsyncMock(
                return_value=[
                    {
                        "asset_id": "11111111-1111-1111-1111-111111111111",
                        "session_id": "session-1",
                        "asset_type": "thumbnail",
                        "object_key": "sessions/session-1/runs/run-1/thumbnails/thumb_001.jpg",
                    }
                ]
            ),
        )
        monkeypatch.setattr(asset_jobs, "mark_asset_deleted", AsyncMock())
        monkeypatch.setattr(asset_jobs, "mark_asset_cleanup_failed", AsyncMock())
        monkeypatch.setattr(asset_jobs, "get_object_storage", lambda: FakeStorage())
        monkeypatch.setattr(asset_jobs.asyncio, "sleep", fake_sleep)

        await asset_jobs.cleanup_expired_assets(stop_event)

        assert deleted_keys == ["sessions/session-1/runs/run-1/thumbnails/thumb_001.jpg"]
        asset_jobs.mark_asset_deleted.assert_awaited_once_with(
            "11111111-1111-1111-1111-111111111111"
        )


@pytest.mark.unit
class TestRendererAssetMetadata:
    @pytest.mark.asyncio
    async def test_persist_slide_outputs_records_asset_metadata(self, monkeypatch, tmp_path):
        thumb_path = tmp_path / "thumb.jpg"
        thumb_path.write_bytes(b"thumb")

        upload = AsyncMock(
            side_effect=[
                StoredObject(
                    key="sessions/session-1/runs/run-1/slides/slide_001.png",
                    url="http://localhost:8000/api/v1/assets/sessions/session-1/runs/run-1/slides/slide_001.png",
                    content_type="image/png",
                    size=100,
                ),
                StoredObject(
                    key="sessions/session-1/runs/run-1/thumbnails/thumb_001.jpg",
                    url="http://localhost:8000/api/v1/assets/sessions/session-1/runs/run-1/thumbnails/thumb_001.jpg",
                    content_type="image/jpeg",
                    size=25,
                ),
                StoredObject(
                    key="sessions/session-1/runs/run-1/slides/slide_002.pptx",
                    url="http://localhost:8000/api/v1/assets/sessions/session-1/runs/run-1/slides/slide_002.pptx",
                    content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    size=200,
                ),
            ]
        )
        record_asset = AsyncMock()

        monkeypatch.setattr(renderer_agent, "_upload_file_to_object_storage", upload)
        monkeypatch.setattr(renderer_agent, "record_stored_asset", record_asset)
        monkeypatch.setattr(renderer_agent, "_generate_thumbnail_async", AsyncMock(return_value=str(thumb_path)))

        results = [
            SlideRenderResult(0, "path_b", output_path="/tmp/slide_001.png"),
            SlideRenderResult(1, "path_a", output_path="/tmp/slide_002.pptx"),
            SlideRenderResult(2, "path_b", error="render failed"),
        ]

        slide_files, progress_events = await renderer_agent._persist_slide_outputs(
            results,
            "session-1",
            3,
            "run-1",
            [
                {"title": "Illustrated opener"},
                {"title": "Editorial detail"},
                {"title": "Broken slide"},
            ],
        )

        assert len(slide_files) == 2
        assert slide_files[0]["title"] == "Illustrated opener"
        assert slide_files[0]["storage_key"].endswith("slide_001.png")
        assert slide_files[0]["thumbnail_storage_key"].endswith("thumb_001.jpg")
        assert slide_files[1]["type"] == "html"
        assert [event["status"] for event in progress_events] == ["complete", "complete", "failed"]
        assert progress_events[0]["slide_title"] == "Illustrated opener"
        assert progress_events[0]["slide_index"] == 0
        assert record_asset.await_count == 3
