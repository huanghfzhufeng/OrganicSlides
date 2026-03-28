"""策划 Agent (Planner) 工具函数。"""

from typing import List, Dict, Any
from styles.context_builder import build_style_packet


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


def build_style_context(style_id: str, style_config: dict, user_intent: str = "") -> str:
    """构建带本地知识摘录的 style packet，供 Planner 进行结构决策。"""
    return build_style_packet(style_id, style_config, user_intent)


def validate_outline(
    outline: List[Dict],
    *,
    is_thesis_mode: bool = False,
    min_slides: int = 4,
) -> tuple[bool, str]:
    """
    验证大纲结构是否合法。
    包含新的断言句标题验证和 visual_type 字段验证。
    """
    if not outline:
        return False, "大纲不能为空"

    if len(outline) < min_slides:
        return False, f"大纲页数不足：至少需要 {min_slides} 页，当前只有 {len(outline)} 页"

    if len(outline) > 20:
        return False, "大纲不能超过 20 个章节"

    # 检查是否有封面
    has_cover = outline[0].get("slide_type") == "cover" or outline[0].get("type") == "cover"
    if not has_cover:
        return False, "大纲第一页应为封面页（slide_type: cover）"

    # 验证每个章节
    valid_visual_types = {"illustration", "chart", "flow", "quote", "data", "cover"}
    valid_path_hints = {"path_a", "path_b", "auto"}
    has_data_like_slide = False
    has_conclusion_like_slide = False

    for i, section in enumerate(outline):
        title = str(section.get("title", "")).strip()
        slide_type = section.get("slide_type") or section.get("type", "content")

        # 标题不能为空
        if not title:
            return False, f"第 {i+1} 页缺少标题"

        if slide_type != "cover" and _is_generic_title(title):
            return False, f"第 {i+1} 页标题过于泛化：'{title}'"

        if slide_type not in {"cover", "quote"} and len(title) < 6:
            return False, f"第 {i+1} 页标题过短，无法承载完整断言：'{title}'"

        # key_points 不超过 4 条
        key_points = section.get("key_points", [])
        if len(key_points) > 4:
            return False, f"第 {i+1} 页要点超过 4 条（当前 {len(key_points)} 条）"
        for point in key_points:
            point_text = str(point).strip()
            if not point_text:
                return False, f"第 {i+1} 页存在空要点"
            if len(point_text) > 18:
                return False, f"第 {i+1} 页要点过长：'{point_text}'"

        # visual_type 必须有效（如果提供）
        visual_type = section.get("visual_type")
        if visual_type and visual_type not in valid_visual_types:
            return False, f"第 {i+1} 页 visual_type '{visual_type}' 无效"

        # path_hint 必须有效（如果提供）
        path_hint = section.get("path_hint")
        if path_hint and path_hint not in valid_path_hints:
            return False, f"第 {i+1} 页 path_hint '{path_hint}' 无效"

        if visual_type in {"chart", "data"} or slide_type in {"chart", "data"}:
            has_data_like_slide = True
        if slide_type == "conclusion" or any(token in title for token in ("结论", "建议", "行动", "下一步")):
            has_conclusion_like_slide = True

    if is_thesis_mode and not has_data_like_slide:
        return False, "答辩大纲至少需要 1 页图表/数据页"

    if not has_conclusion_like_slide:
        return False, "大纲缺少明确的结论/行动页"

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


def infer_min_outline_slides(
    user_intent: str,
    source_docs: List[Dict],
    *,
    is_thesis_mode: bool = False,
) -> int:
    if is_thesis_mode:
        return 10

    lowered = (user_intent or "").lower()
    complex_topic_tokens = (
        "复盘",
        "分析",
        "方案",
        "战略",
        "研究",
        "答辩",
        "路演",
        "论文",
        "项目",
        "产品",
        "汇报",
    )

    if source_docs:
        return 8

    if any(token in lowered for token in complex_topic_tokens):
        return 8

    if len((user_intent or "").strip()) >= 28:
        return 8

    return 6


_GENERIC_TITLES = {
    "背景",
    "研究背景",
    "背景介绍",
    "现状",
    "问题",
    "文献综述",
    "方法",
    "研究方法",
    "实验结果",
    "结果",
    "分析",
    "讨论",
    "结论",
    "总结",
    "致谢",
}


def _is_generic_title(title: str) -> bool:
    normalized = title.strip().replace("：", "").replace(":", "").replace(" ", "")
    return normalized in _GENERIC_TITLES
