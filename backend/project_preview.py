"""Preview helpers for current project state and historical snapshots."""

from __future__ import annotations


def _page_number(item: dict, fallback: int) -> int:
    return int(
        item.get("page_number")
        or item.get("slide_number")
        or item.get("page")
        or fallback
    )


def build_project_preview(state: dict) -> dict:
    """Build a consistent preview payload from persisted workflow state."""
    slide_files = list(state.get("slide_files", []) or [])
    slide_render_plans = list(state.get("slide_render_plans", []) or [])
    slides_data = list(state.get("slides_data", []) or [])
    render_progress = list(state.get("render_progress", []) or [])
    outline = list(state.get("outline", []) or [])

    slide_files_by_page = {
        _page_number(slide_file, index + 1): slide_file
        for index, slide_file in enumerate(slide_files)
    }
    plans_by_page = {
        _page_number(plan, index + 1): plan
        for index, plan in enumerate(slide_render_plans)
    }
    slides_by_page = {
        _page_number(slide, index + 1): slide
        for index, slide in enumerate(slides_data)
    }
    progress_by_page = {
        _page_number(progress, index + 1): progress
        for index, progress in enumerate(render_progress)
    }
    outline_by_page = {
        _page_number(section, index + 1): section
        for index, section in enumerate(outline)
    }

    page_numbers = set(slide_files_by_page)
    page_numbers.update(plans_by_page)
    page_numbers.update(slides_by_page)
    page_numbers.update(progress_by_page)
    page_numbers.update(outline_by_page)

    slides: list[dict] = []
    for page_number in sorted(page_numbers):
        slide_file = slide_files_by_page.get(page_number, {})
        plan = plans_by_page.get(page_number, {})
        slide_data = slides_by_page.get(page_number, {})
        progress = progress_by_page.get(page_number, {})
        outline_section = outline_by_page.get(page_number, {})

        title = (
            plan.get("title")
            or slide_data.get("title")
            or outline_section.get("title")
            or f"Slide {page_number}"
        )
        render_path = (
            plan.get("render_path")
            or progress.get("render_path")
            or slide_data.get("render_path")
            or slide_data.get("path_hint")
            or "path_a"
        )
        status = progress.get("status") or ("complete" if slide_file else "pending")
        preview_url = slide_file.get("thumbnail_url", "")
        if not preview_url and slide_file.get("type") == "image":
            preview_url = slide_file.get("path", "")

        slides.append(
            {
                "page_number": page_number,
                "title": title,
                "render_path": render_path,
                "status": status,
                "preview_url": preview_url,
                "artifact_url": slide_file.get("path", ""),
                "thumbnail_url": slide_file.get("thumbnail_url", ""),
            }
        )

    if not slides and outline:
        slides = [
            {
                "page_number": index + 1,
                "title": section.get("title", f"Slide {index + 1}"),
                "render_path": section.get("path_hint", "path_a"),
                "status": "pending",
                "preview_url": "",
                "artifact_url": "",
                "thumbnail_url": "",
            }
            for index, section in enumerate(outline)
        ]

    return {
        "slides_count": len(slides),
        "completed_slides": sum(1 for slide in slides if slide["status"] == "complete"),
        "failed_slides": sum(1 for slide in slides if slide["status"] == "failed"),
        "thumbnail_urls": [slide["preview_url"] for slide in slides if slide["preview_url"]],
        "slides": slides,
    }
