"""Unit tests for visual quality gates and repair behavior."""

from pathlib import Path
from types import SimpleNamespace
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from agents.visual import agent as visual_agent  # noqa: E402
from runtime_schemas import build_style_packet, serialize_models  # noqa: E402


class CapturingLLM:
    def __init__(self, *responses: str):
        self.responses = [SimpleNamespace(content=response) for response in responses]
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return self.responses[len(self.calls) - 1]


def _make_nyt_packet() -> dict:
    return serialize_models(
        build_style_packet(
            style_config={
                "id": "p6-nyt-magazine",
                "name_zh": "NYT Magazine Editorial",
                "name_en": "NYT Magazine Editorial",
                "description": "权威的编辑部式数据报告风格。",
                "tier": 1,
                "colors": {
                    "primary": "#C8000A",
                    "secondary": "#F5F1EA",
                    "background": "#FEFEF9",
                    "text": "#1A1A1A",
                    "accent": "#C8000A",
                },
                "typography": {
                    "title_size": "32pt",
                    "body_size": "16pt",
                    "family": "Georgia",
                },
                "use_cases": ["report", "analysis"],
                "render_paths": ["path_a"],
                "render_path_preference": "path_a",
                "base_style_prompt": "Authoritative editorial design with strong typographic hierarchy.",
            }
        )
    )


def _slides_data() -> list[dict]:
    return [
        {
            "page_number": 1,
            "section_id": "main",
            "title": "数据趋势已经显示出明显分化",
            "visual_type": "chart",
            "path_hint": "path_a",
            "layout_intent": "data_driven",
            "content": {"bullet_points": ["需求恢复", "区域分化"]},
            "image_prompt": None,
            "text_to_render": {
                "title": "数据趋势已经显示出明显分化",
                "subtitle": None,
                "bullets": ["需求恢复", "区域分化"],
            },
            "speaker_notes": "说明主要差异。",
        }
    ]


def _bad_html() -> str:
    return """
<html>
<body style="background: linear-gradient(to right, #fff, #eee)">
  <div>数据趋势已经显示出明显分化</div>
</body>
</html>
""".strip()


def _good_html() -> str:
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: 720pt; height: 405pt;
    font-family: system-ui, -apple-system, "PingFang SC", sans-serif;
    background: #FEFEF9;
    overflow: hidden;
  }
</style>
</head>
<body>
  <div style="position: absolute; top: 8pt; left: 0; right: 0; height: 5pt; background: #C8000A;"></div>
  <div style="position: absolute; top: 32pt; left: 48pt; right: 48pt;">
    <h1 style="font-size: 28pt; color: #1A1A1A; font-weight: 700;">数据趋势已经显示出明显分化</h1>
  </div>
  <div style="position: absolute; top: 120pt; left: 48pt; right: 48pt;">
    <ul style="font-size: 14pt; color: #1A1A1A; padding-left: 20pt; line-height: 1.8;">
      <li>需求恢复</li>
      <li>区域分化</li>
    </ul>
  </div>
</body>
</html>
""".strip()


@pytest.mark.unit
class TestVisualQualityGate:
    def test_validate_visual_plans_rejects_low_quality_path_a_html(self):
        style_packet = _make_nyt_packet()
        slides_data = _slides_data()
        plans = [
            {
                "page_number": 1,
                "render_path": "path_a",
                "layout_name": "bullet_list",
                "title": slides_data[0]["title"],
                "content": slides_data[0]["content"],
                "html_content": _bad_html(),
                "style_notes": "bad html",
            }
        ]

        is_valid, message = visual_agent._validate_visual_plans(plans, slides_data, style_packet)

        assert is_valid is False
        assert "missing doctype" in message or "must not use CSS gradients" in message

    def test_validate_visual_plans_rejects_thin_path_b_sections(self):
        style_packet = serialize_models(
            build_style_packet(
                style_config={
                    "id": "01-snoopy",
                    "name_zh": "Snoopy 温暖漫画",
                    "name_en": "Snoopy Warm Comic",
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
                    "use_cases": ["training"],
                    "render_paths": ["path_b"],
                    "render_path_preference": "path_b",
                    "base_style_prompt": "Warm comic strip.",
                }
            )
        )
        slides_data = [
            {
                "page_number": 1,
                "section_id": "cover",
                "title": "先把复杂问题讲清楚",
                "visual_type": "cover",
                "path_hint": "path_b",
                "layout_intent": "cover",
                "content": {"bullet_points": []},
                "image_prompt": "开篇",
                "text_to_render": {"title": "先把复杂问题讲清楚", "subtitle": None, "bullets": []},
                "speaker_notes": "封面页",
            }
        ]
        plans = [
            {
                "page_number": 1,
                "render_path": "path_b",
                "layout_name": "blank",
                "title": slides_data[0]["title"],
                "content": slides_data[0]["content"],
                "image_prompt": (
                    "Visual Reference: ok\n\n"
                    "Base Style: ok\n\n"
                    "Design Intent: ok\n\n"
                    f"Text to Render:\n- Title: \"{slides_data[0]['title']}\"\n\n"
                    "Visual Narrative: ok"
                ),
                "style_notes": "thin prompt",
            }
        ]

        is_valid, message = visual_agent._validate_visual_plans(plans, slides_data, style_packet)

        assert is_valid is False
        assert "section is too thin" in message

    @pytest.mark.asyncio
    async def test_visual_repairs_low_quality_path_a_html(self, monkeypatch):
        llm = CapturingLLM(
            json.dumps(
                [
                    {
                        "page_number": 1,
                        "render_path": "path_a",
                        "layout_name": "bullet_list",
                        "html_content": _bad_html(),
                        "style_notes": "bad html",
                    }
                ],
                ensure_ascii=False,
            ),
            json.dumps(
                [
                    {
                        "page_number": 1,
                        "render_path": "path_a",
                        "layout_name": "bullet_list",
                        "html_content": _good_html(),
                        "style_notes": "repaired html",
                    }
                ],
                ensure_ascii=False,
            ),
        )
        monkeypatch.setattr(visual_agent, "get_llm", lambda **kwargs: llm)

        style_packet = _make_nyt_packet()
        result = await visual_agent.run(
            {
                "slides_data": _slides_data(),
                "style_id": "p6-nyt-magazine",
                "style_packet": style_packet,
                "messages": [],
            }
        )

        repair_prompt = llm.calls[1][1].content

        assert result["current_status"] == "visual_designed"
        assert result["visual_diagnostics"]["repair_attempted"] is True
        assert "<!DOCTYPE html>" in result["slide_render_plans"][0]["html_content"]
        assert "doctype" in repair_prompt.lower() or "gradients" in repair_prompt.lower()
