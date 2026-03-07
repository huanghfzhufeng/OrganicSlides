"""Unit tests for planner StylePacket injection and validation."""

from pathlib import Path
from types import SimpleNamespace
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from agents.planner import agent as planner_agent  # noqa: E402
from agents.planner.tools import build_style_context, validate_outline  # noqa: E402
from runtime_schemas import build_style_packet, serialize_models  # noqa: E402


class CapturingLLM:
    def __init__(self, *responses: str):
        self.responses = [SimpleNamespace(content=response) for response in responses]
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self.responses[len(self.calls) - 1]


def _make_nyt_style_packet() -> dict:
    return serialize_models(
        build_style_packet(
            style_config={
                "id": "p6-nyt-magazine",
                "name_zh": "NYT Magazine Editorial",
                "name_en": "NYT Magazine Editorial",
                "description": "权威的数据报告与行业分析风格。",
                "tier": 1,
                "colors": {
                    "primary": "#B22222",
                    "secondary": "#F5F1EA",
                    "background": "#FAF8F4",
                    "text": "#1F1F1F",
                    "accent": "#B22222",
                },
                "typography": {
                    "title_size": "32pt",
                    "body_size": "16pt",
                    "family": "Georgia",
                },
                "use_cases": ["data-report", "analysis"],
                "render_paths": ["path_a"],
                "render_path_preference": "path_a",
                "base_style_prompt": "Authoritative editorial design with strong hierarchy.",
            }
        )
    )


def _outline_payload(path_hint: str) -> str:
    return json.dumps(
        {
            "outline": [
                {
                    "id": "cover",
                    "title": "这份行业分析已经显示出明确分化趋势",
                    "slide_type": "cover",
                    "visual_type": "cover",
                    "key_points": [],
                    "path_hint": path_hint,
                    "notes": "封面页",
                },
                {
                    "id": "main",
                    "title": "需求恢复速度正在决定未来十二个月的竞争格局",
                    "slide_type": "content",
                    "visual_type": "chart",
                    "key_points": ["需求恢复", "区域分化", "竞争格局"],
                    "path_hint": path_hint,
                    "notes": "主体页",
                },
            ]
        },
        ensure_ascii=False,
    )


@pytest.mark.unit
class TestPlannerStylePacket:
    def test_build_style_context_includes_style_packet_references(self):
        style_packet = _make_nyt_style_packet()

        context = build_style_context(style_packet)

        assert "NYT Magazine Editorial" in context
        assert "Assertion-Evidence Framework" in context
        assert "Path A 硬规则" in context
        assert "参考来源" in context

    def test_validate_outline_rejects_unsupported_path_hint(self):
        style_packet = _make_nyt_style_packet()
        outline = json.loads(_outline_payload("path_b"))["outline"]

        is_valid, message = validate_outline(outline, style_packet)

        assert is_valid is False
        assert "path_hint 'path_b'" in message
        assert "path_a" in message

    @pytest.mark.asyncio
    async def test_planner_repairs_outline_against_style_packet_constraints(self, monkeypatch):
        llm = CapturingLLM(
            _outline_payload("path_b"),
            _outline_payload("path_a"),
        )
        monkeypatch.setattr(planner_agent, "get_llm", lambda **kwargs: llm)

        style_packet = _make_nyt_style_packet()
        result = await planner_agent.run(
            {
                "user_intent": "做一份行业数据报告",
                "research_packet": {
                    "query": "做一份行业数据报告",
                    "source_docs": [],
                    "search_results": [],
                },
                "style_id": "p6-nyt-magazine",
                "style_packet": style_packet,
                "messages": [],
            }
        )

        first_prompt = llm.calls[0][1].content
        repair_prompt = llm.calls[1][1].content

        assert result["current_status"] == "outline_generated"
        assert result["planner_diagnostics"]["repair_attempted"] is True
        assert all(slide["path_hint"] == "path_a" for slide in result["outline"])
        assert "NYT Magazine Editorial" in first_prompt
        assert "Assertion-Evidence Framework" in first_prompt
        assert "NYT Magazine Editorial" in repair_prompt
