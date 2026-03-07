"""Unit tests for writer quality gates and repair behavior."""

from pathlib import Path
from types import SimpleNamespace
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from agents.writer import agent as writer_agent  # noqa: E402
from agents.writer.tools import evaluate_slide_quality  # noqa: E402
from runtime_schemas import build_style_packet, serialize_models  # noqa: E402


class CapturingLLM:
    def __init__(self, *responses: str):
        self.responses = [SimpleNamespace(content=response) for response in responses]
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self.responses[len(self.calls) - 1]


def _make_path_b_style_packet() -> dict:
    return serialize_models(
        build_style_packet(
            style_config={
                "id": "18-neo-brutalism",
                "name_zh": "Neo-Brutalism 新粗野主义",
                "name_en": "Neo-Brutalism",
                "description": "粗边框、色块和大字的培训风格。",
                "tier": 1,
                "colors": {
                    "primary": "#FF3B4F",
                    "secondary": "#F5E6D3",
                    "background": "#F5E6D3",
                    "text": "#1A1A1A",
                    "accent": "#FF3B4F",
                },
                "typography": {
                    "title_size": "34pt",
                    "body_size": "18pt",
                    "family": "Arial Black",
                },
                "use_cases": ["training"],
                "render_paths": ["path_b"],
                "render_path_preference": "path_b",
                "base_style_prompt": "Bold blocks, thick borders, and strong contrast.",
            }
        )
    )


def _outline() -> list[dict]:
    return [
        {
            "id": "cover",
            "title": "这套培训已经需要更强现场感",
            "slide_type": "cover",
            "visual_type": "cover",
            "key_points": [],
            "path_hint": "path_b",
            "notes": "封面页",
        },
        {
            "id": "main",
            "title": "高对比叙事正在提升学员的专注度",
            "slide_type": "content",
            "visual_type": "illustration",
            "key_points": ["高对比", "更专注", "更易记"],
            "path_hint": "path_b",
            "notes": "主体页",
        },
    ]


def _bad_slides_json() -> str:
    return json.dumps(
        [
            {
                "page_number": 1,
                "section_id": "cover",
                "title": "培训介绍",
                "visual_type": "cover",
                "path_hint": "path_b",
                "layout_intent": "cover",
                "content": {
                    "main_text": None,
                    "bullet_points": [],
                    "supporting_text": None,
                },
                "image_prompt": "高对比封面场景，观众立刻感受到紧迫感。",
                "text_to_render": {
                    "title": "这套培训已经需要更强现场感",
                    "subtitle": None,
                    "bullets": [],
                },
                "speaker_notes": "封面说明。",
            },
            {
                "page_number": 2,
                "section_id": "main",
                "title": "高对比叙事正在提升学员的专注度",
                "visual_type": "illustration",
                "path_hint": "path_b",
                "layout_intent": "bullet_points",
                "content": {
                    "main_text": None,
                    "bullet_points": ["帮助所有学员立刻进入学习情境", "更专注"],
                    "supporting_text": None,
                },
                "image_prompt": "高对比培训现场，学员被讲者吸引。",
                "text_to_render": {
                    "title": "高对比叙事正在提升学员的专注度",
                    "subtitle": None,
                    "bullets": ["帮助所有学员立刻进入学习情境", "更专注"],
                },
                "speaker_notes": "说明训练价值。",
            },
        ],
        ensure_ascii=False,
    )


def _good_slides_json() -> str:
    return json.dumps(
        [
            {
                "page_number": 1,
                "section_id": "cover",
                "title": "这套培训已经需要更强现场感",
                "visual_type": "cover",
                "path_hint": "path_b",
                "layout_intent": "cover",
                "content": {
                    "main_text": None,
                    "bullet_points": [],
                    "supporting_text": None,
                },
                "image_prompt": "高对比封面场景里，学员被现场能量立刻吸引。",
                "text_to_render": {
                    "title": "更强现场感",
                    "subtitle": None,
                    "bullets": [],
                },
                "speaker_notes": "封面说明培训需要更强的现场感。",
            },
            {
                "page_number": 2,
                "section_id": "main",
                "title": "高对比叙事正在提升学员的专注度",
                "visual_type": "illustration",
                "path_hint": "path_b",
                "layout_intent": "bullet_points",
                "content": {
                    "main_text": None,
                    "bullet_points": ["高对比", "更专注", "更易记"],
                    "supporting_text": None,
                },
                "image_prompt": "高对比培训现场让学员持续盯住关键内容，气氛紧凑而专注。",
                "text_to_render": {
                    "title": "更专注",
                    "subtitle": None,
                    "bullets": ["高对比", "更专注", "更易记"],
                },
                "speaker_notes": "说明高对比叙事如何提高专注度和记忆点。",
            },
        ],
        ensure_ascii=False,
    )


@pytest.mark.unit
class TestWriterQualityGate:
    def test_quality_gate_rejects_title_changes_from_outline(self):
        style_packet = _make_path_b_style_packet()
        slides = json.loads(_bad_slides_json())

        is_valid, message = evaluate_slide_quality(slides, _outline(), style_packet)

        assert is_valid is False
        assert "标题必须保留大纲断言句标题" in message

    def test_quality_gate_rejects_long_bullets_and_render_titles(self):
        style_packet = _make_path_b_style_packet()
        slides = json.loads(_bad_slides_json())
        slides[0]["title"] = _outline()[0]["title"]

        is_valid, message = evaluate_slide_quality(slides, _outline(), style_packet)

        assert is_valid is False
        assert (
            "bullet_points 必须控制在 12 字以内" in message
            or "text_to_render.title 必须控制在 8 个中文字以内" in message
        )

    @pytest.mark.asyncio
    async def test_writer_repairs_quality_gate_failures(self, monkeypatch):
        llm = CapturingLLM(
            _bad_slides_json(),
            _good_slides_json(),
        )
        monkeypatch.setattr(writer_agent, "get_llm", lambda **kwargs: llm)

        style_packet = _make_path_b_style_packet()
        outline = _outline()
        result = await writer_agent.run(
            {
                "outline": outline,
                "user_intent": "做一份企业培训课件",
                "research_packet": {
                    "query": "做一份企业培训课件",
                    "source_docs": [],
                    "search_results": [],
                },
                "style_id": "18-neo-brutalism",
                "style_packet": style_packet,
                "messages": [],
            }
        )

        repair_prompt = llm.calls[1][1].content

        assert result["current_status"] == "content_written"
        assert result["writer_diagnostics"]["repair_attempted"] is True
        assert result["slides_data"][0]["title"] == outline[0]["title"]
        assert max(len(bullet) for bullet in result["slides_data"][1]["content"]["bullet_points"]) <= 12
        assert result["slides_data"][1]["text_to_render"]["title"] == "更专注"
        assert "必须保留大纲断言句标题" in repair_prompt or "12 字以内" in repair_prompt
