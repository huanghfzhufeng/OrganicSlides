"""Unit tests for explicit repair and failure states in planner/writer/visual."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import graph
from agents.planner import agent as planner_agent
from agents.visual import agent as visual_agent
from agents.writer import agent as writer_agent


class FakeLLM:
    def __init__(self, *responses: str):
        self.ainvoke = AsyncMock(
            side_effect=[SimpleNamespace(content=response) for response in responses]
        )


@pytest.mark.unit
class TestStructuredOutputRepair:
    @pytest.mark.asyncio
    async def test_planner_repairs_invalid_json_before_succeeding(self, monkeypatch):
        llm = FakeLLM(
            "not-json",
            """
            {
              "outline": [
                {
                  "id": "cover",
                  "title": "这个方案值得立即推进",
                  "slide_type": "cover",
                  "visual_type": "cover",
                  "key_points": [],
                  "path_hint": "path_b",
                  "notes": "封面"
                },
                {
                  "id": "main",
                  "title": "这个方案现在比观望更安全",
                  "slide_type": "content",
                  "visual_type": "illustration",
                  "key_points": ["先修基础", "再扩规模"],
                  "path_hint": "auto",
                  "notes": "主体页"
                }
              ]
            }
            """,
        )
        monkeypatch.setattr(planner_agent, "get_llm", lambda **kwargs: llm)

        result = await planner_agent.run(
            {
                "user_intent": "做一份路演",
                "source_docs": [],
                "search_results": [],
                "style_id": "organic",
                "style_config": {},
                "messages": [],
            }
        )

        assert result["current_status"] == "outline_generated"
        assert result["planner_diagnostics"]["repair_attempted"] is True
        assert result["planner_diagnostics"]["attempts"][0]["success"] is False
        assert result["planner_diagnostics"]["attempts"][1]["success"] is True
        assert "修复并生成" in result["messages"][-1]["content"]

    @pytest.mark.asyncio
    async def test_writer_returns_error_when_repair_also_fails(self, monkeypatch):
        llm = FakeLLM("bad-json", "still-bad-json")
        monkeypatch.setattr(writer_agent, "get_llm", lambda **kwargs: llm)

        result = await writer_agent.run(
            {
                "outline": [
                    {
                        "id": "section_1",
                        "title": "现在必须升级系统",
                        "slide_type": "content",
                        "visual_type": "illustration",
                        "key_points": ["现状不稳"],
                        "path_hint": "path_b",
                        "notes": "说明风险",
                    }
                ],
                "user_intent": "系统升级",
                "source_docs": [],
                "style_id": "organic",
                "style_config": {},
                "messages": [],
            }
        )

        assert result["current_status"] == "writer_error"
        assert result["slides_data"] == []
        assert "撰稿输出无法修复" in result["error"]
        assert result["writer_diagnostics"]["repair_attempted"] is True
        assert result["writer_diagnostics"]["attempts"][-1]["success"] is False

    @pytest.mark.asyncio
    async def test_visual_repairs_missing_required_fields(self, monkeypatch):
        llm = FakeLLM(
            """
            [
              {
                "page_number": 1,
                "render_path": "path_b",
                "layout_name": "blank",
                "style_notes": "缺少 image prompt"
              }
            ]
            """,
            """
            [
              {
                "page_number": 1,
                "render_path": "path_b",
                "layout_name": "blank",
                "image_prompt": "Warm editorial illustration for the assertion slide",
                "style_notes": "修复完成"
              }
            ]
            """,
        )
        monkeypatch.setattr(visual_agent, "get_llm", lambda **kwargs: llm)

        result = await visual_agent.run(
            {
                "slides_data": [
                    {
                        "page_number": 1,
                        "title": "先修稳定性再扩张",
                        "visual_type": "illustration",
                        "path_hint": "path_b",
                        "layout_intent": "cover",
                        "content": {"bullet_points": ["先稳住"]},
                        "image_prompt": "Writer draft about stabilizing before growth",
                    }
                ],
                "style_config": {
                    "id": "organic",
                    "render_paths": ["path_b"],
                    "render_path_preference": "path_b",
                },
                "messages": [],
            }
        )

        assert result["current_status"] == "visual_designed"
        assert result["visual_diagnostics"]["repair_attempted"] is True
        assert result["slide_render_plans"][0]["image_prompt"]
        assert "修复并完成" in result["messages"][-1]["content"]

    @pytest.mark.asyncio
    async def test_render_preparation_returns_explicit_error_without_visual_plans(self):
        result = await graph.render_preparation_node(
            {
                "slides_data": [
                    {
                        "page_number": 1,
                        "title": "必须阻止静默回退",
                        "path_hint": "path_a",
                    }
                ],
                "style_config": {"render_paths": ["path_a"]},
                "messages": [],
            }
        )

        assert result["current_status"] == "render_preparation_error"
        assert "拒绝静默回退" in result["error"]

    @pytest.mark.asyncio
    async def test_resume_workflow_routes_writer_error_to_error_node(self, monkeypatch):
        async def failing_writer(state):
            return {
                "current_status": "writer_error",
                "current_agent": "writer",
                "error": "writer parse failed",
                "messages": [{"role": "assistant", "content": "writer failed", "agent": "writer"}],
            }

        async def unexpected_visual(state):  # pragma: no cover - should never run
            raise AssertionError("visual should not run after writer_error")

        async def unexpected_renderer(state):  # pragma: no cover - should never run
            raise AssertionError("renderer should not run after writer_error")

        monkeypatch.setattr(graph, "writer_agent", failing_writer)
        monkeypatch.setattr(graph, "visual_agent", unexpected_visual)
        monkeypatch.setattr(graph, "renderer_agent", unexpected_renderer)

        app = graph.create_resume_app()
        result = await app.ainvoke(
            {
                "session_id": "session-1",
                "outline_approved": True,
                "messages": [],
            },
            {"configurable": {"thread_id": "session-1"}},
        )

        assert result["current_status"] == "error"
        assert result["current_agent"] == "error_handler"
        assert result["error"] == "writer parse failed"
