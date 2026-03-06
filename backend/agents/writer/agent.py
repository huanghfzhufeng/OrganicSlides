"""
撰写 Agent (Writer) - 主逻辑
负责生成每页的内容文本和演讲者备注
新增：image_prompt、path_hint、text_to_render 字段
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage

from agents.writer.prompts import (
    WRITER_REPAIR_SYSTEM_PROMPT,
    WRITER_REPAIR_USER_TEMPLATE,
    WRITER_SYSTEM_PROMPT,
    WRITER_USER_TEMPLATE,
)
from agents.writer.tools import (
    format_outline_for_prompt,
    format_docs_for_context,
    build_style_context,
    validate_slides_content,
)
from agents.base import get_llm, create_system_message
from agents.structured_output import extract_json_payload, resolve_structured_output


async def run(state: dict) -> dict[str, Any]:
    """
    撰写 Agent 入口函数
    根据大纲生成每页内容，含 image_prompt 和 path_hint
    """
    llm = get_llm(model="gpt-4o", temperature=0.7)

    outline = state.get("outline", [])
    user_intent = state.get("user_intent", "")
    source_docs = state.get("source_docs", [])
    style_id = state.get("style_id", "")
    style_config = state.get("style_config", {})

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
    style_context = build_style_context(style_id, style_config)

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
        validator=validate_slides_content,
        repair_system_prompt=WRITER_REPAIR_SYSTEM_PROMPT,
        repair_user_template=WRITER_REPAIR_USER_TEMPLATE,
        repair_context={
            "user_intent": user_intent,
            "outline_text": outline_text,
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

    slides_data = result.value

    return {
        "slides_data": slides_data,
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
