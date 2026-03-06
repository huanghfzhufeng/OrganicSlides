"""
撰写 Agent (Writer) - 主逻辑
负责生成每页的内容文本和演讲者备注
新增：image_prompt、path_hint、text_to_render 字段
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage

from agents.writer.prompts import WRITER_SYSTEM_PROMPT, WRITER_USER_TEMPLATE
from agents.writer.tools import (
    format_outline_for_prompt,
    format_docs_for_context,
    build_style_context,
    validate_slides_content,
    create_default_slides_from_outline,
)
from agents.base import get_llm, create_system_message


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

    # 解析响应
    slides_data = _parse_slides_response(response.content, outline)

    # 验证内容
    is_valid, msg = validate_slides_content(slides_data)
    if not is_valid:
        slides_data = create_default_slides_from_outline(outline)

    return {
        "slides_data": slides_data,
        "current_status": "content_written",
        "current_agent": "writer",
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": f"撰稿人已完成 {len(slides_data)} 页内容撰写",
                "agent": "writer"
            }
        ]
    }


def _parse_slides_response(content: str, outline: list) -> list:
    """解析 LLM 响应中的幻灯片内容"""
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        return json.loads(json_str)

    except (json.JSONDecodeError, IndexError):
        return create_default_slides_from_outline(outline)
