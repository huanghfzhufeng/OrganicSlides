"""
策划 Agent (Planner) - 主逻辑
负责分析用户意图，生成结构化大纲
"""

import json
import uuid
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from agents.planner.prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_TEMPLATE
from agents.planner.tools import build_context, validate_outline
from agents.base import get_llm, create_system_message


async def run(state: dict) -> dict[str, Any]:
    """
    策划 Agent 入口函数
    分析用户意图，生成结构化大纲
    """
    llm = get_llm(model="gpt-4o", temperature=0.7)
    
    user_intent = state.get("user_intent", "")
    source_docs = state.get("source_docs", [])
    search_results = state.get("search_results", [])
    
    # 构建上下文
    context = build_context(source_docs, search_results)
    
    # 构建用户消息
    user_message = PLANNER_USER_TEMPLATE.format(
        user_intent=user_intent,
        context=context
    )

    messages = [
        create_system_message(PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]
    
    response = await llm.ainvoke(messages)
    
    # 解析 LLM 响应
    outline = _parse_outline_response(response.content)
    
    # 验证大纲
    is_valid, msg = validate_outline(outline)
    if not is_valid:
        # 如果验证失败，使用默认大纲
        outline = _create_default_outline()
    
    return {
        "outline": outline,
        "current_status": "outline_generated",
        "current_agent": "planner",
        "messages": state.get("messages", []) + [
            {"role": "assistant", "content": f"策划师已生成 {len(outline)} 页大纲", "agent": "planner"}
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
    """创建默认大纲"""
    return [
        {"id": "cover", "title": "封面", "type": "cover", "key_points": [], "notes": ""},
        {"id": "intro", "title": "介绍", "type": "content", "key_points": ["背景", "目标"], "notes": ""},
        {"id": "main", "title": "主要内容", "type": "content", "key_points": ["核心观点"], "notes": ""},
        {"id": "conclusion", "title": "总结", "type": "conclusion", "key_points": ["回顾", "行动号召"], "notes": ""}
    ]
