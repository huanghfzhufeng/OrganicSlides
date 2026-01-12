"""
视觉总监 Agent (Visual) 工具函数
"""

from typing import List, Dict, Any


def calculate_text_length(content: Dict) -> int:
    """计算内容的文本长度"""
    main_text = content.get("main_text", "")
    bullet_points = content.get("bullet_points", [])
    supporting_text = content.get("supporting_text", "")
    
    total = len(str(main_text)) + len(str(supporting_text))
    total += sum(len(str(p)) for p in bullet_points)
    
    return total


def suggest_layout_from_content(slide: Dict) -> str:
    """根据内容建议布局"""
    content = slide.get("content", {})
    layout_intent = slide.get("layout_intent", "")
    visual_needs = slide.get("visual_needs", {})
    
    text_length = calculate_text_length(content)
    
    # 根据布局意图
    if layout_intent in ["cover", "title_slide"]:
        return "title_slide"
    
    if layout_intent in ["quote"]:
        return "blank"
    
    if layout_intent in ["conclusion"]:
        return "bullet_list"
    
    # 根据视觉需求
    if visual_needs.get("needs_chart"):
        return "two_content"
    
    if visual_needs.get("needs_image"):
        return "picture_with_caption"
    
    # 根据文本长度
    if text_length < 50:
        return "blank"  # 大字号居中
    elif text_length < 150:
        return "bullet_list"
    else:
        return "two_content"  # 双栏


def create_slides_summary(slides_data: List[Dict]) -> List[Dict]:
    """创建幻灯片内容摘要"""
    summaries = []
    
    for slide in slides_data:
        content = slide.get("content", {})
        text_length = calculate_text_length(content)
        
        summaries.append({
            "page": slide.get("page_number"),
            "title": slide.get("title"),
            "layout_intent": slide.get("layout_intent"),
            "text_length": text_length,
            "visual_needs": slide.get("visual_needs", {})
        })
    
    return summaries


def apply_default_visual_design(slides_data: List[Dict]) -> List[Dict]:
    """应用默认视觉设计"""
    for slide in slides_data:
        layout_name = suggest_layout_from_content(slide)
        slide["layout_id"] = get_layout_id(layout_name)
        slide["layout_name"] = layout_name
        slide["visual_elements"] = []
    
    return slides_data


def get_layout_id(layout_name: str) -> int:
    """获取布局 ID"""
    layout_map = {
        "title_slide": 0,
        "bullet_list": 1,
        "section_header": 2,
        "two_content": 3,
        "comparison": 4,
        "title_only": 5,
        "blank": 6,
        "content_with_caption": 7,
        "picture_with_caption": 8,
    }
    return layout_map.get(layout_name, 1)
