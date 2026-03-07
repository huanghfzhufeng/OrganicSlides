"""
策划 Agent (Planner) - 主逻辑
负责分析用户意图，生成结构化大纲
核心原则：标题是断言句（Assertion-Evidence Framework）
"""

import json
import uuid
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from agents.planner.prompts import (
    PLANNER_REPAIR_SYSTEM_PROMPT,
    PLANNER_REPAIR_USER_TEMPLATE,
    PLANNER_SYSTEM_PROMPT,
    PLANNER_USER_TEMPLATE,
)
from agents.planner.tools import build_context, build_style_context, validate_outline, normalize_outline
from agents.base import get_llm, create_system_message
from agents.structured_output import extract_json_payload, resolve_structured_output
from runtime_schemas import build_research_packet, build_style_packet, serialize_models, validation_error_message


async def run(state: dict) -> dict[str, Any]:
    """
    策划 Agent 入口函数
    分析用户意图，生成结构化大纲（含 visual_type 和 path_hint）
    """
    llm = get_llm(model="gpt-4o", temperature=0.7)

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
        message = f"运行时 schema 校验失败: {validation_error_message(exc)}"
        return {
            "outline": [],
            "current_status": "planner_error",
            "current_agent": "planner",
            "error": message,
            "messages": state.get("messages", []) + [
                {
                    "role": "assistant",
                    "content": f"策划师输入校验失败：{message}",
                    "agent": "planner",
                }
            ],
        }

    source_docs = serialize_models(research_packet.source_docs)
    search_results = serialize_models(research_packet.search_results)
    style_id = style_packet.style_id
    style_config = serialize_models(style_packet)

    # 构建上下文
    research_context = build_context(source_docs, search_results)
    style_context = build_style_context(style_id, style_config)

    # 构建用户消息
    user_message = PLANNER_USER_TEMPLATE.format(
        user_intent=user_intent,
        style_context=style_context,
        research_context=research_context,
    )

    messages = [
        create_system_message(PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    response = await llm.ainvoke(messages)

    result = await resolve_structured_output(
        llm=llm,
        raw_content=response.content,
        parser=_parse_outline_response,
        validator=_validate_outline_response,
        repair_system_prompt=PLANNER_REPAIR_SYSTEM_PROMPT,
        repair_user_template=PLANNER_REPAIR_USER_TEMPLATE,
        repair_context={
            "user_intent": user_intent,
        },
    )

    if not result.success:
        return {
            "outline": [],
            "current_status": "planner_error",
            "current_agent": "planner",
            "error": f"策划输出无法修复: {result.error}",
            "planner_diagnostics": {
                "repair_attempted": len(result.attempts) > 1,
                "attempts": result.attempts,
            },
            "messages": state.get("messages", []) + [
                {
                    "role": "assistant",
                    "content": f"策划师输出修复失败：{result.error}",
                    "agent": "planner",
                }
            ],
        }

    outline = result.value

    return {
        "outline": outline,
        "research_packet": serialize_models(research_packet),
        "style_packet": style_config,
        "source_docs": source_docs,
        "search_results": search_results,
        "style_id": style_id,
        "style_config": style_config,
        "current_status": "outline_generated",
        "current_agent": "planner",
        "planner_diagnostics": {
            "repair_attempted": len(result.attempts) > 1,
            "attempts": result.attempts,
        },
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": _build_success_message(outline, result.repaired),
                "agent": "planner"
            }
        ]
    }


def _parse_outline_response(content: str) -> list:
    """解析 LLM 响应中的大纲"""
    json_str = extract_json_payload(content)
    result = json.loads(json_str)
    if not isinstance(result, dict):
        raise ValueError("planner output must be a JSON object")

    outline = result.get("outline")
    if not isinstance(outline, list):
        raise ValueError("planner output must include an outline array")

    # 为每个章节添加 ID（如果没有）
    for section in outline:
        if "id" not in section:
            section["id"] = f"section_{uuid.uuid4().hex[:8]}"

    return normalize_outline(outline)


def _validate_outline_response(outline: list) -> tuple[bool, str]:
    if not outline:
        return False, "outline cannot be empty"
    return validate_outline(outline)


def _build_success_message(outline: list, repaired: bool) -> str:
    action = "修复并生成" if repaired else "已生成"
    return f"策划师{action} {len(outline)} 页大纲"


def _create_default_outline() -> list:
    """创建默认大纲（带断言句标题）"""
    return [
        {
            "id": "cover",
            "title": "演示文稿",
            "slide_type": "cover",
            "visual_type": "cover",
            "key_points": [],
            "path_hint": "path_b",
            "notes": ""
        },
        {
            "id": "intro",
            "title": "这个问题影响了所有相关方",
            "slide_type": "content",
            "visual_type": "illustration",
            "key_points": ["背景与现状", "核心挑战"],
            "path_hint": "auto",
            "notes": "介绍背景和问题"
        },
        {
            "id": "main",
            "title": "我们的方案解决了三个核心痛点",
            "slide_type": "content",
            "visual_type": "flow",
            "key_points": ["核心观点一", "核心观点二", "核心观点三"],
            "path_hint": "auto",
            "notes": "展示解决方案"
        },
        {
            "id": "conclusion",
            "title": "立即行动，抓住这个机会",
            "slide_type": "conclusion",
            "visual_type": "quote",
            "key_points": ["核心结论", "下一步行动"],
            "path_hint": "path_b",
            "notes": "总结与行动号召"
        }
    ]
