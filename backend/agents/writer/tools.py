"""
撰写 Agent (Writer) 工具函数
"""

from typing import List, Dict, Any


def format_outline_for_prompt(outline: List[Dict]) -> str:
    """将大纲格式化为提示语"""
    if not outline:
        return "暂无大纲"
    
    lines = []
    for i, section in enumerate(outline, 1):
        title = section.get("title", "未命名章节")
        slide_type = section.get("type", "content")
        key_points = section.get("key_points", [])
        
        line = f"{i}. [{slide_type}] {title}"
        if key_points:
            line += f"\n   要点: {', '.join(key_points)}"
        lines.append(line)
    
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


def validate_slides_content(slides: List[Dict]) -> tuple[bool, str]:
    """验证幻灯片内容"""
    if not slides:
        return False, "幻灯片内容不能为空"
    
    for i, slide in enumerate(slides):
        if not slide.get("title"):
            return False, f"第 {i+1} 页缺少标题"
    
    return True, "验证通过"


def create_default_slides_from_outline(outline: List[Dict]) -> List[Dict]:
    """基于大纲创建默认幻灯片内容"""
    slides = []
    
    for i, section in enumerate(outline):
        slide = {
            "page_number": i + 1,
            "section_id": section.get("id", f"section_{i}"),
            "title": section.get("title", f"第 {i+1} 页"),
            "layout_intent": _get_layout_from_type(section.get("type", "content")),
            "content": {
                "main_text": "",
                "bullet_points": section.get("key_points", []),
                "supporting_text": ""
            },
            "speaker_notes": section.get("notes", ""),
            "visual_needs": {
                "needs_image": False,
                "needs_chart": section.get("type") in ["chart", "data"],
                "chart_type": "bar" if section.get("type") == "chart" else None,
                "image_description": None
            }
        }
        slides.append(slide)
    
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
        "conclusion": "conclusion"
    }
    return type_to_layout.get(slide_type, "bullet_points")
