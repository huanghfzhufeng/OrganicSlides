"""
视觉总监 Agent (Visual) - 主逻辑
核心职责：渲染路径决策者 + HTML 生成 + Path B 提示词完善
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage

from agents.visual.prompts import VISUAL_SYSTEM_PROMPT, VISUAL_USER_TEMPLATE
from agents.visual.tools import (
    create_slides_summary_for_visual,
    apply_default_visual_design,
    build_default_html,
    build_default_image_prompt,
)
from agents.base import get_llm, create_system_message
from rendering_policy import enforce_render_path_preference


async def run(state: dict) -> dict[str, Any]:
    """
    视觉总监 Agent 入口函数
    为每页确定渲染路径，生成 HTML（Path A）或完善 image_prompt（Path B）
    """
    llm = get_llm(model="gpt-4o", temperature=0.5)

    slides_data = state.get("slides_data", [])
    style_config = state.get("style_config") or state.get("theme_config", {})

    if not slides_data:
        return {
            "slide_render_plans": [],
            "render_path": "path_a",
            "current_status": "visual_skipped",
            "current_agent": "visual",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "视觉总监：没有幻灯片内容需要处理", "agent": "visual"}
            ]
        }

    # 准备幻灯片内容摘要（含新字段）
    slides_summary = create_slides_summary_for_visual(slides_data)
    base_style_prompt = style_config.get("base_style_prompt", "")

    user_message = VISUAL_USER_TEMPLATE.format(
        style_config_json=json.dumps(style_config, ensure_ascii=False, indent=2),
        base_style_prompt=base_style_prompt or "（未指定基础风格提示词，使用 Path A HTML 渲染）",
        slides_summary=slides_summary,
    )

    messages = [
        create_system_message(VISUAL_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    response = await llm.ainvoke(messages)

    # 解析视觉方案
    slide_render_plans = _parse_visual_response(response.content, slides_data, style_config)

    # Determine overall render_path
    paths_used = {p.get("render_path") for p in slide_render_plans}
    if paths_used == {"path_a"}:
        overall_path = "path_a"
    elif paths_used == {"path_b"}:
        overall_path = "path_b"
    else:
        overall_path = "mixed"

    return {
        "slide_render_plans": slide_render_plans,
        "render_path": overall_path,
        "current_status": "visual_designed",
        "current_agent": "visual",
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": f"视觉总监已完成 {len(slide_render_plans)} 页视觉设计（渲染路径：{overall_path}）",
                "agent": "visual"
            }
        ]
    }


def _parse_visual_response(content: str, slides_data: list, style_config: dict) -> list:
    """解析 LLM 视觉设计响应"""
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        plans = json.loads(json_str)

        # Validate that each plan has required fields; fill defaults if missing
        validated = []
        for index, plan in enumerate(plans):
            slide = slides_data[index] if index < len(slides_data) else {}
            render_path = enforce_render_path_preference(
                plan.get("render_path", "path_a"),
                style_config,
            )
            html_content = plan.get("html_content")
            image_prompt = plan.get("image_prompt")
            if render_path == "path_a" and not html_content:
                html_content = build_default_html(slide, style_config)
            if render_path == "path_b" and not image_prompt:
                image_prompt = build_default_image_prompt(slide, style_config)

            validated.append({
                "page_number": plan.get("page_number") or slide.get("page_number"),
                "render_path": render_path,
                "layout_name": plan.get("layout_name", "bullet_list"),
                "title": slide.get("title", ""),
                "content": slide.get("content", {}),
                "html_content": html_content if render_path == "path_a" else None,
                "image_prompt": image_prompt if render_path == "path_b" else None,
                "style_notes": plan.get("style_notes", ""),
                "color_system": plan.get("color_system", {}),
            })

        return validated

    except (json.JSONDecodeError, IndexError):
        # Fallback: deterministic visual design without LLM
        return apply_default_visual_design(slides_data, style_config)
