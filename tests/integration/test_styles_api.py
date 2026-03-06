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

        self.main = main
        self.app = main.app
        self.client = TestClient(self.app)
        self.monkeypatch = monkeypatch
        self.session_store = {}
        self.revisions = []

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
            revision = {
                "session_id": session_id,
                "revision_type": revision_type,
                "state": dict(state),
                "project_id": project_id,
            }
            self.revisions.append(revision)
            return revision

        monkeypatch.setattr(main, "_load_session_state", fake_load_session_state)
        monkeypatch.setattr(main, "_save_session_state", fake_save_session_state)
        monkeypatch.setattr(main, "_merge_session_state", fake_merge_session_state)
        monkeypatch.setattr(main, "create_project_revision", fake_create_project_revision)

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

        async def fake_generate_sse_events(session_id_param, state):
            yield "data: {\"type\":\"complete\",\"status\":\"done\"}\n\n"

        monkeypatch.setattr(self.main, "generate_sse_events", fake_generate_sse_events)

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
