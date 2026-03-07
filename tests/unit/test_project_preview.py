"""Unit tests for persisted project preview assembly."""

from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from project_preview import build_project_preview


@pytest.mark.unit
class TestProjectPreview:
    def test_build_project_preview_prefers_thumbnail_and_titles(self):
        preview = build_project_preview(
            {
                "outline": [
                    {"id": "1", "title": "封面结论", "path_hint": "path_b"},
                    {"id": "2", "title": "第二页观点", "path_hint": "path_a"},
                ],
                "slide_render_plans": [
                    {"page_number": 1, "title": "封面结论", "render_path": "path_b"},
                    {"page_number": 2, "title": "第二页观点", "render_path": "path_a"},
                ],
                "slide_files": [
                    {
                        "page_number": 1,
                        "type": "image",
                        "path": "http://localhost/slides/slide_001.png",
                        "thumbnail_url": "http://localhost/thumbs/thumb_001.jpg",
                    },
                    {
                        "page_number": 2,
                        "type": "html",
                        "path": "http://localhost/slides/slide_002.pptx",
                    },
                ],
                "render_progress": [
                    {"slide_number": 1, "render_path": "path_b", "status": "complete"},
                    {"slide_number": 2, "render_path": "path_a", "status": "complete"},
                ],
            }
        )

        assert preview["slides_count"] == 2
        assert preview["completed_slides"] == 2
        assert preview["thumbnail_urls"] == ["http://localhost/thumbs/thumb_001.jpg"]
        assert preview["slides"][0]["title"] == "封面结论"
        assert preview["slides"][0]["preview_url"] == "http://localhost/thumbs/thumb_001.jpg"
        assert preview["slides"][1]["title"] == "第二页观点"
        assert preview["slides"][1]["preview_url"] == ""

    def test_build_project_preview_falls_back_to_outline_when_no_assets_exist(self):
        preview = build_project_preview(
            {
                "outline": [
                    {"id": "1", "title": "断言一", "path_hint": "path_b"},
                    {"id": "2", "title": "断言二", "path_hint": "path_a"},
                ]
            }
        )

        assert preview["slides_count"] == 2
        assert preview["completed_slides"] == 0
        assert preview["failed_slides"] == 0
        assert [slide["title"] for slide in preview["slides"]] == ["断言一", "断言二"]
        assert preview["slides"][0]["status"] == "pending"
