"""Unit tests for renderer preflight validation."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import graph  # noqa: E402
from agents.renderer import agent as renderer_agent  # noqa: E402
from agents.renderer.preflight import validate_renderer_preflight  # noqa: E402


@pytest.mark.unit
class TestRendererPreflight:
    def test_validate_renderer_preflight_rejects_route_mismatch(self):
        plans = [
            {
                "page_number": 1,
                "render_path": "path_b",
                "image_prompt": "Visual Reference: reference section with enough detail.\n\nBase Style: detailed style.\n\nDesign Intent: audience should feel urgency.\n\nText to Render:\n- Title: \"增长趋势\"\n\nVisual Narrative: a long enough visual narrative for image generation.",
            }
        ]
        style_config = {
            "render_paths": ["path_a", "path_b"],
            "render_path_preference": "path_a",
        }

        is_valid, message = validate_renderer_preflight(plans, style_config)

        assert is_valid is False
        assert "does not match renderer routing" in message

    def test_validate_renderer_preflight_rejects_missing_local_html_asset(self):
        plans = [
            {
                "page_number": 1,
                "render_path": "path_a",
                "html_content": """
<!DOCTYPE html>
<html>
<body style="width: 720pt; height: 405pt;">
  <div><img src=\"missing-chart.png\" /></div>
</body>
</html>
""".strip(),
            }
        ]
        style_config = {"render_paths": ["path_a"]}

        is_valid, message = validate_renderer_preflight(plans, style_config)

        assert is_valid is False
        assert "missing local asset" in message

    @pytest.mark.asyncio
    async def test_render_preparation_rejects_preflight_errors(self):
        result = await graph.render_preparation_node(
            {
                "style_config": {"render_paths": ["path_a"]},
                "slide_render_plans": [
                    {
                        "page_number": 1,
                        "render_path": "path_a",
                        "layout_name": "bullet_list",
                        "title": "趋势已经分化",
                        "content": {"bullet_points": ["需求恢复"]},
                        "html_content": """
<!DOCTYPE html>
<html>
<body style="width: 720pt; height: 405pt;">
  <div><img src=\"missing-chart.png\" /></div>
</body>
</html>
""".strip(),
                    }
                ],
                "slides_data": [
                    {
                        "page_number": 1,
                        "title": "趋势已经分化",
                        "visual_type": "chart",
                        "path_hint": "path_a",
                        "content": {"bullet_points": ["需求恢复"]},
                    }
                ],
                "messages": [],
            }
        )

        assert result["current_status"] == "render_preparation_error"
        assert "missing local asset" in result["error"]

    @pytest.mark.asyncio
    async def test_renderer_rejects_preflight_errors_before_rendering(self):
        result = await renderer_agent.run(
            {
                "session_id": "session-1",
                "style_config": {"render_paths": ["path_a"]},
                "slide_render_plans": [
                    {
                        "page_number": 1,
                        "render_path": "path_a",
                        "layout_name": "bullet_list",
                        "title": "趋势已经分化",
                        "content": {"bullet_points": ["需求恢复"]},
                        "html_content": """
<!DOCTYPE html>
<html>
<body style="width: 720pt; height: 405pt;">
  <div><img src=\"missing-chart.png\" /></div>
</body>
</html>
""".strip(),
                    }
                ],
                "messages": [],
            }
        )

        assert result["current_status"] == "render_failed"
        assert "Renderer preflight failed" in result["error"]
