"""
策划 Agent (Planner) 工具函数
"""

from typing import List, Dict, Any


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


def build_style_context(style_id: str, style_config: dict) -> str:
    """构建风格上下文文本，供 Planner 了解当前风格"""
    if not style_config:
        return "未指定风格（使用默认风格）"

    name = style_config.get("name_zh") or style_config.get("name_en", style_id)
    render_paths = style_config.get("render_paths", ["path_a"])
    use_cases = style_config.get("use_cases", [])

    lines = [
        f"风格名称：{name}",
        f"渲染路径偏好：{', '.join(render_paths)}",
    ]
    if use_cases:
        lines.append(f"适用场景：{', '.join(use_cases)}")

    # 如果是插画/漫画风格，提示更多 path_b 页面
    if "path_b" in render_paths:
        lines.append("提示：此风格支持全AI视觉生成，封面、插画页建议 path_hint = path_b")

    return "\n".join(lines)


def validate_outline(outline: List[Dict]) -> tuple[bool, str]:
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

    return True, "验证通过"


def normalize_outline(outline: List[Dict]) -> List[Dict]:
    """
    规范化大纲：确保所有必要字段存在，补全缺失字段的默认值。
    不修改原对象，返回新列表。
    """
    normalized = []
    for i, section in enumerate(outline):
        slide_type = section.get("slide_type") or section.get("type", "content")
        visual_type = section.get("visual_type", "illustration")
        if slide_type == "cover":
            visual_type = "cover"
        elif slide_type in ("chart", "data"):
            visual_type = "chart"

        normalized.append({
            **section,
            "slide_type": slide_type,
            "visual_type": visual_type,
            "path_hint": section.get("path_hint", "auto"),
            "key_points": section.get("key_points", [])[:4],  # Enforce max 4
        })
    return normalized
