"""Unit tests for Visual StylePacket injection and validation."""

from pathlib import Path
from types import SimpleNamespace
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from agents.visual import agent as visual_agent  # noqa: E402
from agents.visual.tools import build_style_context  # noqa: E402
from runtime_schemas import build_style_packet, serialize_models  # noqa: E402


class CapturingLLM:
    def __init__(self, *responses: str):
        self.responses = [SimpleNamespace(content=response) for response in responses]
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self.responses[len(self.calls) - 1]


def _make_snoopy_packet() -> dict:
    return serialize_models(
        build_style_packet(
            style_config={
                "id": "01-snoopy",
                "name_zh": "Snoopy 温暖漫画",
                "name_en": "Snoopy Warm Comic",
                "description": "温暖、幽默、适合培训和知识分享的漫画叙事风格。",
                "tier": 1,
                "colors": {
                    "primary": "#FF6B6B",
                    "secondary": "#FFF8E8",
                    "background": "#FFF8E8",
                    "text": "#1A1A1A",
                    "accent": "#FF6B6B",
                },
                "typography": {
                    "title_size": "32pt",
                    "body_size": "16pt",
                    "family": "Comic Sans MS",
                },
                "use_cases": ["training", "education"],
                "render_paths": ["path_b"],
                "render_path_preference": "path_b",
                "sample_image_path": "/static/styles/samples/style-01-snoopy.png",
                "base_style_prompt": "Warm comic strip with hand-drawn lines and gentle humor.",
            }
        )
    )


def _slides_data() -> list[dict]:
    return [
        {
            "page_number": 1,
            "section_id": "cover",
            "title": "先把复杂问题讲清楚",
            "visual_type": "cover",
            "path_hint": "path_b",
            "layout_intent": "cover",
            "content": {"bullet_points": []},
            "image_prompt": "温暖开篇场景",
            "text_to_render": {"title": "先把复杂问题讲清楚", "subtitle": None, "bullets": []},
            "speaker_notes": "封面页",
        }
    ]


def _valid_path_b_prompt(title: str) -> str:
    return (
        "Visual Reference: use the tracked Snoopy warm comic sample as the visual reference.\n\n"
        "Base Style: warm comic strip with hand-drawn lines and gentle humor.\n\n"
        "Design Intent: audience should feel calm, curious, and ready to learn.\n\n"
        f"Text to Render:\n- Title: \"{title}\"\n\n"
        "Visual Narrative: A teacher and learner share a warm, story-driven moment that makes a complex idea feel approachable."
    )


@pytest.mark.unit
class TestVisualStylePacket:
    def test_build_style_context_includes_style_packet_constraints(self):
        style_packet = _make_snoopy_packet()

        context = build_style_context(style_packet)

        assert "Snoopy" in context
        assert "Path B 必填段落" in context
        assert "样例素材路径" in context
        assert "Assertion-Evidence Framework" in context or "Title = assertion" in context

    def test_validate_visual_plans_rejects_unsupported_render_path(self):
        style_packet = _make_snoopy_packet()
        slides_data = _slides_data()
        plans = [
            {
                "page_number": 1,
                "render_path": "path_a",
                "layout_name": "bullet_list",
                "title": slides_data[0]["title"],
                "content": slides_data[0]["content"],
                "html_content": "<html><body><div><h1>先把复杂问题讲清楚</h1></div></body></html>",
            }
        ]

        is_valid, message = visual_agent._validate_visual_plans(plans, slides_data, style_packet)

        assert is_valid is False
        assert "unsupported render_path 'path_a'" in message

    def test_validate_visual_plans_rejects_forbidden_path_b_terms(self):
        style_packet = _make_snoopy_packet()
        slides_data = _slides_data()
        plans = [
            {
                "page_number": 1,
                "render_path": "path_b",
                "layout_name": "blank",
                "title": slides_data[0]["title"],
                "content": slides_data[0]["content"],
                "image_prompt": (
                    "Visual Reference: use the tracked Snoopy warm comic sample as the visual reference.\n\n"
                    "Base Style: warm comic strip with hand-drawn lines and gentle humor.\n\n"
                    "Design Intent: audience should feel calm and safe.\n\n"
                    f"Text to Render:\n- Title: \"{slides_data[0]['title']}\"\n\n"
                    "Visual Narrative: 左侧是一位老师和学员在温暖教室里对话。"
                ),
                "style_notes": "path_b",
            }
        ]

        is_valid, message = visual_agent._validate_visual_plans(plans, slides_data, style_packet)

        assert is_valid is False
        assert "forbidden terms" in message
        assert "左" in message

    @pytest.mark.asyncio
    async def test_visual_repairs_against_style_packet_constraints(self, monkeypatch):
        llm = CapturingLLM(
            json.dumps(
                [
                    {
                        "page_number": 1,
                        "render_path": "path_b",
                        "layout_name": "blank",
                        "image_prompt": "左侧角色场景",
                        "style_notes": "bad prompt",
                    }
                ],
                ensure_ascii=False,
            ),
            json.dumps(
                [
                    {
                        "page_number": 1,
                        "render_path": "path_b",
                        "layout_name": "blank",
                        "image_prompt": _valid_path_b_prompt("先把复杂问题讲清楚"),
                        "style_notes": "repaired prompt",
                    }
                ],
                ensure_ascii=False,
            ),
        )
        monkeypatch.setattr(visual_agent, "get_llm", lambda **kwargs: llm)

        style_packet = _make_snoopy_packet()
        result = await visual_agent.run(
            {
                "slides_data": _slides_data(),
                "style_id": "01-snoopy",
                "style_packet": style_packet,
                "messages": [],
            }
        )

        first_prompt = llm.calls[0][1].content
        repair_prompt = llm.calls[1][1].content

        assert result["current_status"] == "visual_designed"
        assert result["visual_diagnostics"]["repair_attempted"] is True
        assert "Snoopy" in first_prompt
        assert "Path B 必填段落" in first_prompt
        assert "Snoopy" in repair_prompt
        assert "Visual Reference" in result["slide_render_plans"][0]["image_prompt"]
