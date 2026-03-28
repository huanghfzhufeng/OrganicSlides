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
    format_blueprint_for_prompt,
    format_outline_for_prompt,
    format_docs_for_context,
    build_style_context,
    validate_slides_content,
    create_default_slides_from_blueprint,
    create_default_slides_from_outline,
)
from agents.base import get_llm, create_system_message, strip_thinking_tags
from agents.base import extract_json_payload
from skills.runtime import build_skill_prompt_packet


async def run(state: dict) -> dict[str, Any]:
    """
    撰写 Agent 入口函数
    根据大纲生成每页内容，含 image_prompt 和 path_hint
    """
    llm = get_llm(temperature=0.7)

    outline = state.get("outline", [])
    slide_blueprint = state.get("slide_blueprint", [])
    user_intent = state.get("user_intent", "")
    source_docs = state.get("source_docs", [])
    skill_context = build_skill_prompt_packet(state.get("skill_packet"))
    style_config = state.get("style_config", {}) or {}
    theme_config = state.get("theme_config", {}) or {}
    if not style_config and theme_config.get("style_id"):
        # Style is selected in step 3 and stored in theme_config for backward compat.
        # Fall back so Writer can still emit style-aware image_prompt.
        style_config = dict(theme_config)

    style_id = (
        state.get("style_id")
        or style_config.get("id")
        or style_config.get("style_id")
        or style_config.get("style", "")
    )

    plan_items = slide_blueprint or outline

    if not plan_items:
        return {
            "slides_data": [],
            "current_status": "writer_error",
            "current_agent": "writer",
            "error": "没有页级策划可以撰写",
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "撰稿人：缺少页级策划内容", "agent": "writer"}
            ]
        }

    # 准备提示语
    outline_text = format_outline_for_prompt(outline)
    blueprint_text = format_blueprint_for_prompt(slide_blueprint)
    research_context = format_docs_for_context(source_docs)
    style_context = build_style_context(style_id, style_config, user_intent)

    user_message = WRITER_USER_TEMPLATE.format(
        user_intent=user_intent,
        skill_context=skill_context,
        style_context=style_context,
        outline_text=outline_text,
        blueprint_text=blueprint_text,
        research_context=research_context,
    )

    messages = [
        create_system_message(WRITER_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    response = await llm.ainvoke(messages)

    # 解析响应（剥离推理标签）
    raw_content = strip_thinking_tags(response.content)
    slides_data = _parse_slides_response(raw_content, slide_blueprint or outline)

    # 验证内容
    is_valid, msg = validate_slides_content(slides_data, outline=slide_blueprint or outline)
    if not is_valid:
        repaired = await _repair_slides(
            llm=llm,
            base_messages=messages,
            invalid_reason=msg,
            outline=slide_blueprint or outline,
        )
        if repaired:
            slides_data = repaired
            is_valid, msg = validate_slides_content(slides_data, outline=slide_blueprint or outline)

    if not is_valid:
        if slide_blueprint:
            slides_data = create_default_slides_from_blueprint(slide_blueprint)
        else:
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
        json_str = extract_json_payload(content)
        result = json.loads(json_str)
        if isinstance(result, dict):
            return result.get("slides", [])
        return result

    except (json.JSONDecodeError, IndexError):
        return create_default_slides_from_outline(outline)


async def _repair_slides(
    llm,
    base_messages: list,
    invalid_reason: str,
    outline: list,
) -> list:
    repair_message = HumanMessage(
        content=(
            "你上一次输出的幻灯片内容无效，原因如下：\n"
            f"{invalid_reason}\n\n"
            "请重新输出合法 JSON 数组，要求：\n"
            "1. 页数必须与大纲完全一致\n"
            "2. 需要 image_prompt 的页面必须提供 image_prompt\n"
            "3. path_b 的 image_prompt 只能描述情绪和场景，禁止布局词\n"
            "4. 每页最多 4 条短要点\n"
            "5. 只返回 JSON，不要 markdown 代码块"
        )
    )
    response = await llm.ainvoke([*base_messages, repair_message])
    return _parse_slides_response(strip_thinking_tags(response.content), outline)
