"""
Renderer Agent — dual-path rendering pipeline.

Reads from `slide_render_plans` (Visual agent output) when available.
Falls back to `slides_data` (legacy path) when slide_render_plans is absent.

Path A: html_content → html2pptx_runner.js → per-slide PPTX
Path B: image_prompt → generate_image.py (parallel batches) → PNG
Mixed: both paths combined, ordered by page_number, assembled into one PPTX

Design spec: docs/agent-prompt-redesign.md §Agent 5: Renderer
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Optional

from agents.renderer.paths import SlideRenderResult, render_slide
from agents.renderer.preflight import validate_renderer_preflight
from agents.renderer.tools import (
    add_bullet_points,
    add_text_to_placeholder,
    apply_theme_to_slide,
    create_presentation,
    get_layout_id,
    save_presentation,
)
from services.pptx_assembler import assemble_presentation
from services.object_storage import StoredObject, get_object_storage

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
_OUTPUT_DIR.mkdir(exist_ok=True)

_THUMBNAIL_DIR = _OUTPUT_DIR / "thumbnails"
_THUMBNAIL_DIR.mkdir(exist_ok=True)

# Batch size for parallel Path B image generation (spec: 3-5)
_IMAGE_BATCH_SIZE = 4

# Max concurrent renders (spec: Task #14)
_MAX_CONCURRENT_RENDERS = 3

# Overall workflow timeout (seconds) — 10 minutes per spec
_OVERALL_TIMEOUT = 600

# Status messages (spec: RENDERER_STATUS_MESSAGES)
_STATUS = {
    "start": "渲染引擎启动，开始生成演示文稿...",
    "path_a": "正在生成 HTML 幻灯片（Path A）...",
    "path_b": "正在 AI 生成幻灯片图片（Path B）...",
    "assemble": "正在组装 PPTX 文件...",
    "complete": "演示文稿生成完成！",
    "error": "渲染过程中出现错误",
    "partial_error": "部分幻灯片渲染失败，已跳过",
}


async def run(state: dict) -> dict[str, Any]:
    """
    Renderer Agent entry point.

    Routing priority:
    1. slide_render_plans present → full dual-path pipeline (Visual agent output)
    2. style_id in style_config / theme_config → dual-path via slides_data
    3. Otherwise → legacy python-pptx renderer (3-theme backward compat)
    """
    session_id: str = state.get("session_id", uuid.uuid4().hex)
    slide_render_plans: list[dict] = state.get("slide_render_plans", [])
    slides_data: list[dict] = state.get("slides_data", [])

    # Prefer explicit style_config, fall back to theme_config
    style_config: dict = state.get("style_config") or state.get("theme_config", {})

    if not slide_render_plans and not slides_data:
        return _error_result(state, "没有幻灯片数据可渲染")

    # Apply render_path_preference from style_config to override auto routing
    render_pref = style_config.get("render_path_preference", "auto")
    if render_pref in ("path_a", "path_b"):
        style_config = {**style_config, "render_paths": [render_pref]}

    try:
        result = await asyncio.wait_for(
            _dispatch(state, slide_render_plans, slides_data, style_config, session_id),
            timeout=_OVERALL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return _error_result(
            state,
            f"工作流超时（超过 {_OVERALL_TIMEOUT // 60} 分钟），请重试或减少幻灯片数量",
        )

    return result


async def _dispatch(
    state: dict,
    slide_render_plans: list[dict],
    slides_data: list[dict],
    style_config: dict,
    session_id: str,
) -> dict[str, Any]:
    """Route to the appropriate rendering pipeline."""
    if slide_render_plans:
        return await _run_from_render_plans(
            state, slide_render_plans, style_config, session_id
        )
    elif style_config.get("style_id"):
        return await _run_dual_path(state, slides_data, style_config, session_id)
    else:
        return await _run_legacy(state, slides_data, style_config, session_id)


# ---------------------------------------------------------------------------
# Primary path: Visual agent's slide_render_plans
# ---------------------------------------------------------------------------

async def _run_from_render_plans(
    state: dict,
    slide_render_plans: list[dict],
    style_config: dict,
    session_id: str,
) -> dict[str, Any]:
    """
    Execute rendering from Visual agent's slide_render_plans.

    Plans are dicts with: page_number, render_path, html_content, image_prompt.
    All slides rendered concurrently, capped at _MAX_CONCURRENT_RENDERS.
    """
    preflight_ok, preflight_message = validate_renderer_preflight(slide_render_plans, style_config)
    if not preflight_ok:
        return _error_result(state, f"Renderer preflight failed: {preflight_message}")

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_RENDERS)
    total = len(slide_render_plans)
    async def _one_with_semaphore(plan: dict, idx: int) -> SlideRenderResult:
        async with semaphore:
            loop = asyncio.get_running_loop()
            slide_data = {**plan, "render_path": plan.get("render_path", "path_a")}
            return await loop.run_in_executor(
                None, lambda: render_slide(slide_data, style_config, idx)
            )

    tasks = [_one_with_semaphore(p, i) for i, p in enumerate(slide_render_plans)]
    results: list[SlideRenderResult] = list(await asyncio.gather(*tasks))

    # Sort by slide_index to maintain page order
    results.sort(key=lambda r: r.slide_index)

    successful = [r for r in results if r.success]
    if not successful:
        errors = "; ".join(r.error or "unknown" for r in results[:3])
        return _error_result(state, f"All slides failed: {errors}")

    output_path = _OUTPUT_DIR / f"presentation_{session_id}.pptx"
    try:
        final_path = await asyncio.get_running_loop().run_in_executor(
            None, lambda: assemble_presentation(results, str(output_path))
        )
    except Exception as exc:
        return _error_result(state, f"Assembly failed: {exc}")

    try:
        stored_presentation = await _upload_presentation_async(final_path, session_id)
        slide_files, progress_events = await _persist_slide_outputs(
            results,
            session_id,
            total,
        )
    except Exception as exc:
        return _error_result(state, f"Object storage failed: {exc}")

    failed_errors = [f"Slide {r.slide_index+1}: {r.error}" for r in results if not r.success]
    return _success_result(
        state, stored_presentation, slide_files, total, failed_errors, progress_events
    )


# ---------------------------------------------------------------------------
# Secondary path: dual-path from slides_data (no render_plans yet)
# ---------------------------------------------------------------------------

async def _run_dual_path(
    state: dict,
    slides_data: list[dict],
    style_config: dict,
    session_id: str,
) -> dict[str, Any]:
    """Dual-path rendering directly from slides_data when render_plans absent."""
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_RENDERS)
    total = len(slides_data)
    async def _one(slide_data: dict, idx: int) -> SlideRenderResult:
        async with semaphore:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: render_slide(slide_data, style_config, idx)
            )

    tasks = [_one(slide, i) for i, slide in enumerate(slides_data)]
    results: list[SlideRenderResult] = list(await asyncio.gather(*tasks))

    successful = [r for r in results if r.success]
    if not successful:
        errors = "; ".join(r.error or "unknown" for r in results[:3])
        return _error_result(state, f"All slides failed: {errors}")

    output_path = _OUTPUT_DIR / f"presentation_{session_id}.pptx"
    try:
        loop = asyncio.get_running_loop()
        final_path = await loop.run_in_executor(
            None, lambda: assemble_presentation(results, str(output_path))
        )
    except Exception as exc:
        return _error_result(state, f"Assembly failed: {exc}")

    try:
        stored_presentation = await _upload_presentation_async(final_path, session_id)
        slide_files, progress_events = await _persist_slide_outputs(
            results,
            session_id,
            total,
        )
    except Exception as exc:
        return _error_result(state, f"Object storage failed: {exc}")

    failed_errors = [f"Slide {r.slide_index+1}: {r.error}" for r in results if not r.success]
    return _success_result(
        state, stored_presentation, slide_files, total, failed_errors, progress_events
    )


# ---------------------------------------------------------------------------
# Legacy python-pptx renderer (3-theme backward compat)
# ---------------------------------------------------------------------------

async def _run_legacy(
    state: dict,
    slides_data: list[dict],
    style_config: dict,
    session_id: str,
) -> dict[str, Any]:
    """Original python-pptx based rendering for legacy 3-theme configs."""
    try:
        loop = asyncio.get_running_loop()
        filepath = await loop.run_in_executor(
            None, lambda: _build_pptx_legacy(slides_data, style_config, session_id)
        )
        stored_presentation = await _upload_presentation_async(filepath, session_id)
        return {
            "pptx_path": stored_presentation.url,
            "pptx_storage_key": stored_presentation.key,
            "current_status": "render_complete",
            "current_agent": "renderer",
            "messages": state.get("messages", []) + [{
                "role": "assistant",
                "content": f"渲染引擎已生成 {len(slides_data)} 页演示文稿",
                "agent": "renderer",
            }],
        }
    except Exception as exc:
        return _error_result(state, str(exc))


def _build_pptx_legacy(slides_data: list[dict], theme_config: dict, session_id: str) -> str:
    prs = create_presentation()
    for slide_data in slides_data:
        _render_slide_legacy(prs, slide_data, theme_config)
    return save_presentation(prs, session_id)


def _render_slide_legacy(prs, slide_data: dict, theme_config: dict) -> None:
    layout_name = slide_data.get("layout_name", slide_data.get("layout_intent", "bullet_list"))
    layout_id = get_layout_id(layout_name, len(prs.slide_layouts))
    slide = prs.slides.add_slide(prs.slide_layouts[layout_id])
    apply_theme_to_slide(slide, theme_config)

    title = slide_data.get("title", "")
    if slide.shapes.title:
        add_text_to_placeholder(slide.shapes.title, title, theme_config, is_title=True)

    bullet_points = slide_data.get("content", {}).get("bullet_points", [])
    if bullet_points and len(slide.placeholders) > 1:
        for ph in slide.placeholders:
            if ph.placeholder_format.idx == 1:
                add_bullet_points(ph, bullet_points, theme_config)
                break

    notes = slide_data.get("speaker_notes", "")
    if notes:
        slide.notes_slide.notes_text_frame.text = notes


# ---------------------------------------------------------------------------
# Thumbnail generation
# ---------------------------------------------------------------------------

def _generate_thumbnail(image_path: str, session_id: str, slide_index: int) -> Optional[str]:
    """
    Create a small JPEG thumbnail (320×180) from a PNG slide image.

    Returns the local thumbnail path, or None on failure.
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return None

    try:
        src = Path(image_path)
        if not src.exists():
            return None

        thumb_name = f"thumb_{session_id}_{slide_index}.jpg"
        thumb_path = _THUMBNAIL_DIR / thumb_name

        with Image.open(src) as img:
            img.thumbnail((320, 180), Image.LANCZOS)
            # Convert RGBA → RGB so JPEG encoder doesn't fail
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(str(thumb_path), "JPEG", quality=80, optimize=True)

        return str(thumb_path)

    except Exception:
        return None


async def _generate_thumbnail_async(
    image_path: Optional[str],
    session_id: str,
    slide_index: int,
) -> Optional[str]:
    """Async wrapper for thumbnail generation (runs in thread pool)."""
    if not image_path:
        return None
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None,
            lambda: _generate_thumbnail(image_path, session_id, slide_index),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# render_progress event builder
# ---------------------------------------------------------------------------

def _make_render_progress_event(
    slide_number: int,
    total_slides: int,
    render_path: str,
    status: str,
    thumbnail_url: Optional[str] = None,
    error: Optional[str] = None,
) -> dict:
    """
    Build a render_progress SSE event payload.

    Schema:
      { type, slide_number, total_slides, render_path, status, thumbnail_url? }
    """
    event: dict = {
        "type": "render_progress",
        "slide_number": slide_number,
        "total_slides": total_slides,
        "render_path": render_path,
        "status": status,  # "complete" | "failed"
    }
    if thumbnail_url:
        event["thumbnail_url"] = thumbnail_url
    if error:
        event["error"] = error
    return event


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _success_result(
    state: dict,
    stored_presentation: StoredObject,
    slide_files: list[dict],
    total: int,
    failed_errors: list[str],
    render_progress_events: Optional[list[dict]] = None,
) -> dict[str, Any]:
    done = len(slide_files)
    content = f"渲染引擎已生成 {done}/{total} 页演示文稿"
    if failed_errors:
        content += f"，{len(failed_errors)} 页失败"
    result: dict[str, Any] = {
        "pptx_path": stored_presentation.url,
        "pptx_storage_key": stored_presentation.key,
        "slide_files": slide_files,
        "current_status": "render_complete",
        "current_agent": "renderer",
        "messages": state.get("messages", []) + [{
            "role": "assistant",
            "content": content,
            "agent": "renderer",
        }],
    }
    if render_progress_events:
        result["render_progress_events"] = render_progress_events
    return result


def _error_result(state: dict, message: str) -> dict[str, Any]:
    return {
        "current_status": "render_failed",
        "current_agent": "renderer",
        "error": message,
        "messages": state.get("messages", []) + [{
            "role": "assistant",
            "content": f"渲染引擎出错: {message}",
            "agent": "renderer",
        }],
    }


def _build_object_key(session_id: str, category: str, filename: str) -> str:
    return f"sessions/{session_id}/{category}/{filename}"


def _slide_artifact_kind(result: SlideRenderResult) -> str:
    if result.render_path in ("path_a", "path_a_fallback", "fallback_text"):
        return "html"
    return "image"


def _slide_content_type(result: SlideRenderResult) -> str:
    if _slide_artifact_kind(result) == "image":
        return "image/png"
    return "application/vnd.openxmlformats-officedocument.presentationml.presentation"


async def _upload_file_to_object_storage(
    local_path: str,
    object_key: str,
    content_type: str,
) -> StoredObject:
    loop = asyncio.get_running_loop()
    storage = get_object_storage()
    return await loop.run_in_executor(
        None,
        lambda: storage.upload_file(local_path, object_key, content_type),
    )


async def _upload_presentation_async(local_path: str, session_id: str) -> StoredObject:
    return await _upload_file_to_object_storage(
        local_path,
        _build_object_key(session_id, "presentations", f"presentation_{session_id}.pptx"),
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


async def _persist_slide_outputs(
    results: list[SlideRenderResult],
    session_id: str,
    total_slides: int,
) -> tuple[list[dict], list[dict]]:
    slide_files: list[dict] = []
    progress_events: list[dict] = []

    for result in sorted(results, key=lambda item: item.slide_index):
        thumbnail_url: Optional[str] = None

        if result.success and result.output_path:
            artifact_filename = f"slide_{result.slide_index + 1:03d}{Path(result.output_path).suffix}"
            stored_artifact = await _upload_file_to_object_storage(
                result.output_path,
                _build_object_key(session_id, "slides", artifact_filename),
                _slide_content_type(result),
            )
            slide_file = {
                "page_number": result.slide_index + 1,
                "path": stored_artifact.url,
                "storage_key": stored_artifact.key,
                "type": _slide_artifact_kind(result),
            }

            if result.render_path == "path_b":
                thumbnail_path = await _generate_thumbnail_async(
                    result.output_path,
                    session_id,
                    result.slide_index,
                )
                if thumbnail_path:
                    stored_thumbnail = await _upload_file_to_object_storage(
                        thumbnail_path,
                        _build_object_key(
                            session_id,
                            "thumbnails",
                            f"thumb_{result.slide_index + 1:03d}.jpg",
                        ),
                        "image/jpeg",
                    )
                    thumbnail_url = stored_thumbnail.url
                    slide_file["thumbnail_storage_key"] = stored_thumbnail.key
                    slide_file["thumbnail_url"] = stored_thumbnail.url

            slide_files.append(slide_file)

        progress_events.append(
            _make_render_progress_event(
                slide_number=result.slide_index + 1,
                total_slides=total_slides,
                render_path=result.render_path,
                status="complete" if result.success else "failed",
                thumbnail_url=thumbnail_url,
                error=result.error,
            )
        )

    return slide_files, progress_events
