"""Integration tests for the collaborative per-slide review workflow."""

from types import SimpleNamespace
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestCollaborativeReviewAPI:
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
            current = dict(self.session_store.get(session_id, {}))
            current.update(updates)
            self.session_store[session_id] = current

        async def fake_push_log(session_id, data):
            return None

        class FakeDBSession:
            async def execute(self, *args, **kwargs):
                return None

            async def commit(self):
                return None

        monkeypatch.setattr(main.redis_client, "set_session", fake_set_session)
        monkeypatch.setattr(main.redis_client, "get_session", fake_get_session)
        monkeypatch.setattr(main.redis_client, "update_session", fake_update_session)
        monkeypatch.setattr(main.redis_client, "push_log", fake_push_log)

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

    def _seed_session(self, **overrides) -> str:
        session_id = str(uuid.uuid4())
        base_state = {
            "session_id": session_id,
            "skill_id": "huashu-slides",
            "collaboration_mode": "collaborative",
            "outline_approved": True,
            "slide_blueprint_approved": True,
            "slide_blueprint": [
                {
                    "id": "slide_1",
                    "page_number": 1,
                    "section_id": "section_1",
                    "section_title": "研究背景",
                    "title": "第一页标题",
                    "slide_type": "content",
                    "visual_type": "illustration",
                    "path_hint": "path_b",
                    "goal": "说明背景",
                    "evidence_type": "logic",
                    "key_points": ["点 1", "点 2"],
                    "content_brief": "内容摘要",
                    "speaker_notes": "备注",
                }
            ],
            "slides_data": [
                {
                    "page_number": 1,
                    "title": "旧标题",
                    "content": {"bullet_points": ["旧要点 1", "旧要点 2"]},
                    "speaker_notes": "旧备注",
                    "image_prompt": "old prompt",
                    "visual_type": "illustration",
                    "layout_intent": "split_focus",
                }
            ],
            "slide_render_plans": [
                {
                    "page_number": 1,
                    "render_path": "path_b",
                    "layout_name": "split_focus",
                    "image_prompt": "old render prompt",
                    "style_notes": "old notes",
                }
            ],
            "slide_reviews": [
                {
                    "page_number": 1,
                    "accepted": False,
                    "status": "pending",
                    "feedback": "",
                    "revision_count": 0,
                }
            ],
            "slide_review_required": True,
            "slide_review_approved": False,
            "current_status": "waiting_for_slide_review",
        }
        base_state.update(overrides)
        self.session_store[session_id] = base_state
        return session_id

    def test_get_slide_review_returns_review_payload(self):
        self._enable_auth()
        session_id = self._seed_session()

        response = self.client.get(f"/api/v1/workflow/slide-review/{session_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["session_id"] == session_id
        assert payload["approved"] is False
        assert payload["slides"][0]["title"] == "旧标题"
        assert payload["slides"][0]["render_path"] == "path_b"

    def test_update_slide_review_patches_single_slide(self):
        self._enable_auth()
        session_id = self._seed_session()

        response = self.client.post(
            "/api/v1/workflow/slide-review/update",
            json={
                "session_id": session_id,
                "page_number": 1,
                "slide_patch": {
                    "title": "修订后的标题",
                    "content": {"bullet_points": ["新要点 1", "新要点 2"]},
                    "speaker_notes": "新的备注",
                },
                "render_patch": {
                    "image_prompt": "new render prompt",
                    "style_notes": "new notes",
                },
                "feedback": "标题再聚焦一点",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["slides"][0]["title"] == "修订后的标题"
        assert payload["slides"][0]["bullet_points"] == ["新要点 1", "新要点 2"]
        assert payload["slides"][0]["feedback"] == "标题再聚焦一点"
        assert self.session_store[session_id]["slides_data"][0]["speaker_notes"] == "新的备注"
        assert self.session_store[session_id]["slide_render_plans"][0]["image_prompt"] == "new render prompt"
        assert self.session_store[session_id]["slide_reviews"][0]["status"] == "revised"

    def test_accept_slide_review_marks_workflow_ready_for_render(self):
        self._enable_auth()
        session_id = self._seed_session()

        response = self.client.post(
            "/api/v1/workflow/slide-review/accept",
            json={"session_id": session_id, "page_number": 1},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["approved"] is True
        assert payload["slides"][0]["accepted"] is True
        assert self.session_store[session_id]["slide_review_required"] is False
        assert self.session_store[session_id]["slide_review_approved"] is True
        assert self.session_store[session_id]["current_status"] == "slide_review_approved"

    def test_regenerate_slide_review_refreshes_only_target_page(self):
        self._enable_auth()
        session_id = self._seed_session()

        async def fake_writer_agent(_state):
            return {
                "slides_data": [
                    {
                        "page_number": 1,
                        "title": "重生成标题",
                        "content": {"bullet_points": ["重生成要点"]},
                        "speaker_notes": "新的演讲备注",
                        "image_prompt": "writer prompt",
                        "visual_type": "diagram",
                        "layout_intent": "data_focus",
                    }
                ]
            }

        async def fake_visual_agent(_state):
            return {
                "slide_render_plans": [
                    {
                        "page_number": 1,
                        "render_path": "path_a",
                        "layout_name": "data_focus",
                        "html_content": "<section>ok</section>",
                        "image_prompt": "visual prompt",
                        "style_notes": "visual notes",
                    }
                ]
            }

        self.monkeypatch.setattr(self.main, "writer_agent", fake_writer_agent)
        self.monkeypatch.setattr(self.main, "visual_agent", fake_visual_agent)

        response = self.client.post(
            "/api/v1/workflow/slide-review/regenerate",
            json={"session_id": session_id, "page_number": 1},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["slides"][0]["title"] == "重生成标题"
        assert payload["slides"][0]["render_path"] == "path_a"
        assert payload["slides"][0]["review_status"] == "regenerated"
        assert payload["slides"][0]["revision_count"] == 1
        assert self.session_store[session_id]["slides_data"][0]["title"] == "重生成标题"
        assert self.session_store[session_id]["slide_render_plans"][0]["html_content"] == "<section>ok</section>"

    def test_render_endpoint_requires_approved_review(self):
        self._enable_auth()
        session_id = self._seed_session(slide_review_approved=False)

        response = self.client.get(f"/api/v1/workflow/render/{session_id}")

        assert response.status_code == 409
        assert "accepted" in response.json()["detail"]

    def test_render_endpoint_streams_after_all_slides_accepted(self):
        self._enable_auth()
        session_id = self._seed_session(
            slide_review_approved=True,
            slide_review_required=False,
            current_status="slide_review_approved",
            slide_reviews=[
                {
                    "page_number": 1,
                    "accepted": True,
                    "status": "accepted",
                    "feedback": "",
                    "revision_count": 0,
                }
            ],
        )

        async def fake_render_stream(_session_id):
            yield 'data: {"type":"complete","status":"done","pptx_path":"demo.pptx"}\n\n'

        self.monkeypatch.setattr(self.main, "generate_render_only_sse_events", fake_render_stream)

        response = self.client.get(f"/api/v1/workflow/render/{session_id}")

        assert response.status_code == 200
        assert '"type":"complete"' in response.text
