"""Unit tests for validated runtime schemas."""

from pathlib import Path

import pytest
from pydantic import ValidationError

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from runtime_schemas import (
    build_research_packet,
    build_style_packet,
    validate_render_plans,
    validate_slide_specs,
)
from state import create_initial_state


@pytest.mark.unit
class TestRuntimeSchemas:
    def test_build_research_packet_normalizes_documents_and_search_results(self):
        packet = build_research_packet(
            "新能源路演",
            [
                {
                    "chunk_id": "doc-1",
                    "content": "  这是参考内容  ",
                    "source": "huashu-slides/references/proven-styles-gallery.md",
                }
            ],
            [
                {
                    "title": "  Example  ",
                    "url": "https://example.com",
                    "snippet": "  useful snippet  ",
                }
            ],
        )

        assert packet.query == "新能源路演"
        assert packet.source_docs[0].content == "这是参考内容"
        assert packet.search_results[0].title == "Example"

    def test_build_style_packet_from_legacy_theme_config_produces_defaults(self):
        packet = build_style_packet(
            theme_config={
                "style": "organic",
                "colors": {
                    "background": "#FDFCF8",
                    "text": "#2C2C24",
                    "accent": "#A85448",
                },
            }
        )

        assert packet.id == "organic"
        assert packet.style_id == "organic"
        assert packet.render_paths == ["path_a"]
        assert packet.render_path_preference == "auto"
        assert packet.colors.background == "#FDFCF8"
        assert packet.prompt_constraints["path_a_rules"]
        assert "Assertion-Evidence Framework" in packet.design_principles_excerpt

    def test_create_initial_state_persists_research_and_style_packets(self):
        state = create_initial_state(
            session_id="session-1",
            user_intent="做一份答辩 PPT",
            theme="organic",
        )

        assert state["research_packet"]["query"] == "做一份答辩 PPT"
        assert state["style_packet"]["style_id"] == "organic"
        assert state["style_packet"]["render_paths"] == ["path_a"]

    def test_validate_slide_specs_normalizes_missing_fields(self):
        slides = validate_slide_specs(
            [
                {
                    "title": "先把稳定性补齐",
                    "visual_type": "illustration",
                    "path_hint": "path_b",
                    "layout_intent": "cover",
                    "content": {
                        "bullet_points": ["一", "二", "三", "四", "五"],
                    },
                    "image_prompt": "Warm illustration about stability first",
                    "speaker_notes": "展开解释",
                }
            ]
        )

        slide = slides[0]
        assert slide.page_number == 1
        assert slide.section_id == "section_1"
        assert slide.text_to_render.title == "先把稳定性补齐"
        assert slide.text_to_render.bullets == ["一", "二", "三", "四"]
        assert slide.content.bullet_points == ["一", "二", "三", "四"]

    def test_validate_slide_specs_rejects_path_b_slides_without_image_prompt(self):
        with pytest.raises(ValidationError):
            validate_slide_specs(
                [
                    {
                        "title": "必须先修基础",
                        "visual_type": "illustration",
                        "path_hint": "path_b",
                        "layout_intent": "cover",
                        "content": {"bullet_points": ["先修基础"]},
                    }
                ]
            )

    def test_validate_render_plans_applies_style_preference_and_color_defaults(self):
        style_packet = build_style_packet(
            style_config={
                "id": "01-snoopy",
                "name_zh": "Snoopy",
                "name_en": "Snoopy",
                "tier": 1,
                "colors": {
                    "background": "#FFF8E8",
                    "text": "#1A1A1A",
                    "accent": "#FF6B6B",
                },
                "typography": {},
                "use_cases": ["education"],
                "render_paths": ["path_a", "path_b"],
                "render_path_preference": "path_b",
            }
        )

        plans = validate_render_plans(
            [
                {
                    "page_number": 1,
                    "render_path": "path_a",
                    "layout_name": "cover",
                    "title": "先做质量内核",
                    "content": {"bullet_points": ["补齐 schema"]},
                    "image_prompt": "Editorial illustration for schema-first architecture",
                }
            ],
            style_packet,
        )

        plan = plans[0]
        assert plan.render_path == "path_b"
        assert plan.color_system.background == "#FFF8E8"
        assert plan.image_prompt == "Editorial illustration for schema-first architecture"

    def test_build_style_packet_assembles_reference_context_and_sample_asset(self):
        packet = build_style_packet(
            style_config={
                "id": "18-neo-brutalism",
                "name_zh": "Neo-Brutalism 新粗野主义",
                "name_en": "Neo-Brutalism",
                "description": "粗边框+色块+大字，远距离可读。",
                "tier": 1,
                "colors": {
                    "background": "#F5E6D3",
                    "text": "#1A1A1A",
                    "accent": "#FF3B4F",
                },
                "typography": {},
                "use_cases": ["education"],
                "render_paths": ["path_a", "path_b"],
                "sample_image_path": "/static/styles/samples/style-01-snoopy.png",
                "base_style_prompt": "Use bold blocks and thick borders.",
            }
        )

        assert "Neo-Brutalism" in packet.reference_summary
        assert "设计运动" in packet.movement_excerpt or "Neo-Brutalism" in packet.movement_excerpt
        assert packet.prompt_constraints["path_b_required_sections"] == [
            "visual_reference",
            "base_style",
            "design_intent",
            "text_to_render",
            "visual_narrative",
        ]
        assert packet.sample_asset_exists is True
        assert packet.sample_asset_path.endswith("backend/static/styles/samples/style-01-snoopy.png")
