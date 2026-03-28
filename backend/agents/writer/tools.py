"""撰写 Agent (Writer) 工具函数。"""

from typing import List, Dict, Any, Optional
from styles.context_builder import build_style_packet


def format_outline_for_prompt(outline: List[Dict]) -> str:
    """将大纲格式化为提示语，包含 visual_type 和 path_hint"""
    if not outline:
        return "暂无大纲"

    lines = []
    for i, section in enumerate(outline, 1):
        title = section.get("title", "未命名章节")
        slide_type = section.get("slide_type") or section.get("type", "content")
        visual_type = section.get("visual_type", "illustration")
        path_hint = section.get("path_hint", "auto")
        key_points = section.get("key_points", [])
        notes = section.get("notes", "")

        line = f"{i}. [{slide_type}] {title}"
        line += f"\n   视觉类型: {visual_type} | 渲染提示: {path_hint}"
        if key_points:
            line += f"\n   要点: {', '.join(key_points)}"
        if notes:
            line += f"\n   备注: {notes}"
        lines.append(line)

    return "\n".join(lines)


def format_blueprint_for_prompt(slide_blueprint: List[Dict]) -> str:
    """将页级策划格式化为 Writer 可消费的提示语。"""
    if not slide_blueprint:
        return "暂无页级策划"

    lines = []
    for item in slide_blueprint:
        page_number = item.get("page_number", "?")
        title = item.get("title", "未命名页面")
        goal = item.get("goal", "")
        key_points = item.get("key_points", [])
        visual_type = item.get("visual_type", "illustration")
        path_hint = item.get("path_hint", "auto")
        content_brief = item.get("content_brief", "")

        lines.append(f"{page_number}. {title}")
        lines.append(f"   页面目标: {goal}")
        lines.append(f"   视觉类型: {visual_type} | 渲染提示: {path_hint}")
        if key_points:
            lines.append(f"   要点: {', '.join(str(point) for point in key_points[:4])}")
        if content_brief:
            lines.append(f"   内容摘要: {content_brief}")

    return "\n".join(lines)


def format_docs_for_context(source_docs: List[Dict], max_docs: int = 3) -> str:
    """将文档格式化为上下文"""
    if not source_docs:
        return ""

    docs_text = "\n".join([
        f"[来源 {i+1}]: {doc.get('content', '')[:300]}..."
        for i, doc in enumerate(source_docs[:max_docs])
    ])
    return f"<参考资料>\n{docs_text}\n</参考资料>"


def build_style_context(style_id: str, style_config: dict, user_intent: str = "") -> str:
    """构建带本地风格知识摘录的 style packet，供 Writer 稳定写内容和 image_prompt。"""
    return build_style_packet(style_id, style_config, user_intent)


def validate_slides_content(
    slides: List[Dict],
    *,
    outline: Optional[List[Dict]] = None,
) -> tuple[bool, str]:
    """
    验证幻灯片内容，包含新字段的验证。
    """
    if not slides:
        return False, "幻灯片内容不能为空"

    if outline is not None and len(slides) != len(outline):
        return False, f"幻灯片页数与大纲不一致：期望 {len(outline)} 页，实际 {len(slides)} 页"

    valid_visual_types = {"illustration", "chart", "flow", "quote", "data", "cover"}
    valid_path_hints = {"path_a", "path_b", "auto"}
    banned_layout_words = ("左", "右", "居中", "偏上", "顶部", "字号", "font-size", "position")

    for i, slide in enumerate(slides):
        # 标题必须存在
        title = str(slide.get("title", "")).strip()
        if not title:
            return False, f"第 {i+1} 页缺少标题"
        if len(title) < 4:
            return False, f"第 {i+1} 页标题过短：'{title}'"

        # bullet_points 不超过 4 条
        bullet_points = slide.get("content", {}).get("bullet_points", [])
        if len(bullet_points) > 4:
            return False, f"第 {i+1} 页要点超过 4 条（当前 {len(bullet_points)} 条）"
        for point in bullet_points:
            point_text = str(point).strip()
            if not point_text:
                return False, f"第 {i+1} 页存在空要点"
            if len(point_text) > 18:
                return False, f"第 {i+1} 页要点过长：'{point_text}'"

        # visual_type 校验
        visual_type = slide.get("visual_type")
        if visual_type and visual_type not in valid_visual_types:
            return False, f"第 {i+1} 页 visual_type '{visual_type}' 无效"

        # path_hint 校验
        path_hint = slide.get("path_hint")
        if path_hint and path_hint not in valid_path_hints:
            return False, f"第 {i+1} 页 path_hint '{path_hint}' 无效"

        # illustration/cover/path_b 页面需要 image_prompt
        needs_image_prompt = (
            visual_type in ("illustration", "cover")
            or path_hint == "path_b"
        )
        image_prompt = str(slide.get("image_prompt", "") or "").strip()
        if needs_image_prompt and not image_prompt:
            return False, f"第 {i+1} 页缺少 image_prompt"
        if path_hint == "path_b" and any(word in image_prompt for word in banned_layout_words):
            return False, f"第 {i+1} 页 image_prompt 仍在描述布局而非场景"

        text_to_render = slide.get("text_to_render", {}) or {}
        if not str(text_to_render.get("title", "")).strip():
            return False, f"第 {i+1} 页缺少 text_to_render.title"

    return True, "验证通过"


def create_default_slides_from_outline(outline: List[Dict]) -> List[Dict]:
    """基于大纲创建默认幻灯片内容，包含新字段"""
    slides = []

    for i, section in enumerate(outline):
        slide_type = section.get("slide_type") or section.get("type", "content")
        visual_type = section.get("visual_type", "illustration")
        path_hint = section.get("path_hint", "auto")
        title = section.get("title", f"第 {i+1} 页")

        slide = {
            "page_number": i + 1,
            "section_id": section.get("id", f"section_{i}"),
            "title": title,
            "visual_type": visual_type,
            "path_hint": path_hint,
            "layout_intent": _get_layout_from_type(slide_type),
            "content": {
                "main_text": None,
                "bullet_points": section.get("key_points", [])[:4],
                "supporting_text": None,
            },
            "image_prompt": _generate_default_image_prompt(title, visual_type) if visual_type in ("illustration", "cover") else None,
            "text_to_render": {
                "title": title[:8] if len(title) > 8 else title,
                "subtitle": None,
                "bullets": section.get("key_points", [])[:4],
            },
            "speaker_notes": section.get("notes", ""),
        }
        slides.append(slide)

    return slides


def create_default_slides_from_blueprint(slide_blueprint: List[Dict]) -> List[Dict]:
    """基于页级策划创建默认幻灯片内容。"""
    slides: List[Dict] = []

    for item in slide_blueprint:
        slide_type = item.get("slide_type", "content")
        visual_type = item.get("visual_type", "illustration")
        path_hint = item.get("path_hint", "auto")
        title = item.get("title", "未命名页面")
        key_points = item.get("key_points", [])[:4]

        slides.append(
            {
                "page_number": item.get("page_number", len(slides) + 1),
                "section_id": item.get("section_id", item.get("id", f"section_{len(slides)}")),
                "title": title,
                "visual_type": visual_type,
                "path_hint": path_hint,
                "layout_intent": _get_layout_from_type(slide_type),
                "content": {
                    "main_text": item.get("content_brief"),
                    "bullet_points": key_points,
                    "supporting_text": None,
                },
                "image_prompt": _generate_default_image_prompt(title, visual_type) if visual_type in ("illustration", "cover", "quote") else None,
                "text_to_render": {
                    "title": title[:8] if len(title) > 8 else title,
                    "subtitle": None,
                    "bullets": key_points,
                },
                "speaker_notes": item.get("speaker_notes") or item.get("goal", ""),
            }
        )

    return slides


def _get_layout_from_type(slide_type: str) -> str:
    """根据章节类型获取布局意图"""
    type_to_layout = {
        "cover": "cover",
        "content": "bullet_points",
        "data": "data_driven",
        "comparison": "two_column",
        "quote": "quote",
        "chart": "data_driven",
        "conclusion": "conclusion",
    }
    return type_to_layout.get(slide_type, "bullet_points")


def _generate_default_image_prompt(title: str, visual_type: str) -> Optional[str]:
    """为默认幻灯片生成基础 image_prompt"""
    if visual_type == "cover":
        return f"温暖开篇画面，传达关于「{title}」的期待感和好奇心，简洁有力"
    elif visual_type == "illustration":
        return f"一个视觉比喻，帮助理解「{title}」的核心概念，情绪温暖清晰"
    return None
