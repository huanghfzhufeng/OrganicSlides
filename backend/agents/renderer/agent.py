"""
渲染引擎 Agent (Renderer) - 主逻辑
负责调用 python-pptx 生成最终的 .pptx 文件
"""

import uuid
from typing import Any

from agents.renderer.tools import (
    create_presentation,
    save_presentation,
    apply_theme_to_slide,
    add_text_to_placeholder,
    add_bullet_points,
    get_layout_id
)


async def run(state: dict) -> dict[str, Any]:
    """
    渲染引擎 Agent 入口函数
    使用 python-pptx 生成最终文件
    """
    slides_data = state.get("slides_data", [])
    theme_config = state.get("theme_config", {})
    session_id = state.get("session_id", uuid.uuid4().hex)
    
    if not slides_data:
        return {
            "current_status": "render_failed",
            "current_agent": "renderer",
            "error": "没有幻灯片数据可渲染",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "渲染引擎：没有内容可渲染", "agent": "renderer"}
            ]
        }
    
    try:
        # 创建演示文稿
        prs = create_presentation()
        
        # 遍历生成每页
        for slide_data in slides_data:
            _render_slide(prs, slide_data, theme_config)
        
        # 保存文件
        filepath = save_presentation(prs, session_id)
        
        return {
            "pptx_path": filepath,
            "current_status": "render_complete",
            "current_agent": "renderer",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": f"渲染引擎已生成 {len(slides_data)} 页演示文稿", "agent": "renderer"}
            ]
        }
        
    except Exception as e:
        return {
            "current_status": "render_failed",
            "current_agent": "renderer",
            "error": str(e),
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": f"渲染引擎出错: {str(e)}", "agent": "renderer"}
            ]
        }


def _render_slide(prs, slide_data: dict, theme_config: dict):
    """渲染单个幻灯片"""
    layout_name = slide_data.get("layout_name", slide_data.get("layout_intent", "bullet_list"))
    layout_id = get_layout_id(layout_name, len(prs.slide_layouts))
    
    slide_layout = prs.slide_layouts[layout_id]
    slide = prs.slides.add_slide(slide_layout)
    
    # 应用主题
    apply_theme_to_slide(slide, theme_config)
    
    # 设置标题
    title = slide_data.get("title", "")
    if slide.shapes.title:
        add_text_to_placeholder(slide.shapes.title, title, theme_config, is_title=True)
    
    # 添加内容
    content = slide_data.get("content", {})
    bullet_points = content.get("bullet_points", [])
    
    if bullet_points and len(slide.placeholders) > 1:
        # 查找内容占位符
        for placeholder in slide.placeholders:
            if placeholder.placeholder_format.idx == 1:
                add_bullet_points(placeholder, bullet_points, theme_config)
                break
    
    # 添加演讲者备注
    notes = slide_data.get("speaker_notes", "")
    if notes:
        notes_slide = slide.notes_slide
        notes_tf = notes_slide.notes_text_frame
        notes_tf.text = notes
