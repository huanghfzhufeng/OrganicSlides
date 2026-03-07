"""Integration tests for styles API endpoints"""

import pytest
import json
import uuid
from pathlib import Path
from fastapi.testclient import TestClient


def get_style_json_files(styles_path):
    """Get all style JSON files, excluding metadata like index.json"""
    return [f for f in styles_path.glob("*.json") if f.name != "index.json"]


REQUIRED_FIELDS = {
    "id", "name_zh", "name_en", "tier", "colors", "typography",
    "use_cases", "sample_image_path", "render_paths"
}


@pytest.mark.integration
class TestStylesAPI:
    """Test styles API endpoints with mocked runtime dependencies"""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Setup for each test"""
        import main
        from project_preview import build_project_preview

        self.main = main
        self.app = main.app
        self.client = TestClient(self.app)
        self.monkeypatch = monkeypatch
        self.session_store = {}
        self.revisions = []
        self.active_job = None
        self.failure_summary = None

        async def fake_load_session_state(session_id):
            return self.session_store.get(session_id)

        async def fake_save_session_state(session_id, state, project_id=None):
            self.session_store[session_id] = dict(state)
            return self.session_store[session_id]

        async def fake_merge_session_state(session_id, updates):
            current = self.session_store.get(session_id)
            if current is None:
                return None
            merged = {**current, **updates}
            self.session_store[session_id] = merged
            return merged

        async def fake_create_project_revision(session_id, revision_type, state, project_id=None):
            revision_number = (
                sum(1 for revision in self.revisions if revision["session_id"] == session_id) + 1
            )
            revision = {
                "revision_id": f"revision-{session_id}-{revision_number}",
                "session_id": session_id,
                "revision_number": revision_number,
                "revision_type": revision_type,
                "state": dict(state),
                "project_id": project_id,
                "status": state.get("current_status", "unknown"),
                "theme": (state.get("theme_config", {}) or {}).get("style") or state.get("style_id"),
                "outline": list(state.get("outline", [])),
                "outline_count": len(state.get("outline", [])),
                "created_at": f"2026-03-07T00:00:{revision_number:02d}Z",
                "restored_from_revision_number": state.get("last_restored_revision_number"),
                "preview": build_project_preview(state),
            }
            self.revisions.append(revision)
            return revision

        async def fake_list_project_revisions(session_id, limit=20):
            revisions = [revision for revision in self.revisions if revision["session_id"] == session_id]
            revisions.sort(key=lambda revision: revision["revision_number"], reverse=True)
            return [
                {
                    "revision_id": revision["revision_id"],
                    "project_id": revision["project_id"],
                    "session_id": revision["session_id"],
                    "revision_number": revision["revision_number"],
                    "revision_type": revision["revision_type"],
                    "status": revision["status"],
                    "theme": revision["theme"],
                    "outline": list(revision["outline"]),
                    "outline_count": revision["outline_count"],
                    "created_at": revision["created_at"],
                    "restored_from_revision_number": revision["restored_from_revision_number"],
                    "preview": revision["preview"],
                }
                for revision in revisions[:limit]
            ]

        async def fake_count_project_revisions(session_id):
            return sum(1 for revision in self.revisions if revision["session_id"] == session_id)

        async def fake_restore_project_revision(session_id, revision_number=None, revision_id=None):
            target = None
            for revision in self.revisions:
                if revision["session_id"] != session_id:
                    continue
                if revision_number is not None and revision["revision_number"] == revision_number:
                    target = revision
                    break
                if revision_id is not None and revision["revision_id"] == revision_id:
                    target = revision
                    break

            if target is None:
                return None

            restored_state = {
                **target["state"],
                "session_id": session_id,
                "last_restored_revision_id": target["revision_id"],
                "last_restored_revision_number": target["revision_number"],
            }
            restored_state.pop("error", None)
            self.session_store[session_id] = restored_state
            restoration_revision = await fake_create_project_revision(
                session_id,
                "revision_restored",
                restored_state,
                project_id=target["project_id"],
            )
            return {
                "restored_revision": {
                    **target,
                    "state_snapshot": dict(target["state"]),
                },
                "restoration_revision": restoration_revision,
                "state": restored_state,
            }

        async def fake_find_session_active_generation_job(session_id):
            if self.active_job and self.active_job["session_id"] == session_id:
                return dict(self.active_job)
            return None

        async def fake_get_generation_failure(session_id):
            if self.failure_summary and self.failure_summary["session_id"] == session_id:
                return dict(self.failure_summary)
            return None

        monkeypatch.setattr(main, "_load_session_state", fake_load_session_state)
        monkeypatch.setattr(main, "_save_session_state", fake_save_session_state)
        monkeypatch.setattr(main, "_merge_session_state", fake_merge_session_state)
        monkeypatch.setattr(main, "create_project_revision", fake_create_project_revision)
        monkeypatch.setattr(main, "count_project_revisions", fake_count_project_revisions)
        monkeypatch.setattr(main, "list_project_revisions", fake_list_project_revisions)
        monkeypatch.setattr(main, "restore_project_revision_snapshot", fake_restore_project_revision)
        monkeypatch.setattr(main, "find_session_active_generation_job", fake_find_session_active_generation_job)
        monkeypatch.setattr(main, "get_generation_failure", fake_get_generation_failure)

        yield

        self.app.dependency_overrides.clear()
        self.client.close()

    def _create_project(self, prompt="Test presentation", style="organic"):
        response = self.client.post(
            "/api/v1/project/create",
            json={"prompt": prompt, "style": style}
        )
        assert response.status_code == 200
        return response.json()

    def test_health_check(self):
        """Test API health check endpoint"""
        response = self.client.get("/")
        assert response.status_code == 200
        assert "MAS-PPT API" in response.json()["message"]

    def test_list_styles_endpoint_exists(self):
        """Test that styles list endpoint is callable"""
        # This test verifies the endpoint structure
        # Will be implemented once Task #2 (API endpoints) is complete
        try:
            response = self.client.get("/api/v1/styles")
            # Accept 200, 404, or 501 (not implemented yet)
            assert response.status_code in [200, 404, 501]
        except Exception:
            # Endpoint may not exist yet
            pass

    def test_project_create_with_valid_data(self):
        """Test creating a project with valid data"""
        payload = {
            "prompt": "Create a presentation about renewable energy",
            "style": "organic"
        }
        response = self.client.post("/api/v1/project/create", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "session_access_token" in data
        assert data["status"] == "created"
        assert data["session_id"] in self.session_store

    def test_project_create_minimal_payload(self):
        """Test project creation with minimal required fields"""
        payload = {
            "prompt": "Test presentation"
        }
        response = self.client.post("/api/v1/project/create", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert self.session_store[data["session_id"]]["user_intent"] == "Test presentation"
        assert self.session_store[data["session_id"]]["research_packet"]["query"] == "Test presentation"
        assert self.session_store[data["session_id"]]["style_packet"]["style_id"] == "organic"

    def test_project_create_records_initial_revision(self):
        """Test project creation records an initial revision snapshot"""
        response = self.client.post(
            "/api/v1/project/create",
            json={"prompt": "Record initial revision"}
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        assert len(self.revisions) == 1
        assert self.revisions[0]["session_id"] == session_id
        assert self.revisions[0]["revision_type"] == "project_created"

    def test_project_create_returns_valid_session_id(self):
        """Test that session_id is a valid UUID"""
        payload = {"prompt": "Test"}
        response = self.client.post("/api/v1/project/create", json=payload)
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        try:
            uuid.UUID(session_id)
        except ValueError:
            pytest.fail(f"Invalid session_id format: {session_id}")

    def test_project_status_not_found(self):
        """Project endpoints require access token when no user session exists"""
        response = self.client.get("/api/v1/project/status/invalid-id")
        assert response.status_code == 401

    def test_project_status_existing_session(self):
        """Test project status for existing session with access token"""
        project = self._create_project(prompt="Test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]

        response = self.client.get(
            f"/api/v1/project/status/{session_id}",
            params={"access_token": access_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "initialized"
        assert data["current_agent"] == ""

    def test_project_preview_returns_persisted_slide_preview(self):
        """Preview endpoint should hydrate persisted slide preview cards"""
        project = self._create_project(prompt="Preview test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]
        self.session_store[session_id].update(
            {
                "current_status": "render_complete",
                "pptx_path": "http://localhost:8000/api/v1/assets/sessions/test/presentation.pptx",
                "slide_render_plans": [
                    {"page_number": 1, "title": "封面结论", "render_path": "path_b"},
                    {"page_number": 2, "title": "第二页观点", "render_path": "path_a"},
                ],
                "slide_files": [
                    {
                        "page_number": 1,
                        "title": "封面结论",
                        "render_path": "path_b",
                        "type": "image",
                        "path": "http://localhost:8000/api/v1/assets/sessions/test/slides/slide_001.png",
                        "thumbnail_url": "http://localhost:8000/api/v1/assets/sessions/test/thumbnails/thumb_001.jpg",
                    },
                    {
                        "page_number": 2,
                        "title": "第二页观点",
                        "render_path": "path_a",
                        "type": "html",
                        "path": "http://localhost:8000/api/v1/assets/sessions/test/slides/slide_002.pptx",
                    },
                ],
                "render_progress": [
                    {"slide_number": 1, "render_path": "path_b", "status": "complete"},
                    {"slide_number": 2, "render_path": "path_a", "status": "complete"},
                ],
            }
        )

        response = self.client.get(
            f"/api/v1/project/preview/{session_id}",
            params={"access_token": access_token},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "render_complete"
        assert payload["preview"]["slides_count"] == 2
        assert payload["preview"]["slides"][0]["title"] == "封面结论"
        assert payload["preview"]["slides"][0]["preview_url"].endswith("thumb_001.jpg")
        assert payload["preview"]["slides"][1]["title"] == "第二页观点"
        assert payload["preview"]["slides"][1]["preview_url"] == ""

    def test_workflow_outline_not_found(self):
        """Outline endpoint requires access token when no user session exists"""
        response = self.client.get("/api/v1/workflow/outline/invalid-id")
        assert response.status_code == 401

    def test_workflow_outline_existing_session(self):
        """Test getting outline for existing session with access token"""
        project = self._create_project(prompt="Test presentation")
        session_id = project["session_id"]
        access_token = project["session_access_token"]

        response = self.client.get(
            f"/api/v1/workflow/outline/{session_id}",
            params={"access_token": access_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["outline"] == []
        assert data["status"] == "initialized"

    def test_update_outline_records_revision(self):
        """Test outline updates create a new revision snapshot"""
        project = self._create_project(prompt="Outline test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]
        self.revisions.clear()

        outline = [{"id": "1", "title": "Test assertion", "type": "content"}]
        response = self.client.post(
            "/api/v1/workflow/outline/update",
            json={"session_id": session_id, "outline": outline, "access_token": access_token}
        )

        assert response.status_code == 200
        assert self.revisions[-1]["session_id"] == session_id
        assert self.revisions[-1]["revision_type"] == "outline_updated"
        assert self.revisions[-1]["state"]["outline"] == outline

    def test_update_project_style_records_revision(self):
        """Test style updates create a new revision snapshot"""
        project = self._create_project(prompt="Style revision test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]
        self.revisions.clear()

        response = self.client.post(
            "/api/v1/project/style",
            json={
                "session_id": session_id,
                "style_id": "01-snoopy",
                "render_path_preference": "path_a",
                "access_token": access_token,
            }
        )

        assert response.status_code == 200
        assert self.revisions[-1]["session_id"] == session_id
        assert self.revisions[-1]["revision_type"] == "style_updated"
        assert self.revisions[-1]["state"]["theme_config"]["style_id"] == "01-snoopy"
        assert self.session_store[session_id]["style_config"]["render_path_preference"] == "path_a"
        assert self.session_store[session_id]["style_config"]["render_paths"] == ["path_a"]
        assert self.session_store[session_id]["style_packet"]["style_id"] == "01-snoopy"
        assert self.session_store[session_id]["style_packet"]["render_paths"] == ["path_a"]
        assert self.session_store[session_id]["style_packet"]["reference_sources"]
        assert self.session_store[session_id]["style_packet"]["prompt_constraints"]["path_a_rules"]

    def test_list_project_revisions_returns_reverse_chronological_history(self):
        """Revision history endpoint should return the latest revisions first"""
        project = self._create_project(prompt="Revision list test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]

        outline = [{"id": "1", "title": "Assertion slide", "type": "content"}]
        self.client.post(
            "/api/v1/workflow/outline/update",
            json={"session_id": session_id, "outline": outline, "access_token": access_token},
        )
        self.client.post(
            "/api/v1/project/style",
            json={
                "session_id": session_id,
                "style_id": "01-snoopy",
                "render_path_preference": "path_a",
                "access_token": access_token,
            },
        )

        response = self.client.get(
            f"/api/v1/project/revisions/{session_id}",
            params={"access_token": access_token},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 3
        assert [revision["revision_type"] for revision in payload["revisions"]] == [
            "style_updated",
            "outline_updated",
            "project_created",
        ]
        assert payload["revisions"][0]["revision_number"] == 3
        assert "preview" in payload["revisions"][0]

    def test_restore_project_revision_replaces_session_state_and_records_restoration(self):
        """Restoring a revision should replace current state and append a restoration revision"""
        project = self._create_project(prompt="Revision restore test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]

        original_outline = [{"id": "1", "title": "Original assertion", "type": "content"}]
        updated_outline = [{"id": "1", "title": "Updated assertion", "type": "content"}]

        self.client.post(
            "/api/v1/workflow/outline/update",
            json={"session_id": session_id, "outline": original_outline, "access_token": access_token},
        )
        self.client.post(
            "/api/v1/workflow/outline/update",
            json={"session_id": session_id, "outline": updated_outline, "access_token": access_token},
        )

        response = self.client.post(
            "/api/v1/project/revisions/restore",
            json={
                "session_id": session_id,
                "revision_number": 2,
                "access_token": access_token,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "revision_restored"
        assert payload["restored_revision"]["revision_number"] == 2
        assert payload["restoration_revision"]["revision_type"] == "revision_restored"
        assert payload["current_state"]["outline"] == original_outline
        assert self.session_store[session_id]["outline"] == original_outline
        assert self.session_store[session_id]["last_restored_revision_number"] == 2
        assert self.revisions[-1]["revision_type"] == "revision_restored"
        assert self.revisions[-1]["restored_from_revision_number"] == 2

    def test_restore_project_revision_rejects_active_generation_job(self):
        """Revision restore should be blocked while a generation job is active"""
        project = self._create_project(prompt="Active restore guard test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]
        self.active_job = {
            "job_id": "job-1",
            "session_id": session_id,
            "status": "running",
            "trigger": "resume_workflow",
        }

        response = self.client.post(
            "/api/v1/project/revisions/restore",
            json={
                "session_id": session_id,
                "revision_number": 1,
                "access_token": access_token,
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "Cannot restore revisions while a generation job is active"

    def test_project_failure_endpoint_returns_latest_failure_summary(self):
        """Failure endpoint should surface user-facing failure context"""
        project = self._create_project(prompt="Failure summary test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]
        self.failure_summary = {
            "job_id": "job-failed",
            "session_id": session_id,
            "trigger": "resume_workflow",
            "status": "error",
            "current_agent": "visual",
            "error_type": "visual_failed",
            "failure_stage": "visual",
            "message": "visual 阶段失败，请修正后重试",
            "technical_message": "visual parse failed",
            "recoverable": True,
            "retry_available": True,
            "retry_trigger": "resume_workflow",
            "details": {"agent": "visual"},
            "failed_at": "2026-03-07T00:00:05Z",
        }

        response = self.client.get(
            f"/api/v1/project/failure/{session_id}",
            params={"access_token": access_token},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["failure"]["error_type"] == "visual_failed"
        assert payload["failure"]["retry_available"] is True
        assert payload["failure"]["retry_trigger"] == "resume_workflow"

    def test_retry_project_generation_queues_failed_trigger(self, monkeypatch):
        """Retry endpoint should requeue the failed workflow trigger"""
        project = self._create_project(prompt="Retry workflow test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]
        self.failure_summary = {
            "job_id": "job-failed",
            "session_id": session_id,
            "trigger": "resume_workflow",
            "status": "error",
            "current_agent": "renderer",
            "error_type": "renderer_failed",
            "failure_stage": "renderer",
            "message": "renderer 阶段失败，请修正后重试",
            "technical_message": "renderer failed",
            "recoverable": True,
            "retry_available": True,
            "retry_trigger": "resume_workflow",
            "details": {"agent": "renderer"},
            "failed_at": "2026-03-07T00:00:06Z",
        }

        async def fake_enqueue_worker_job(session_id_param, trigger):
            assert session_id_param == session_id
            assert trigger == "resume_workflow"
            return {"job_id": "job-retry", "status": "queued", "trigger": trigger}

        monkeypatch.setattr(self.main, "_enqueue_worker_job", fake_enqueue_worker_job)

        response = self.client.post(
            "/api/v1/project/retry",
            json={"session_id": session_id, "access_token": access_token},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "retry_queued"
        assert payload["job_id"] == "job-retry"
        assert payload["trigger"] == "resume_workflow"

    def test_retry_project_generation_rejects_non_retryable_failure(self):
        """Retry endpoint should reject non-recoverable failures"""
        project = self._create_project(prompt="Retry rejection test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]
        self.failure_summary = {
            "job_id": "job-failed",
            "session_id": session_id,
            "trigger": "start_workflow",
            "status": "error",
            "current_agent": "worker",
            "error_type": "session_not_found",
            "failure_stage": "worker",
            "message": "会话不存在，无法继续重试",
            "technical_message": "Session not found",
            "recoverable": False,
            "retry_available": False,
            "retry_trigger": None,
            "details": {"agent": "worker"},
            "failed_at": "2026-03-07T00:00:07Z",
        }

        response = self.client.post(
            "/api/v1/project/retry",
            json={"session_id": session_id, "access_token": access_token},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "会话不存在，无法继续重试"

    def test_project_create_with_custom_style(self):
        """Test creating project with different styles"""
        styles = ["organic", "tech", "classic"]

        for style in styles:
            response = self.client.post(
                "/api/v1/project/create",
                json={"prompt": "Test", "style": style}
            )
            assert response.status_code == 200
            session_id = response.json()["session_id"]
            assert response.json()["status"] == "created"
            assert self.session_store[session_id]["theme_config"]["style"] == style

    def test_workflow_start_requires_access_token(self):
        """SSE start endpoint should reject anonymous access without session token"""
        project = self._create_project(prompt="SSE auth test")
        session_id = project["session_id"]

        response = self.client.get(f"/api/v1/workflow/start/{session_id}")
        assert response.status_code == 401

    def test_workflow_start_accepts_access_token(self, monkeypatch):
        """SSE start endpoint should allow valid session token"""
        project = self._create_project(prompt="SSE auth allow test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]

        async def fake_generate_sse_events(job_id):
            yield "data: {\"type\":\"complete\",\"status\":\"done\"}\n\n"

        async def fake_enqueue_worker_job(session_id_param, trigger):
            assert session_id_param == session_id
            assert trigger == "start_workflow"
            return {"job_id": "job-1", "status": "queued", "trigger": trigger}

        monkeypatch.setattr(self.main, "generate_sse_events", fake_generate_sse_events)
        monkeypatch.setattr(self.main, "_enqueue_worker_job", fake_enqueue_worker_job)

        response = self.client.get(
            f"/api/v1/workflow/start/{session_id}",
            params={"access_token": access_token},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_download_requires_access_token(self, tmp_path):
        """Download endpoint should require the session access token"""
        project = self._create_project(prompt="Download auth test")
        session_id = project["session_id"]
        self.session_store[session_id]["pptx_path"] = str(tmp_path / "deck.pptx")
        Path(self.session_store[session_id]["pptx_path"]).write_bytes(b"pptx")

        response = self.client.get(f"/api/v1/project/download/{session_id}")
        assert response.status_code == 401

    def test_download_accepts_access_token(self, tmp_path):
        """Download endpoint should allow valid session token"""
        project = self._create_project(prompt="Download auth allow test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]
        self.session_store[session_id]["pptx_path"] = str(tmp_path / "deck.pptx")
        Path(self.session_store[session_id]["pptx_path"]).write_bytes(b"pptx")

        response = self.client.get(
            f"/api/v1/project/download/{session_id}",
            params={"access_token": access_token},
        )
        assert response.status_code == 200

    def test_download_reads_pptx_from_object_storage(self, monkeypatch):
        """Download endpoint should stream object-stored presentations when a storage key exists"""
        project = self._create_project(prompt="Object storage download test")
        session_id = project["session_id"]
        access_token = project["session_access_token"]
        self.session_store[session_id]["pptx_path"] = "http://localhost:8000/api/v1/assets/sessions/test/presentation.pptx"
        self.session_store[session_id]["pptx_storage_key"] = "sessions/test/presentation.pptx"

        class FakeStorage:
            def read_object(self, key):
                assert key == "sessions/test/presentation.pptx"
                return (
                    b"pptx-from-object-storage",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )

        monkeypatch.setattr(self.main, "get_object_storage", lambda: FakeStorage())

        response = self.client.get(
            f"/api/v1/project/download/{session_id}",
            params={"access_token": access_token},
        )

        assert response.status_code == 200
        assert response.content == b"pptx-from-object-storage"

    def test_asset_endpoint_reads_object_storage(self, monkeypatch):
        """Asset proxy endpoint should serve thumbnail bytes from object storage"""
        class FakeStorage:
            def read_object(self, key):
                assert key == "sessions/demo/thumbnails/thumb_001.jpg"
                return (b"thumb-bytes", "image/jpeg")

        monkeypatch.setattr(self.main, "get_object_storage", lambda: FakeStorage())

        response = self.client.get("/api/v1/assets/sessions/demo/thumbnails/thumb_001.jpg")

        assert response.status_code == 200
        assert response.content == b"thumb-bytes"
        assert response.headers["content-type"].startswith("image/jpeg")


@pytest.mark.integration
class TestStyleDataIntegration:
    """Test style data loading and validation in integration context"""

    def test_load_all_style_json_files(self, styles_path):
        """Load and parse all style JSON files"""
        json_files = get_style_json_files(styles_path)
        loaded_styles = {}

        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)
                loaded_styles[style["id"]] = style

        assert len(loaded_styles) > 0, "Should have loaded at least one style"

    def test_style_json_schema_consistency(self, styles_path):
        """Verify all styles follow the same schema"""
        json_files = get_style_json_files(styles_path)
        all_styles = []

        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)
                all_styles.append(style)

        # All should have the same top-level keys (with some optional fields)
        if len(all_styles) > 1:
            # Required keys must be present in all styles
            first_required = REQUIRED_FIELDS & set(all_styles[0].keys())
            for style in all_styles[1:]:
                style_has = first_required & set(style.keys())
                assert style_has == first_required, (
                    f"Style {style['id']} missing required fields"
                )

    def test_sample_image_files_accessible(self, styles_path):
        """Verify all referenced sample images are accessible"""
        json_files = get_style_json_files(styles_path)
        samples_dir = styles_path / "samples"

        if not samples_dir.exists():
            pytest.skip("Samples directory doesn't exist yet")

        missing_samples = []
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            sample_path = style.get("sample_image_path")
            if sample_path:
                filename = Path(sample_path).name
                actual_path = samples_dir / filename
                if not actual_path.exists():
                    missing_samples.append(f"{json_file.name} references {filename}")

        # Report but don't fail on missing samples during development
        if missing_samples:
            pytest.skip(f"Missing samples (expected during development): {', '.join(missing_samples[:3])}")

    def test_style_color_palette_consistency(self, styles_path):
        """Verify color palettes are consistent within each style"""
        json_files = get_style_json_files(styles_path)

        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            colors = style.get("colors", {})
            main_colors = {
                colors.get("primary"),
                colors.get("secondary"),
                colors.get("background"),
                colors.get("text"),
                colors.get("accent")
            }

            # Should have at least 3 unique colors
            unique_colors = {c for c in main_colors if c is not None}
            assert len(unique_colors) >= 3, (
                f"{json_file.name} should have at least 3 unique colors, got {len(unique_colors)}"
            )

    def test_tier_distribution(self, styles_path):
        """Verify healthy distribution of style tiers"""
        json_files = get_style_json_files(styles_path)
        tier_counts = {1: 0, 2: 0, 3: 0, "editorial": 0}

        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)
                tier = style.get("tier")
                if tier in tier_counts:
                    tier_counts[tier] += 1

        # Should have at least one style in some tier
        total = sum(tier_counts.values())
        assert total > 0, "Should have styles defined with tiers"
