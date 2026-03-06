"""Unit tests for render path preference enforcement."""

from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from agents.renderer.paths import _choose_render_path
from agents.visual.tools import apply_default_visual_design, determine_render_path


@pytest.mark.unit
class TestRenderPathPreference:
    def test_determine_render_path_honors_explicit_preference(self):
        slide = {"path_hint": "path_a", "visual_type": "chart"}
        style_config = {
            "render_paths": ["path_a", "path_b"],
            "render_path_preference": "path_b",
        }

        assert determine_render_path(slide, style_config) == "path_b"

    def test_apply_default_visual_design_builds_path_b_plan_when_forced(self):
        slides = [
            {
                "page_number": 1,
                "title": "Growth",
                "visual_type": "data",
                "path_hint": "path_a",
                "content": {"bullet_points": ["Revenue up", "Costs down"]},
            }
        ]
        style_config = {
            "id": "01-snoopy",
            "name_en": "Snoopy",
            "render_paths": ["path_a", "path_b"],
            "render_path_preference": "path_b",
        }

        plans = apply_default_visual_design(slides, style_config)

        assert plans[0]["render_path"] == "path_b"
        assert plans[0]["image_prompt"]
        assert plans[0]["html_content"] is None

    def test_renderer_prefers_user_selected_render_path_over_slide_plan(self):
        slide_data = {"render_path": "path_b"}
        style_config = {
            "render_paths": ["path_a", "path_b"],
            "render_path_preference": "path_a",
        }

        assert _choose_render_path(slide_data, style_config) == "path_a"
