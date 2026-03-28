"""Slide blueprint agent."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage

from agents.base import create_system_message, extract_json_payload, get_llm, strip_thinking_tags
from agents.blueprint.prompts import BLUEPRINT_SYSTEM_PROMPT, BLUEPRINT_USER_TEMPLATE
from agents.blueprint.tools import (
    create_default_blueprint_from_outline,
    format_docs_for_context,
    format_outline_for_prompt,
    normalize_slide_blueprint,
    validate_slide_blueprint,
)
from skills.runtime import build_skill_prompt_packet


async def run(state: dict) -> dict[str, Any]:
    llm = get_llm(temperature=0.4)

    outline = state.get("outline", [])
    source_docs = state.get("source_docs", [])
    user_intent = state.get("user_intent", "")
    skill_context = build_skill_prompt_packet(state.get("skill_packet"))

    if not outline:
        return {
            "slide_blueprint": [],
            "current_status": "blueprint_error",
            "current_agent": "blueprint_planner",
            "error": "没有可扩展的大纲",
            "messages": state.get("messages", []) + [
                {
                    "role": "assistant",
                    "content": "页级策划器：缺少大纲，无法展开逐页蓝图",
                    "agent": "blueprint_planner",
                }
            ],
        }

    outline_text = format_outline_for_prompt(outline)
    research_context = format_docs_for_context(source_docs)

    user_message = BLUEPRINT_USER_TEMPLATE.format(
        user_intent=user_intent,
        skill_context=skill_context,
        outline_text=outline_text,
        research_context=research_context,
    )

    messages = [
        create_system_message(BLUEPRINT_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = await llm.ainvoke(messages)
    raw_content = strip_thinking_tags(response.content)
    slide_blueprint = _parse_blueprint_response(raw_content, outline)
    slide_blueprint = normalize_slide_blueprint(slide_blueprint)

    is_valid, message = validate_slide_blueprint(slide_blueprint, outline)
    if not is_valid:
        repaired = await _repair_blueprint(
            llm=llm,
            base_messages=messages,
            invalid_reason=message,
            outline=outline,
        )
        if repaired:
            slide_blueprint = normalize_slide_blueprint(repaired)
            is_valid, message = validate_slide_blueprint(slide_blueprint, outline)

    if not is_valid:
        slide_blueprint = create_default_blueprint_from_outline(outline)

    return {
        "slide_blueprint": slide_blueprint,
        "slide_blueprint_approved": False,
        "current_status": "blueprint_generated",
        "current_agent": "blueprint_planner",
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": f"页级策划器已将大纲展开为 {len(slide_blueprint)} 页蓝图",
                "agent": "blueprint_planner",
            }
        ],
    }


def _parse_blueprint_response(content: str, outline: list[dict]) -> list[dict]:
    try:
        json_str = extract_json_payload(content)
        result = json.loads(json_str)
        if isinstance(result, dict):
            result = result.get("slide_blueprint", [])
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, IndexError, TypeError):
        pass

    return create_default_blueprint_from_outline(outline)


async def _repair_blueprint(
    llm,
    base_messages: list,
    invalid_reason: str,
    outline: list[dict],
) -> list[dict]:
    repair_message = HumanMessage(
        content=(
            "你上一次输出的 Slide Blueprint 无效，原因如下：\n"
            f"{invalid_reason}\n\n"
            "请重新输出合法 JSON 数组，要求：\n"
            "1. 每一项就是 1 页，不是章节\n"
            "2. 页数至少不小于 outline 章节数\n"
            "3. 每页必须有 title、goal、content_brief\n"
            "4. 每页 key_points 最多 4 条\n"
            "5. 只返回 JSON，不要 markdown 代码块"
        )
    )
    response = await llm.ainvoke([*base_messages, repair_message])
    return _parse_blueprint_response(strip_thinking_tags(response.content), outline)
