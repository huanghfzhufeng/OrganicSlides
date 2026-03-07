"""
策划 Agent (Planner) 工具函数
"""

from typing import List, Dict, Any

from rendering_policy import effective_render_paths, get_render_path_preference


def format_docs_for_context(source_docs: List[Dict], max_docs: int = 3) -> str:
    """将检索到的文档格式化为上下文"""
    if not source_docs:
        return ""

    docs_text = "\n".join([
        f"[文档 {i+1}]: {doc.get('content', '')[:500]}..."
        for i, doc in enumerate(source_docs[:max_docs])
    ])
    return f"<参考文档>\n{docs_text}\n</参考文档>"


def format_search_for_context(search_results: List[Dict], max_results: int = 5) -> str:
    """将搜索结果格式化为上下文"""
    if not search_results:
        return ""

    search_text = "\n".join([
        f"[搜索 {i+1}]: {result.get('title', '')} - {result.get('snippet', '')[:200]}"
        for i, result in enumerate(search_results[:max_results])
    ])
    return f"<搜索结果>\n{search_text}\n</搜索结果>"


def build_context(source_docs: List[Dict], search_results: List[Dict]) -> str:
    """构建完整的研究上下文"""
    parts = []

    docs_context = format_docs_for_context(source_docs)
    if docs_context:
        parts.append(docs_context)

    search_context = format_search_for_context(search_results)
    if search_context:
        parts.append(search_context)

    return "\n\n".join(parts)


def build_style_context(style_config: dict) -> str:
    """构建风格上下文文本，供 Planner 使用完整 StylePacket。"""
    if not style_config:
        return "未指定风格（使用默认风格）"

    name = (
        style_config.get("name_zh")
        or style_config.get("name_en")
        or style_config.get("style_id")
        or style_config.get("id")
        or "默认风格"
    )
    render_paths = effective_render_paths(style_config)
    render_preference = get_render_path_preference(style_config)
    use_cases = style_config.get("use_cases", [])
    key_principles = style_config.get("key_principles", [])
    description = style_config.get("description", "")
    reference_sources = style_config.get("reference_sources", [])
    sample_asset_path = style_config.get("sample_asset_path", "")
    prompt_constraints = style_config.get("prompt_constraints", {})

    lines = [
        f"风格名称：{name}",
        f"支持渲染路径：{', '.join(render_paths)}",
    ]
    if render_preference != "auto":
        lines.append(f"强制渲染偏好：{render_preference}")
    if description:
        lines.append(f"风格描述：{description}")
    if use_cases:
        lines.append(f"适用场景：{', '.join(use_cases)}")
    if key_principles:
        lines.append(f"关键原则：{'; '.join(key_principles[:5])}")

    for title, content in [
        ("风格参考摘要", style_config.get("reference_summary", "")),
        ("风格画廊摘录", style_config.get("gallery_excerpt", "")),
        ("设计运动摘录", style_config.get("movement_excerpt", "")),
    ]:
        lines.extend(_format_optional_block(title, content))

    design_principles_summary = _summarize_design_principles(
        style_config.get("design_principles_excerpt", "")
    )
    if design_principles_summary:
        lines.append(f"设计原则重点：{design_principles_summary}")

    path_a_rules = prompt_constraints.get("path_a_rules", [])
    if path_a_rules:
        lines.append(f"Path A 硬规则：{'; '.join(path_a_rules[:4])}")
    if "path_b" in render_paths:
        required_sections = prompt_constraints.get("path_b_required_sections", [])
        if required_sections:
            lines.append(f"Path B prompt 必须包含：{', '.join(required_sections)}")
    if sample_asset_path:
        lines.append(f"样例素材路径：{sample_asset_path}")
    if reference_sources:
        lines.append(f"参考来源：{', '.join(reference_sources[:4])}")

    return "\n".join(lines)


def validate_outline(outline: List[Dict], style_config: dict | None = None) -> tuple[bool, str]:
    """
    验证大纲结构是否合法。
    包含新的断言句标题验证和 visual_type 字段验证。
    """
    if not outline:
        return False, "大纲不能为空"

    if len(outline) < 2:
        return False, "大纲至少需要 2 个章节"

    if len(outline) > 20:
        return False, "大纲不能超过 20 个章节"

    # 检查是否有封面
    has_cover = outline[0].get("slide_type") == "cover" or outline[0].get("type") == "cover"
    if not has_cover:
        return False, "大纲第一页应为封面页（slide_type: cover）"

    supported_render_paths = effective_render_paths(style_config)

    # 验证每个章节
    valid_visual_types = {"illustration", "chart", "flow", "quote", "data", "cover"}
    valid_path_hints = {"path_a", "path_b", "auto"}

    for i, section in enumerate(outline):
        title = section.get("title", "")

        # 标题不能为空
        if not title:
            return False, f"第 {i+1} 页缺少标题"

        # key_points 不超过 4 条
        key_points = section.get("key_points", [])
        if len(key_points) > 4:
            return False, f"第 {i+1} 页要点超过 4 条（当前 {len(key_points)} 条）"

        # visual_type 必须有效（如果提供）
        visual_type = section.get("visual_type")
        if visual_type and visual_type not in valid_visual_types:
            return False, f"第 {i+1} 页 visual_type '{visual_type}' 无效"

        # path_hint 必须有效（如果提供）
        path_hint = section.get("path_hint")
        if path_hint and path_hint not in valid_path_hints:
            return False, f"第 {i+1} 页 path_hint '{path_hint}' 无效"
        if path_hint in {"path_a", "path_b"} and path_hint not in supported_render_paths:
            return (
                False,
                f"第 {i+1} 页 path_hint '{path_hint}' 与当前风格支持路径 "
                f"{', '.join(supported_render_paths)} 不一致",
            )

    return True, "验证通过"


def normalize_outline(outline: List[Dict], style_config: dict | None = None) -> List[Dict]:
    """
    规范化大纲：确保所有必要字段存在，补全缺失字段的默认值。
    不修改原对象，返回新列表。
    """
    normalized = []
    supported_render_paths = effective_render_paths(style_config)
    render_preference = get_render_path_preference(style_config)

    for i, section in enumerate(outline):
        slide_type = section.get("slide_type") or section.get("type", "content")
        visual_type = section.get("visual_type", "illustration")
        if slide_type == "cover":
            visual_type = "cover"
        elif slide_type in ("chart", "data"):
            visual_type = "chart"

        path_hint = section.get("path_hint")
        if not path_hint:
            if render_preference in {"path_a", "path_b"}:
                path_hint = render_preference
            elif len(supported_render_paths) == 1:
                path_hint = supported_render_paths[0]
            else:
                path_hint = "auto"
        elif path_hint == "auto" and len(supported_render_paths) == 1:
            path_hint = supported_render_paths[0]

        normalized.append({
            **section,
            "slide_type": slide_type,
            "visual_type": visual_type,
            "path_hint": path_hint,
            "key_points": section.get("key_points", [])[:4],  # Enforce max 4
        })
    return normalized


def _format_optional_block(title: str, content: str, max_chars: int = 700) -> list[str]:
    compact = " ".join(str(content).split())
    if not compact:
        return []
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + "..."
    return [f"{title}：{compact}"]


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
