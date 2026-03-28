"""
研究 Agent (Researcher) - 主逻辑
负责 RAG 检索和联网搜索素材
"""

import asyncio
from typing import Any

from agents.researcher.tools import (
    web_search,
    rag_search,
    merge_and_dedupe_results,
    should_run_web_search,
)

_RESEARCH_WEB_BUDGET_SECONDS = 6.0


async def run_local(state: dict) -> dict[str, Any]:
    """
    先做本地检索，快速给前端一个可见进度。

    这样用户至少能马上看到“本地资料命中了什么”，而不是一直卡在一个
    researcher 节点上等待联网请求返回。
    """
    user_intent = state.get("user_intent", "")
    existing_docs = state.get("source_docs", [])
    is_thesis_mode = state.get("is_thesis_mode", False)

    rag_results = await rag_search(user_intent, existing_docs)
    all_docs = existing_docs + rag_results
    needs_web_search = should_run_web_search(
        user_intent,
        existing_docs,
        rag_results,
        is_thesis_mode=is_thesis_mode,
    )

    next_message = (
        f"本地检索完成：命中 {len(rag_results)} 条资料片段，准备联网补充案例与数据"
        if needs_web_search
        else f"本地检索完成：命中 {len(rag_results)} 条资料片段，跳过联网搜索"
    )

    return {
        "source_docs": all_docs,
        "search_results": state.get("search_results", []),
        "needs_web_search": needs_web_search,
        "current_status": "research_local_complete",
        "current_agent": "researcher_local",
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": next_message,
                "agent": "researcher_local",
            }
        ],
    }


async def run_web(state: dict) -> dict[str, Any]:
    """
    在严格时间预算内补充联网结果。
    超时直接返回空结果，不再让整条链路像卡死一样挂着。
    """
    if not state.get("needs_web_search", False):
        return {
            "current_status": "research_complete",
            "current_agent": "researcher_web",
            "messages": state.get("messages", []) + [
                {
                    "role": "assistant",
                    "content": "联网搜索已跳过，直接进入大纲生成",
                    "agent": "researcher_web",
                }
            ],
        }

    user_intent = state.get("user_intent", "")

    try:
        search_results = await asyncio.wait_for(
            web_search(user_intent),
            timeout=_RESEARCH_WEB_BUDGET_SECONDS,
        )
    except asyncio.TimeoutError:
        search_results = []

    merged_search_results, _ = merge_and_dedupe_results(search_results, [])

    return {
        "search_results": merged_search_results,
        "current_status": "research_complete",
        "current_agent": "researcher_web",
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": f"联网补充完成：找到 {len(merged_search_results)} 条网络资源",
                "agent": "researcher_web",
            }
        ],
    }


async def run(state: dict) -> dict[str, Any]:
    """
    研究 Agent 入口函数
    执行 RAG 检索和联网搜索
    """
    local_result = await run_local(state)
    merged_state = {**state, **local_result}
    if not local_result.get("needs_web_search"):
        return {
            **local_result,
            "current_status": "research_complete",
        }

    web_result = await run_web(merged_state)
    return {
        **local_result,
        **web_result,
    }
