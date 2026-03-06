"""Shared helpers for render-path preference enforcement."""

from typing import Optional


def get_render_path_preference(style_config: Optional[dict], theme_config: Optional[dict] = None) -> str:
    """Return a normalized render-path preference."""
    for config in (style_config or {}, theme_config or {}):
        preference = config.get("render_path_preference", "auto")
        if preference in ("path_a", "path_b", "auto"):
            return preference
    return "auto"


def enforce_render_path_preference(
    selected_path: str,
    style_config: Optional[dict],
    theme_config: Optional[dict] = None,
) -> str:
    """Override a selected path when the user picked a concrete render path."""
    preference = get_render_path_preference(style_config, theme_config)
    if preference in ("path_a", "path_b"):
        return preference
    if selected_path in ("path_a", "path_b"):
        return selected_path
    return "path_a"


def effective_render_paths(style_config: Optional[dict], theme_config: Optional[dict] = None) -> list[str]:
    """Return the supported render paths after preference overrides are applied."""
    preference = get_render_path_preference(style_config, theme_config)
    if preference in ("path_a", "path_b"):
        return [preference]

    for config in (style_config or {}, theme_config or {}):
        render_paths = [path for path in config.get("render_paths", []) if path in ("path_a", "path_b")]
        if render_paths:
            return render_paths
    return ["path_a"]
