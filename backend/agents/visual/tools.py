"""
视觉总监 Agent (Visual) 工具函数
"""

import json
from typing import List, Dict, Any, Optional

from rendering_policy import effective_render_paths, enforce_render_path_preference, get_render_path_preference


def create_slides_summary_for_visual(slides_data: List[Dict]) -> str:
    """
    为 Visual agent 创建幻灯片内容摘要（JSON 格式）。
    包含 visual_type、path_hint、image_prompt、text_to_render 等关键字段。
    """
    summaries = []

    for slide in slides_data:
        content = slide.get("content", {})
        summaries.append({
            "page_number": slide.get("page_number"),
            "title": slide.get("title"),
            "visual_type": slide.get("visual_type", "illustration"),
            "path_hint": slide.get("path_hint", "auto"),
            "layout_intent": slide.get("layout_intent", "bullet_points"),
            "bullet_points": content.get("bullet_points", []),
            "main_text": content.get("main_text"),
            "image_prompt_draft": slide.get("image_prompt"),  # Writer's draft
            "text_to_render": slide.get("text_to_render", {}),
            "speaker_notes": slide.get("speaker_notes", ""),
        })

    return json.dumps(summaries, ensure_ascii=False, indent=2)


def build_style_context(style_config: Dict[str, Any]) -> str:
    """Build a high-signal StylePacket summary for the Visual agent."""
    if not style_config:
        return "未指定风格"

    name = (
        style_config.get("name_zh")
        or style_config.get("name_en")
        or style_config.get("style_id")
        or style_config.get("id")
        or "默认风格"
    )
    render_paths = effective_render_paths(style_config)
    render_preference = get_render_path_preference(style_config)
    prompt_constraints = style_config.get("prompt_constraints", {})

    lines = [
        f"当前风格：{name}",
        f"支持渲染路径：{', '.join(render_paths)}",
    ]
    if render_preference != "auto":
        lines.append(f"强制渲染偏好：{render_preference}")

    for key, label in [
        ("description", "风格描述"),
        ("reference_summary", "风格参考摘要"),
        ("movement_excerpt", "设计运动摘录"),
    ]:
        block = _format_optional_block(label, style_config.get(key, ""))
        if block:
            lines.append(block)

    design_principles_summary = _summarize_design_principles(
        style_config.get("design_principles_excerpt", "")
    )
    if design_principles_summary:
        lines.append(f"设计原则重点：{design_principles_summary}")

    if style_config.get("base_style_prompt"):
        lines.append(
            _format_optional_block("Base Style Prompt", style_config.get("base_style_prompt", ""))
        )

    required_sections = prompt_constraints.get("path_b_required_sections", [])
    if required_sections:
        lines.append(f"Path B 必填段落：{', '.join(required_sections)}")

    forbidden_terms = prompt_constraints.get("path_b_forbidden_terms", [])
    if forbidden_terms:
        lines.append(f"Path B 禁用词：{', '.join(forbidden_terms)}")

    path_a_rules = prompt_constraints.get("path_a_rules", [])
    if path_a_rules:
        lines.append(f"Path A 硬规则：{'; '.join(path_a_rules[:4])}")

    sample_asset_path = style_config.get("sample_asset_path", "")
    if sample_asset_path:
        lines.append(f"样例素材路径：{sample_asset_path}")

    reference_sources = style_config.get("reference_sources", [])
    if reference_sources:
        lines.append(f"参考来源：{', '.join(reference_sources[:4])}")

    return "\n".join(line for line in lines if line)


def determine_render_path(slide: Dict, style_config: Dict) -> str:
    """
    Determine the render path for a slide based on its properties and style config.
    Returns "path_a" or "path_b".
    """
    path_hint = slide.get("path_hint", "auto")
    visual_type = slide.get("visual_type", "illustration")
    style_render_paths = effective_render_paths(style_config)

    preferred_path = enforce_render_path_preference("auto", style_config)
    if preferred_path in ("path_a", "path_b"):
        return preferred_path

    # Explicit path_hint takes priority (except "auto")
    if path_hint == "path_b":
        # Only use path_b if style supports it
        if "path_b" in style_render_paths:
            return "path_b"
        return "path_a"  # Fallback if style doesn't support path_b

    if path_hint == "path_a":
        return "path_a"

    # Auto-decide based on visual_type and style
    if visual_type in ("chart", "data", "flow"):
        return "path_a"  # Precise layout needed

    if visual_type in ("illustration", "cover") and "path_b" in style_render_paths:
        return "path_b"

    if visual_type == "quote":
        # Quote works in both paths; prefer path_b for dramatic styles
        if "path_b" in style_render_paths and "path_a" not in style_render_paths:
            return "path_b"
        return "path_a"

    return "path_a"  # Safe default


def validate_visual_constraints(
    plans: List[Dict[str, Any]],
    slides_data: List[Dict[str, Any]],
    style_config: Dict[str, Any],
) -> tuple[bool, str]:
    """Validate render plans against StylePacket-supported paths and Path B prompt rules."""
    supported_render_paths = effective_render_paths(style_config)
    prompt_constraints = style_config.get("prompt_constraints", {})
    forbidden_terms = prompt_constraints.get("path_b_forbidden_terms", [])
    required_sections = prompt_constraints.get("path_b_required_sections", [])

    for index, plan in enumerate(plans):
        render_path = plan.get("render_path")
        if render_path not in supported_render_paths:
            return (
                False,
                f"plan {index + 1} uses unsupported render_path '{render_path}' "
                f"for current style ({', '.join(supported_render_paths)})",
            )

        if render_path != "path_b":
            continue

        image_prompt = str(plan.get("image_prompt") or "")
        if not image_prompt:
            continue

        missing_sections = _missing_required_sections(image_prompt, required_sections)
        if missing_sections:
            return (
                False,
                f"plan {index + 1} image_prompt missing required sections: "
                f"{', '.join(missing_sections)}",
            )

        matched_terms = _matched_forbidden_terms(image_prompt, forbidden_terms)
        if matched_terms:
            return (
                False,
                f"plan {index + 1} image_prompt contains forbidden terms: "
                f"{', '.join(matched_terms)}",
            )

        slide = slides_data[index] if index < len(slides_data) else {}
        expected_title = (
            slide.get("text_to_render", {}).get("title")
            or slide.get("title")
            or ""
        ).strip()
        if expected_title and expected_title not in image_prompt:
            return (
                False,
                f"plan {index + 1} image_prompt must include text_to_render title '{expected_title}'",
            )

    return True, "验证通过"


def build_default_image_prompt(slide: Dict, style_config: Dict) -> str:
    """Generate a basic Path B prompt when the upstream agent did not provide one."""
    explicit_prompt = slide.get("image_prompt")
    if explicit_prompt:
        return explicit_prompt

    title = slide.get("title") or slide.get("text_to_render", {}).get("title") or "presentation slide"
    bullet_points = slide.get("content", {}).get("bullet_points", [])
    bullet_summary = ", ".join(str(point) for point in bullet_points[:4])
    style_name = (
        style_config.get("name_en")
        or style_config.get("name_zh")
        or style_config.get("id")
        or "professional presentation"
    )

    if bullet_summary:
        return f"{style_name} slide illustration for '{title}', visualizing: {bullet_summary}"
    return f"{style_name} slide illustration for '{title}'"


def build_default_html(slide: Dict, style_config: Dict) -> str:
    """
    Generate a minimal valid Path A HTML for a slide using style_config colors.
    Used as fallback when LLM generation fails.
    """
    colors = style_config.get("colors", {})
    bg = colors.get("background", "#FFFFFF")
    text = colors.get("text", "#1A1A1A")
    accent = colors.get("accent", "#0984E3")

    title = slide.get("title", "")
    text_to_render = slide.get("text_to_render", {})
    display_title = text_to_render.get("title") or title
    bullets = text_to_render.get("bullets") or slide.get("content", {}).get("bullet_points", [])

    bullet_items = "".join(f"<li>{b}</li>" for b in bullets[:4])
    bullet_html = f"""
  <div style="position: absolute; top: 120pt; left: 48pt; right: 48pt;">
    <ul style="font-size: 14pt; color: {text}; padding-left: 20pt; list-style: disc; line-height: 1.8;">
      {bullet_items}
    </ul>
  </div>""" if bullet_items else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: 720pt; height: 405pt;
    font-family: system-ui, -apple-system, "PingFang SC", sans-serif;
    background: {bg};
    overflow: hidden;
  }}
</style>
</head>
<body>
  <div style="position: absolute; top: 4pt; left: 0; right: 0; height: 5pt; background: {accent};"></div>
  <div style="position: absolute; top: 32pt; left: 48pt; right: 48pt;">
    <h1 style="font-size: 28pt; color: {text}; font-weight: 700; line-height: 1.3;">{display_title}</h1>
  </div>
  {bullet_html}
</body>
</html>"""


def apply_default_visual_design(slides_data: List[Dict], style_config: Dict) -> List[Dict]:
    """
    Apply default visual design when LLM generation fails.
    Returns slide_render_plans (new list, no mutation).
    """
    plans = []
    for slide in slides_data:
        render_path = determine_render_path(slide, style_config)
        colors = style_config.get("colors", {})

        plan = {
            "page_number": slide.get("page_number"),
            "render_path": render_path,
            "layout_name": "bullet_list",
            "html_content": build_default_html(slide, style_config) if render_path == "path_a" else None,
            "image_prompt": build_default_image_prompt(slide, style_config) if render_path == "path_b" else None,
            "style_notes": f"Fallback: {render_path} selected based on visual_type={slide.get('visual_type')}",
            "color_system": {
                "background": colors.get("background", "#FFFFFF"),
                "text": colors.get("text", "#1A1A1A"),
                "accent": colors.get("accent", "#0984E3"),
            },
        }
        plans.append(plan)

    return plans


# Keep old function signature for backward compatibility
def create_slides_summary(slides_data: List[Dict]) -> List[Dict]:
    """Legacy: create simple slide summaries (for backward compat)."""
    return [
        {
            "page": slide.get("page_number"),
            "title": slide.get("title"),
            "visual_type": slide.get("visual_type", "illustration"),
            "path_hint": slide.get("path_hint", "auto"),
            "layout_intent": slide.get("layout_intent"),
        }
        for slide in slides_data
    ]


def _format_optional_block(title: str, content: str, max_chars: int = 700) -> str:
    compact = " ".join(str(content).split())
    if not compact:
        return ""
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + "..."
    return f"{title}：{compact}"


def _summarize_design_principles(content: str) -> str:
    compact = " ".join(str(content).split())
    if not compact:
        return ""

    highlights = []
    for phrase in [
        "Assertion-Evidence Framework",
        "Information Density",
        "Title = assertion",
        "One idea per slide",
    ]:
        if phrase in compact:
            highlights.append(phrase)

    if highlights:
        return "; ".join(highlights)

    if len(compact) > 240:
        return compact[:240].rstrip() + "..."
    return compact


def _missing_required_sections(image_prompt: str, required_sections: List[str]) -> List[str]:
    prompt_lower = image_prompt.lower()
    missing = []
    for section in required_sections:
        variants = _required_section_variants(section)
        if not any(variant in prompt_lower for variant in variants):
            missing.append(section)
    return missing


def _required_section_variants(section: str) -> List[str]:
    normalized = section.replace("_", " ").lower()
    variants = [normalized]
    aliases = {
        "visual_reference": ["visual reference"],
        "base_style": ["base style"],
        "design_intent": ["design intent"],
        "text_to_render": ["text to render"],
        "visual_narrative": ["visual narrative"],
    }
    variants.extend(aliases.get(section, []))
    return list(dict.fromkeys(variants))


def _matched_forbidden_terms(image_prompt: str, forbidden_terms: List[str]) -> List[str]:
    return sorted({term for term in forbidden_terms if term and term in image_prompt})
