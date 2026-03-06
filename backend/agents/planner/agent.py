"""
策划 Agent (Planner) - 主逻辑
负责分析用户意图，生成结构化大纲
核心原则：标题是断言句（Assertion-Evidence Framework）
"""

import json
import uuid
from typing import Any

from langchain_core.messages import HumanMessage

from agents.planner.prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_TEMPLATE
from agents.planner.tools import build_context, build_style_context, validate_outline, normalize_outline
from agents.base import get_llm, create_system_message


async def run(state: dict) -> dict[str, Any]:
    """
    策划 Agent 入口函数
    分析用户意图，生成结构化大纲（含 visual_type 和 path_hint）
    """
    llm = get_llm(model="gpt-4o", temperature=0.7)

    user_intent = state.get("user_intent", "")
    source_docs = state.get("source_docs", [])
    search_results = state.get("search_results", [])
    style_id = state.get("style_id", "")
    style_config = state.get("style_config", {})

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

    # 解析 LLM 响应
    outline = _parse_outline_response(response.content)

    # 规范化（补全缺失字段，强制 max 4 key_points）
    outline = normalize_outline(outline)

    # 验证大纲
    is_valid, msg = validate_outline(outline)
    if not is_valid:
        outline = _create_default_outline()

    return {
        "outline": outline,
        "current_status": "outline_generated",
        "current_agent": "planner",
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": f"策划师已生成 {len(outline)} 页大纲",
                "agent": "planner"
            }
        ]
    }


def _parse_outline_response(content: str) -> list:
    """解析 LLM 响应中的大纲"""
    try:
        # 处理 markdown 代码块
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        result = json.loads(json_str)
        outline = result.get("outline", [])

        # 为每个章节添加 ID（如果没有）
        for i, section in enumerate(outline):
            if "id" not in section:
                section["id"] = f"section_{uuid.uuid4().hex[:8]}"

        return outline

    except (json.JSONDecodeError, IndexError, KeyError):
        return _create_default_outline()


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
