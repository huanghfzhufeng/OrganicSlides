"""
撰写 Agent (Writer) - 主逻辑
负责生成每页的内容文本和演讲者备注
新增：image_prompt、path_hint、text_to_render 字段
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from agents.writer.prompts import (
    WRITER_REPAIR_SYSTEM_PROMPT,
    WRITER_REPAIR_USER_TEMPLATE,
    WRITER_SYSTEM_PROMPT,
    WRITER_USER_TEMPLATE,
)
from agents.writer.tools import (
    evaluate_slide_quality,
    format_outline_for_prompt,
    format_docs_for_context,
    build_style_context,
    validate_slides_content,
)
from agents.base import get_llm, create_system_message
from agents.structured_output import extract_json_payload, resolve_structured_output
from runtime_schemas import (
    build_research_packet,
    build_style_packet,
    serialize_models,
    validate_slide_specs,
    validation_error_message,
)


async def run(state: dict) -> dict[str, Any]:
    """
    撰写 Agent 入口函数
    根据大纲生成每页内容，含 image_prompt 和 path_hint
    """
    llm = get_llm(model="gpt-4o", temperature=0.7)

    outline = state.get("outline", [])
    user_intent = state.get("user_intent", "")
    try:
        research_packet = build_research_packet(
            user_intent,
            state.get("research_packet", {}).get("source_docs", state.get("source_docs", [])),
            state.get("research_packet", {}).get("search_results", state.get("search_results", [])),
        )
        style_packet = build_style_packet(
            style_id=state.get("style_id", ""),
            style_config=state.get("style_packet", state.get("style_config", {})),
            theme_config=state.get("theme_config", {}),
        )
    except ValidationError as exc:
        message = validation_error_message(exc)
        return {
            "slides_data": [],
            "current_status": "writer_error",
            "current_agent": "writer",
            "error": f"运行时 schema 校验失败: {message}",
            "messages": state.get("messages", []) + [
                {
                    "role": "assistant",
                    "content": f"撰稿人输入校验失败：{message}",
                    "agent": "writer",
                }
            ],
        }

    source_docs = serialize_models(research_packet.source_docs)
    style_id = style_packet.style_id
    style_config = serialize_models(style_packet)

    if not outline:
        return {
            "slides_data": [],
            "current_status": "writer_error",
            "current_agent": "writer",
            "error": "没有大纲可以撰写",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "撰稿人：缺少大纲内容", "agent": "writer"}
            ]
        }

    # 准备提示语
    outline_text = format_outline_for_prompt(outline)
    research_context = format_docs_for_context(source_docs)
    style_context = build_style_context(style_config)

    user_message = WRITER_USER_TEMPLATE.format(
        user_intent=user_intent,
        style_context=style_context,
        outline_text=outline_text,
        research_context=research_context,
    )

    messages = [
        create_system_message(WRITER_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    response = await llm.ainvoke(messages)

    result = await resolve_structured_output(
        llm=llm,
        raw_content=response.content,
        parser=_parse_slides_response,
        validator=lambda slides: _validate_slide_specs_response(slides, outline, style_config),
        repair_system_prompt=WRITER_REPAIR_SYSTEM_PROMPT,
        repair_user_template=WRITER_REPAIR_USER_TEMPLATE,
        repair_context={
            "user_intent": user_intent,
            "outline_text": outline_text,
            "style_context": style_context,
        },
    )

    if not result.success:
        return {
            "slides_data": [],
            "current_status": "writer_error",
            "current_agent": "writer",
            "error": f"撰稿输出无法修复: {result.error}",
            "writer_diagnostics": {
                "repair_attempted": len(result.attempts) > 1,
                "attempts": result.attempts,
            },
            "messages": state.get("messages", []) + [
                {
                    "role": "assistant",
                    "content": f"撰稿人输出修复失败：{result.error}",
                    "agent": "writer",
                }
            ],
        }

    slide_specs = validate_slide_specs(result.value)
    slides_data = serialize_models(slide_specs)

    return {
        "slides_data": slides_data,
        "research_packet": serialize_models(research_packet),
        "style_packet": style_config,
        "source_docs": source_docs,
        "style_id": style_id,
        "style_config": style_config,
        "current_status": "content_written",
        "current_agent": "writer",
        "writer_diagnostics": {
            "repair_attempted": len(result.attempts) > 1,
            "attempts": result.attempts,
        },
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": _build_success_message(slides_data, result.repaired),
                "agent": "writer"
            }
        ]
    }


def _parse_slides_response(content: str) -> list:
    """解析 LLM 响应中的幻灯片内容"""
    json_str = extract_json_payload(content)
    slides = json.loads(json_str)
    if not isinstance(slides, list):
        raise ValueError("writer output must be a JSON array")
    return slides


def _build_success_message(slides_data: list, repaired: bool) -> str:
    action = "修复并完成" if repaired else "已完成"
    return f"撰稿人{action} {len(slides_data)} 页内容撰写"


def _validate_slide_specs_response(
    slides: list,
    outline: list | None = None,
    style_config: dict | None = None,
) -> tuple[bool, str]:
    is_valid, message = validate_slides_content(slides, style_config)
    if not is_valid:
        return is_valid, message

    quality_is_valid, quality_message = evaluate_slide_quality(
        slides,
        outline=outline,
        style_config=style_config,
    )
    if not quality_is_valid:
        return False, quality_message

    try:
        validate_slide_specs(slides)
    except ValidationError as exc:
        return False, validation_error_message(exc)
    return True, "验证通过"
