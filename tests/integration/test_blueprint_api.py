"""Integration tests for the slide blueprint workflow."""

from types import SimpleNamespace
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestBlueprintAPI:
    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
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

        class FakeDBSession:
            async def execute(self, *args, **kwargs):
                return None

            async def commit(self):
                return None

        monkeypatch.setattr(main.redis_client, "set_session", fake_set_session)
        monkeypatch.setattr(main.redis_client, "get_session", fake_get_session)
        monkeypatch.setattr(main.redis_client, "update_session", fake_update_session)
        async def override_get_db():
            yield FakeDBSession()

        self.app.dependency_overrides[main.get_db] = override_get_db
        if hasattr(main, "limiter"):
            main.limiter.enabled = False
            if hasattr(main.limiter, "reset"):
                main.limiter.reset()

        yield

        self.app.dependency_overrides.clear()
        self.client.close()
        if hasattr(main, "limiter"):
            main.limiter.enabled = True

    def _enable_auth(self):
        fake_user = SimpleNamespace(id=uuid.uuid4(), is_active=True)

        async def override_current_user():
            return fake_user

        async def fake_verify_project_ownership(session_id, user, db):
            return SimpleNamespace(id=session_id, user_id=fake_user.id)

        self.app.dependency_overrides[self.main.get_current_active_user] = override_current_user
        self.app.dependency_overrides[self.main.get_current_active_user_sse] = override_current_user
        self.monkeypatch.setattr(self.main, "_verify_project_ownership", fake_verify_project_ownership)
        return fake_user

    def _create_project(self) -> str:
        response = self.client.post("/api/v1/project/create", json={"prompt": "测试蓝图流程"})
        assert response.status_code == 200
        return response.json()["session_id"]

    @staticmethod
    def _sample_outline():
        return [
            {
                "id": "section_1",
                "title": "研究背景与问题定义",
                "type": "content",
                "key_points": ["行业背景", "核心问题", "为什么现在必须解决"],
                "notes": "先交代背景，再说明问题",
            }
        ]

    @staticmethod
    def _sample_blueprint():
        return [
            {
                "section_id": "section_1",
                "section_title": "研究背景与问题定义",
                "title": "为什么这个问题值得现在解决",
                "slide_type": "content",
                "visual_type": "illustration",
                "path_hint": "auto",
                "goal": "用一页建立问题的重要性",
                "evidence_type": "logic",
                "key_points": ["行业背景", "问题正在扩大", "现在是转折点"],
                "content_brief": "先交代背景，再说明为什么此时必须行动",
                "speaker_notes": "用一段完整叙述串联背景与紧迫性",
            }
        ]

    def test_project_create_attaches_skill_runtime_defaults(self):
        session_id = self._create_project()
        session_state = self.session_store[session_id]

        assert session_state["skill_id"] == "huashu-slides"
        assert session_state["collaboration_mode"] == "guided"
        assert session_state["skill_packet"]["default_render_path"] == "path_a"

    def test_skills_endpoint_lists_huashu_runtime(self):
        response = self.client.get("/api/v1/skills")

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] >= 1
        assert any(skill["skill_id"] == "huashu-slides" for skill in payload["skills"])

    def test_generate_blueprint_requires_approved_outline(self):
        self._enable_auth()
        session_id = self._create_project()
        self.session_store[session_id]["outline"] = self._sample_outline()
        self.session_store[session_id]["outline_approved"] = False

        response = self.client.post(
            "/api/v1/workflow/blueprint/generate",
            json={"session_id": session_id},
        )

        assert response.status_code == 409
        assert "Outline must be approved" in response.json()["detail"]

    def test_generate_blueprint_reuses_existing_blueprint(self):
        self._enable_auth()
        session_id = self._create_project()
        blueprint = self._sample_blueprint()
        self.session_store[session_id].update(
            {
                "outline": self._sample_outline(),
                "outline_approved": True,
                "slide_blueprint": blueprint,
                "slide_blueprint_approved": False,
                "current_status": "blueprint_generated",
            }
        )

        async def fail_blueprint_agent(_state):
            raise AssertionError("blueprint agent should not run when blueprint already exists")

        self.monkeypatch.setattr(self.main, "blueprint_agent", fail_blueprint_agent)

        response = self.client.post(
            "/api/v1/workflow/blueprint/generate",
            json={"session_id": session_id},
        )

        assert response.status_code == 200
        assert response.json()["slide_blueprint"] == blueprint

    def test_update_blueprint_normalizes_and_marks_approved(self):
        self._enable_auth()
        session_id = self._create_project()
        self.session_store[session_id].update(
            {
                "outline": self._sample_outline(),
                "outline_approved": True,
            }
        )

        response = self.client.post(
            "/api/v1/workflow/blueprint/update",
            json={
                "session_id": session_id,
                "slide_blueprint": self._sample_blueprint(),
            },
        )

        assert response.status_code == 200
        saved_blueprint = response.json()["slide_blueprint"]
        assert saved_blueprint[0]["id"] == "slide_1"
        assert saved_blueprint[0]["page_number"] == 1
        assert self.session_store[session_id]["slide_blueprint_approved"] is True
        assert self.session_store[session_id]["current_status"] == "blueprint_approved"

    def test_style_update_requires_blueprint_approval(self):
        self._enable_auth()
        session_id = self._create_project()
        self.session_store[session_id].update(
            {
                "outline": self._sample_outline(),
                "outline_approved": True,
                "slide_blueprint": self._sample_blueprint(),
                "slide_blueprint_approved": False,
            }
        )

        response = self.client.post(
            "/api/v1/project/style",
            json={
                "session_id": session_id,
                "style_id": "01-snoopy",
                "render_path_preference": "auto",
            },
        )

        assert response.status_code == 409
        assert "Slide blueprint must be approved" in response.json()["detail"]

    def test_resume_requires_blueprint_approval(self):
        self._enable_auth()
        session_id = self._create_project()
        self.session_store[session_id].update(
            {
                "outline": self._sample_outline(),
                "outline_approved": True,
                "slide_blueprint": [],
                "slide_blueprint_approved": False,
            }
        )

        response = self.client.get(f"/api/v1/workflow/resume/{session_id}")

        assert response.status_code == 409
        assert "Slide blueprint must be approved" in response.json()["detail"]
