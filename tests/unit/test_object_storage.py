"""Unit tests for object storage backends and public URLs."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from services import object_storage


@pytest.mark.unit
class TestObjectStorage:
    @pytest.fixture(autouse=True)
    def reset_storage(self):
        object_storage.reset_object_storage()
        yield
        object_storage.reset_object_storage()

    def test_local_object_storage_uploads_and_reads_files(self, monkeypatch, tmp_path):
        monkeypatch.setattr(object_storage.settings, "OBJECT_STORAGE_BACKEND", "local")
        monkeypatch.setattr(object_storage.settings, "OBJECT_STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
        monkeypatch.setattr(
            object_storage.settings,
            "OBJECT_STORAGE_PUBLIC_BASE_URL",
            "http://localhost:8000/api/v1/assets",
        )
        object_storage.reset_object_storage()

        source = tmp_path / "presentation.pptx"
        source.write_bytes(b"pptx-data")

        storage = object_storage.get_object_storage()
        storage.init()
        stored = storage.upload_file(
            source,
            "sessions/demo/presentations/presentation_demo.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        payload, content_type = storage.read_object(stored.key)

        assert payload == b"pptx-data"
        assert content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        assert stored.url == (
            "http://localhost:8000/api/v1/assets/sessions/demo/presentations/presentation_demo.pptx"
        )

    def test_local_object_storage_uploads_bytes(self, monkeypatch, tmp_path):
        monkeypatch.setattr(object_storage.settings, "OBJECT_STORAGE_BACKEND", "local")
        monkeypatch.setattr(object_storage.settings, "OBJECT_STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
        monkeypatch.setattr(
            object_storage.settings,
            "OBJECT_STORAGE_PUBLIC_BASE_URL",
            "http://localhost:8000/api/v1/assets",
        )
        object_storage.reset_object_storage()

        storage = object_storage.get_object_storage()
        storage.init()
        stored = storage.upload_bytes(
            b"thumbnail-bytes",
            "sessions/demo/thumbnails/thumb_001.jpg",
            "image/jpeg",
        )
        payload, content_type = storage.read_object(stored.key)

        assert payload == b"thumbnail-bytes"
        assert content_type == "image/jpeg"
        assert stored.size == len(b"thumbnail-bytes")
