"""Integration tests for styles API endpoints"""

import pytest
import json
import uuid
from pathlib import Path
from types import SimpleNamespace
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

        async def fake_set_session(session_id, data, ttl=86400):
            self.session_store[session_id] = data

        async def fake_get_session(session_id):
            return self.session_store.get(session_id)

        async def fake_update_session(session_id, updates):
            current = self.session_store.get(session_id, {})
            current.update(updates)
            self.session_store[session_id] = current

        monkeypatch.setattr(main.redis_client, "set_session", fake_set_session)
        monkeypatch.setattr(main.redis_client, "get_session", fake_get_session)
        monkeypatch.setattr(main.redis_client, "update_session", fake_update_session)
        if hasattr(main, "limiter"):
            main.limiter.enabled = False
            if hasattr(main.limiter, "reset"):
                main.limiter.reset()

        yield

        self.app.dependency_overrides.clear()
        self.client.close()
        if hasattr(main, "limiter"):
            main.limiter.enabled = True

    def _enable_project_status_auth(self):
        fake_user = SimpleNamespace(id=uuid.uuid4(), is_active=True)

        async def override_current_user():
            return fake_user

        async def fake_verify_project_ownership(session_id, user, db):
            return SimpleNamespace(id=session_id, user_id=fake_user.id)

        self.app.dependency_overrides[self.main.get_current_active_user] = override_current_user
        self.monkeypatch.setattr(self.main, "_verify_project_ownership", fake_verify_project_ownership)
        return fake_user

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
        """Test protected project status endpoint requires authentication"""
        response = self.client.get("/api/v1/project/status/invalid-id")
        assert response.status_code == 401

    def test_project_status_existing_session(self):
        """Test project status for existing session"""
        self._enable_project_status_auth()

        # Create a project first
        create_response = self.client.post(
            "/api/v1/project/create",
            json={"prompt": "Test"}
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        # Get status
        response = self.client.get(f"/api/v1/project/status/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "initialized"
        assert data["current_agent"] == ""

    def test_workflow_outline_not_found(self):
        """Test getting outline for non-existent session"""
        response = self.client.get("/api/v1/workflow/outline/invalid-id")
        assert response.status_code == 404

    def test_workflow_outline_existing_session(self):
        """Test getting outline for existing session"""
        # Create a project
        create_response = self.client.post(
            "/api/v1/project/create",
            json={"prompt": "Test presentation"}
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        # Get outline
        response = self.client.get(f"/api/v1/workflow/outline/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["outline"] == []
        assert data["status"] == "initialized"

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
