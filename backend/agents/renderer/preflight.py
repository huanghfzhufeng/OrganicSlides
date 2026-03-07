"""Renderer preflight validation for routes, HTML, prompts, and local assets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agents.renderer.paths import _choose_render_path


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ASSET_PATTERNS = [
    re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE),
    re.compile(r"""url\((['"]?)([^'")]+)\1\)""", re.IGNORECASE),
]


def validate_renderer_preflight(
    plans: list[dict[str, Any]],
    style_config: dict[str, Any],
) -> tuple[bool, str]:
    """Validate final render plans before they reach the renderer."""
    for index, plan in enumerate(plans):
        plan_path = plan.get("render_path")
        routed_path = _choose_render_path(plan, style_config)
        if routed_path != plan_path:
            return (
                False,
                f"plan {index + 1} render_path '{plan_path}' does not match renderer routing '{routed_path}'",
            )

        if plan_path == "path_a":
            is_valid, message = _validate_path_a_preflight(plan)
        elif plan_path == "path_b":
            is_valid, message = _validate_path_b_preflight(plan)
        else:
            return False, f"plan {index + 1} has unsupported render_path '{plan_path}'"

        if not is_valid:
            return False, f"plan {index + 1} {message}"

    return True, "验证通过"


def _validate_path_a_preflight(plan: dict[str, Any]) -> tuple[bool, str]:
    html_file = str(plan.get("html_file") or "").strip()
    html_content = str(plan.get("html_content") or "")

    if html_file:
        resolved_html = _resolve_local_path(html_file)
        if not resolved_html or not resolved_html.exists():
            return False, f"html_file does not exist: {html_file}"

    if not html_content and not html_file:
        return False, "requires html_content or html_file"

    for asset_path in _extract_local_asset_paths(html_content):
        resolved_asset = _resolve_local_path(asset_path)
        if not resolved_asset or not resolved_asset.exists():
            return False, f"references missing local asset: {asset_path}"

    return True, "验证通过"


def _validate_path_b_preflight(plan: dict[str, Any]) -> tuple[bool, str]:
    image_prompt = str(plan.get("image_prompt") or "")
    if not image_prompt:
        return False, "requires image_prompt"
    if len("".join(image_prompt.split())) < 40:
        return False, "image_prompt is too short for stable rendering"
    return True, "验证通过"


def _extract_local_asset_paths(html_content: str) -> list[str]:
    if not html_content:
        return []

    assets: list[str] = []
    for pattern in _ASSET_PATTERNS:
        for match in pattern.findall(html_content):
            raw_path = match[1] if isinstance(match, tuple) else match
            path = str(raw_path).strip()
            if not path or _is_external_or_data_asset(path):
                continue
            assets.append(path)
    return list(dict.fromkeys(assets))


def _is_external_or_data_asset(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith(("http://", "https://", "data:", "blob:"))


def _resolve_local_path(path: str) -> Path | None:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    for base in (Path.cwd(), _PROJECT_ROOT):
        resolved = (base / candidate).resolve()
        if resolved.exists():
            return resolved
    return (_PROJECT_ROOT / candidate).resolve()
