"""Unit tests for writer StylePacket injection and validation."""

from pathlib import Path
from types import SimpleNamespace
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from agents.writer import agent as writer_agent  # noqa: E402
from agents.writer.tools import build_style_context, validate_slides_content  # noqa: E402
from runtime_schemas import build_style_packet, serialize_models  # noqa: E402


class CapturingLLM:
    def __init__(self, *responses: str):
        self.responses = [SimpleNamespace(content=response) for response in responses]
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self.responses[len(self.calls) - 1]


def _make_neo_brutalism_packet() -> dict:
    return serialize_models(
        build_style_packet(
            style_config={
                "id": "18-neo-brutalism",
                "name_zh": "Neo-Brutalism 新粗野主义",
                "name_en": "Neo-Brutalism",
                "description": "粗边框、色块、大字，远距离可读。",
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
                "use_cases": ["training", "education"],
                "render_paths": ["path_a", "path_b"],
                "render_path_preference": "path_b",
                "base_style_prompt": "Bold blocks, thick borders, and saturated contrast.",
            }
        )
    )


def _outline() -> list[dict]:
    return [
        {
            "id": "cover",
            "title": "这套培训必须先让人看懂再记住",
            "slide_type": "cover",
            "visual_type": "cover",
            "key_points": [],
            "path_hint": "path_b",
            "notes": "封面页",
        },
        {
            "id": "main",
            "title": "高对比视觉正在提升线下培训的远距可读性",
            "slide_type": "content",
            "visual_type": "illustration",
            "key_points": ["高对比", "远距可读", "培训场景"],
            "path_hint": "path_b",
            "notes": "主体页",
        },
    ]


def _slides_payload(bad_prompt: bool) -> str:
    prompts = {
        True: [
            "标题居中偏上，右侧放一块红色标题牌，左侧是粗边框人物插画",
            "大字放在左边，角色站在右边，背景色块铺满页面",
        ],
        False: [
            "一群学员在高对比色块和粗边框包围的现场空间里聚焦主讲人，画面传达出立刻进入训练状态的兴奋感。",
            "主讲人与学员在明亮醒目的培训现场展开互动，粗边框和饱和色块强化出远距离也能看清重点的力量感。",
        ],
    }[bad_prompt]

    return json.dumps(
        [
            {
                "page_number": 1,
                "section_id": "cover",
                "title": "这套培训必须先让人看懂再记住",
                "visual_type": "cover",
                "path_hint": "path_b",
                "layout_intent": "cover",
                "content": {
                    "main_text": None,
                    "bullet_points": [],
                    "supporting_text": None,
                },
                "image_prompt": prompts[0],
                "text_to_render": {
                    "title": "先看懂",
                    "subtitle": None,
                    "bullets": [],
                },
                "speaker_notes": "封面说明训练目标。",
            },
            {
                "page_number": 2,
                "section_id": "main",
                "title": "高对比视觉正在提升线下培训的远距可读性",
                "visual_type": "illustration",
                "path_hint": "path_b",
                "layout_intent": "bullet_points",
                "content": {
                    "main_text": None,
                    "bullet_points": ["高对比", "远距可读", "培训场景"],
                    "supporting_text": None,
                },
                "image_prompt": prompts[1],
                "text_to_render": {
                    "title": "高对比",
                    "subtitle": None,
                    "bullets": ["高对比", "远距可读", "培训场景"],
                },
                "speaker_notes": "说明视觉策略。",
            },
        ],
        ensure_ascii=False,
    )


@pytest.mark.unit
class TestWriterStylePacket:
    def test_build_style_context_includes_path_b_constraints(self):
        style_packet = _make_neo_brutalism_packet()

        context = build_style_context(style_packet)

        assert "Neo-Brutalism" in context
        assert "Path B 禁用词" in context
        assert "Assertion-Evidence Framework" in context or "Title = assertion" in context

    def test_validate_slides_content_rejects_forbidden_path_b_terms(self):
        style_packet = _make_neo_brutalism_packet()
        slides = json.loads(_slides_payload(bad_prompt=True))

        is_valid, message = validate_slides_content(slides, style_packet)

        assert is_valid is False
        assert "image_prompt 包含风格禁用词" in message
        assert "右" in message or "居中" in message

    @pytest.mark.asyncio
    async def test_writer_repairs_slides_against_style_packet_constraints(self, monkeypatch):
        llm = CapturingLLM(
            _slides_payload(bad_prompt=True),
            _slides_payload(bad_prompt=False),
        )
        monkeypatch.setattr(writer_agent, "get_llm", lambda **kwargs: llm)

        style_packet = _make_neo_brutalism_packet()
        result = await writer_agent.run(
            {
                "outline": _outline(),
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

        first_prompt = llm.calls[0][1].content
        repair_prompt = llm.calls[1][1].content

        assert result["current_status"] == "content_written"
        assert result["writer_diagnostics"]["repair_attempted"] is True
        assert "Neo-Brutalism" in first_prompt
        assert "Path B 禁用词" in first_prompt
        assert "Neo-Brutalism" in repair_prompt
        assert "居中" not in result["slides_data"][0]["image_prompt"]
        assert "右侧" not in result["slides_data"][0]["image_prompt"]
