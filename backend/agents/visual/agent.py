"""
视觉总监 Agent (Visual) - 主逻辑
核心职责：渲染路径决策者 + HTML 生成 + Path B 提示词完善
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from agents.visual.prompts import (
    VISUAL_REPAIR_SYSTEM_PROMPT,
    VISUAL_REPAIR_USER_TEMPLATE,
    VISUAL_SYSTEM_PROMPT,
    VISUAL_USER_TEMPLATE,
)
from agents.visual.tools import (
    build_style_context,
    create_slides_summary_for_visual,
    validate_visual_constraints,
)
from agents.base import get_llm, create_system_message
from agents.structured_output import extract_json_payload, resolve_structured_output
from rendering_policy import enforce_render_path_preference
from runtime_schemas import (
    build_style_packet,
    serialize_models,
    validate_render_plans,
    validate_slide_specs,
    validation_error_message,
)


async def run(state: dict) -> dict[str, Any]:
    """
    视觉总监 Agent 入口函数
    为每页确定渲染路径，生成 HTML（Path A）或完善 image_prompt（Path B）
    """
    llm = get_llm(model="gpt-4o", temperature=0.5)

    try:
        slide_specs = validate_slide_specs(state.get("slides_data", []))
        slides_data = serialize_models(slide_specs)
        style_packet = build_style_packet(
            style_id=state.get("style_id", ""),
            style_config=state.get("style_packet", state.get("style_config", {})),
            theme_config=state.get("theme_config", {}),
        )
        style_config = serialize_models(style_packet)
    except ValidationError as exc:
        message = validation_error_message(exc)
        return {
            "slide_render_plans": [],
            "render_path": "path_a",
            "current_status": "visual_error",
            "current_agent": "visual",
            "error": f"运行时 schema 校验失败: {message}",
            "messages": state.get("messages", []) + [
                {
                    "role": "assistant",
                    "content": f"视觉总监输入校验失败：{message}",
                    "agent": "visual",
                }
            ],
        }

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
    style_context = build_style_context(style_config)
    base_style_prompt = style_config.get("base_style_prompt", "")

    user_message = VISUAL_USER_TEMPLATE.format(
        style_config_json=json.dumps(style_config, ensure_ascii=False, indent=2),
        style_context=style_context,
        base_style_prompt=base_style_prompt or "（未指定基础风格提示词，使用 Path A HTML 渲染）",
        slides_summary=slides_summary,
    )

    messages = [
        create_system_message(VISUAL_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    response = await llm.ainvoke(messages)

    result = await resolve_structured_output(
        llm=llm,
        raw_content=response.content,
        parser=lambda content: _parse_visual_response(content, slides_data, style_config),
        validator=lambda plans: _validate_visual_plans(plans, slides_data, style_config),
        repair_system_prompt=VISUAL_REPAIR_SYSTEM_PROMPT,
        repair_user_template=VISUAL_REPAIR_USER_TEMPLATE,
        repair_context={
            "style_config_json": json.dumps(style_config, ensure_ascii=False, indent=2),
            "style_context": style_context,
            "slides_summary": slides_summary,
        },
    )

    if not result.success:
        return {
            "slide_render_plans": [],
            "render_path": "path_a",
            "current_status": "visual_error",
            "current_agent": "visual",
            "error": f"视觉方案无法修复: {result.error}",
            "visual_diagnostics": {
                "repair_attempted": len(result.attempts) > 1,
                "attempts": result.attempts,
            },
            "messages": state.get("messages", []) + [
                {
                    "role": "assistant",
                    "content": f"视觉总监输出修复失败：{result.error}",
                    "agent": "visual",
                }
            ],
        }

    slide_render_plans = result.value
    render_plans = validate_render_plans(slide_render_plans, style_packet)
    slide_render_plans = serialize_models(render_plans)

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
        "slides_data": slides_data,
        "style_packet": style_config,
        "style_config": style_config,
        "render_path": overall_path,
        "current_status": "visual_designed",
        "current_agent": "visual",
        "visual_diagnostics": {
            "repair_attempted": len(result.attempts) > 1,
            "attempts": result.attempts,
        },
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": _build_success_message(slide_render_plans, overall_path, result.repaired),
                "agent": "visual"
            }
        ]
    }


def _parse_visual_response(content: str, slides_data: list, style_config: dict) -> list:
    """解析 LLM 视觉设计响应"""
    json_str = extract_json_payload(content)
    plans = json.loads(json_str)
    if not isinstance(plans, list):
        raise ValueError("visual output must be a JSON array")

    normalized = []
    for index, plan in enumerate(plans):
        if not isinstance(plan, dict):
            raise ValueError(f"visual plan {index + 1} must be an object")

        slide = slides_data[index] if index < len(slides_data) else {}
        render_path = enforce_render_path_preference(
            plan.get("render_path", "path_a"),
            style_config,
        )

        normalized.append({
            "page_number": plan.get("page_number") or slide.get("page_number"),
            "render_path": render_path,
            "layout_name": plan.get("layout_name", "bullet_list"),
            "title": slide.get("title", ""),
            "content": slide.get("content", {}),
            "html_content": plan.get("html_content"),
            "image_prompt": plan.get("image_prompt"),
            "style_notes": plan.get("style_notes", ""),
            "color_system": plan.get("color_system") or {},
        })

    return normalized


def _validate_visual_plans(plans: list, slides_data: list, style_config: dict) -> tuple[bool, str]:
    if not plans:
        return False, "visual plans cannot be empty"

    if len(plans) != len(slides_data):
        return False, f"visual plans count {len(plans)} does not match slides count {len(slides_data)}"

    for index, plan in enumerate(plans):
        page_number = plan.get("page_number")
        if not page_number:
            return False, f"plan {index + 1} missing page_number"

        render_path = plan.get("render_path")
        if render_path not in {"path_a", "path_b"}:
            return False, f"plan {index + 1} has invalid render_path '{render_path}'"

        if render_path == "path_a" and not plan.get("html_content"):
            return False, f"plan {index + 1} missing html_content for path_a"

        if render_path == "path_b" and not plan.get("image_prompt"):
            return False, f"plan {index + 1} missing image_prompt for path_b"

        if not plan.get("title"):
            return False, f"plan {index + 1} missing title"

    style_is_valid, style_message = validate_visual_constraints(plans, slides_data, style_config)
    if not style_is_valid:
        return False, style_message

    try:
        validate_render_plans(plans, style_config)
    except ValidationError as exc:
        return False, validation_error_message(exc)

    return True, "验证通过"


def _build_success_message(plans: list, overall_path: str, repaired: bool) -> str:
    action = "修复并完成" if repaired else "已完成"
    return f"视觉总监{action} {len(plans)} 页视觉设计（渲染路径：{overall_path}）"
