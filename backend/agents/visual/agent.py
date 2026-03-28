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
    validate_render_plans,
)
from agents.base import (
    extract_json_payload,
    get_llm,
    create_system_message,
    strip_thinking_tags,
)
from skills.runtime import build_skill_prompt_packet
from styles.context_builder import build_style_packet


async def run(state: dict) -> dict[str, Any]:
    """
    视觉总监 Agent 入口函数
    为每页确定渲染路径，生成 HTML（Path A）或完善 image_prompt（Path B）
    """
    llm = get_llm(temperature=0.5)

    slides_data = state.get("slides_data", [])
    style_config = state.get("style_config", {}) or {}
    skill_context = build_skill_prompt_packet(state.get("skill_packet"))
    theme_config = state.get("theme_config", {}) or {}
    if not style_config and theme_config.get("style_id"):
        # Resume flow writes style into theme_config first; keep visual stage style-aware.
        style_config = dict(theme_config)
    style_id = (
        state.get("style_id")
        or style_config.get("id")
        or style_config.get("style_id")
        or style_config.get("style", "")
    )

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
    style_packet = build_style_packet(style_id, style_config, state.get("user_intent", ""))

    user_message = VISUAL_USER_TEMPLATE.format(
        style_config_json=json.dumps(style_config, ensure_ascii=False, indent=2),
        skill_context=skill_context,
        style_packet=style_packet,
        base_style_prompt=base_style_prompt or "（未指定基础风格提示词，使用 Path A HTML 渲染）",
        slides_summary=slides_summary,
    )

    messages = [
        create_system_message(VISUAL_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    response = await llm.ainvoke(messages)

    # 解析视觉方案（剥离推理标签）
    raw_content = strip_thinking_tags(response.content)
    slide_render_plans = _parse_visual_response(raw_content, slides_data, style_config)
    is_valid, message = validate_render_plans(slide_render_plans, slides_data, style_config)
    if not is_valid:
        repaired = await _repair_visual_output(
            llm=llm,
            base_messages=messages,
            invalid_reason=message,
            slides_data=slides_data,
            style_config=style_config,
        )
        if repaired:
            slide_render_plans = repaired
            is_valid, message = validate_render_plans(slide_render_plans, slides_data, style_config)

    if not is_valid:
        slide_render_plans = apply_default_visual_design(slides_data, style_config)

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
        json_str = extract_json_payload(content)
        plans = json.loads(json_str)

        # Validate that each plan has required fields; fill defaults if missing
        validated = []
        for plan in plans:
            render_path = plan.get("render_path", "path_a")
            validated.append({
                "page_number": plan.get("page_number"),
                "render_path": render_path,
                "layout_name": plan.get("layout_name", "bullet_list"),
                "html_content": plan.get("html_content"),
                "image_prompt": plan.get("image_prompt"),
                "style_notes": plan.get("style_notes", ""),
                "color_system": plan.get("color_system", {}),
            })

        return validated

    except (json.JSONDecodeError, IndexError):
        return []


async def _repair_visual_output(
    llm,
    base_messages: list,
    invalid_reason: str,
    slides_data: list,
    style_config: dict,
) -> list:
    repair_message = HumanMessage(
        content=(
            "你上一次输出的视觉方案无效，原因如下：\n"
            f"{invalid_reason}\n\n"
            "请重新输出合法 JSON 数组，要求：\n"
            "1. 页数必须与幻灯片内容一致\n"
            "2. path_a 必须提供完整 html_content\n"
            "3. path_b 必须提供完整 image_prompt，且不得写布局方位词\n"
            "4. render_path 必须符合风格支持的路径\n"
            "5. 只返回 JSON，不要 markdown 代码块"
        )
    )
    response = await llm.ainvoke([*base_messages, repair_message])
    return _parse_visual_response(strip_thinking_tags(response.content), slides_data, style_config)
