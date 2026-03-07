"""
研究 Agent (Researcher) - 主逻辑
负责 RAG 检索和联网搜索素材
"""

import asyncio
from typing import Any

from agents.researcher.tools import web_search, rag_search, merge_and_dedupe_results
from runtime_schemas import build_research_packet, serialize_models


async def run(state: dict) -> dict[str, Any]:
    """
    研究 Agent 入口函数
    执行 RAG 检索和联网搜索
    """
    user_intent = state.get("user_intent", "")
    existing_docs = state.get("source_docs", [])
    
    # 并行执行搜索任务
    web_task = web_search(user_intent)
    rag_task = rag_search(user_intent, existing_docs)
    
    search_results, rag_results = await asyncio.gather(web_task, rag_task)
    
    # 合并并去重结果
    search_results, rag_results = merge_and_dedupe_results(search_results, rag_results)
    
    # 合并所有文档
    all_docs = existing_docs + rag_results
    research_packet = build_research_packet(user_intent, all_docs, search_results)
    
    return {
        "source_docs": serialize_models(research_packet.source_docs),
        "search_results": serialize_models(research_packet.search_results),
        "research_packet": serialize_models(research_packet),
        "current_status": "research_complete",
        "current_agent": "researcher",
        "messages": state.get("messages", []) + [
            {
                "role": "assistant", 
                "content": f"研究员已完成搜索: 找到 {len(search_results)} 条网络资源, {len(rag_results)} 条文档片段", 
                "agent": "researcher"
            }
        ]
    }
