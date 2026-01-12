"""
视觉总监 Agent (Visual) - 主逻辑
负责决定布局、配图需求和视觉元素
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage

from agents.visual.prompts import VISUAL_SYSTEM_PROMPT, VISUAL_USER_TEMPLATE
from agents.visual.tools import create_slides_summary, apply_default_visual_design
from agents.base import get_llm, create_system_message


async def run(state: dict) -> dict[str, Any]:
    """
    视觉总监 Agent 入口函数
    为每页确定布局和视觉元素
    """
    llm = get_llm(model="gpt-4o", temperature=0.5)
    
    slides_data = state.get("slides_data", [])
    theme_config = state.get("theme_config", {})
    
    if not slides_data:
        return {
            "current_status": "visual_skipped",
            "current_agent": "visual",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "视觉总监：没有幻灯片内容需要处理", "agent": "visual"}
            ]
        }
    
    # 准备幻灯片内容摘要
    slides_summary = create_slides_summary(slides_data)
    
    user_message = VISUAL_USER_TEMPLATE.format(
        theme_config=json.dumps(theme_config, ensure_ascii=False),
        slides_summary=json.dumps(slides_summary, ensure_ascii=False, indent=2)
    )

    messages = [
        create_system_message(VISUAL_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]
    
    response = await llm.ainvoke(messages)
    
    # 解析响应并更新 slides_data
    slides_data = _apply_visual_design(response.content, slides_data)
    
    return {
        "slides_data": slides_data,
        "current_status": "visual_designed",
        "current_agent": "visual",
        "messages": state.get("messages", []) + [
            {"role": "assistant", "content": f"视觉总监已完成 {len(slides_data)} 页视觉设计", "agent": "visual"}
        ]
    }


def _apply_visual_design(content: str, slides_data: list) -> list:
    """应用视觉设计到幻灯片"""
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()
        
        visual_plans = json.loads(json_str)
        
        # 将视觉方案合并到 slides_data
        visual_map = {v.get("page_number"): v for v in visual_plans}
        
        for slide in slides_data:
            page_num = slide.get("page_number")
            if page_num in visual_map:
                visual = visual_map[page_num]
                slide["layout_id"] = visual.get("layout_id", 0)
                slide["layout_name"] = visual.get("layout_name", "bullet_list")
                slide["visual_elements"] = visual.get("visual_elements", [])
        
        return slides_data
        
    except (json.JSONDecodeError, IndexError):
        return apply_default_visual_design(slides_data)
