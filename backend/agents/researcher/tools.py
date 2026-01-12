"""
研究 Agent (Researcher) 工具函数
包含 RAG 检索和联网搜索工具
"""

import asyncio
from typing import List, Dict, Any


async def web_search(query: str) -> List[Dict[str, Any]]:
    """
    联网搜索
    TODO: 集成真实的搜索 API (如 Tavily, SerpAPI, Bing)
    """
    await asyncio.sleep(1)  # 模拟网络延迟
    
    return [
        {
            "title": f"关于 {query[:20]} 的最新研究报告",
            "url": "https://example.com/report1",
            "snippet": f"这是一份关于 {query[:30]} 的综合分析报告，包含最新的数据和趋势...",
            "domain": "example.com",
            "relevance_score": 0.95
        },
        {
            "title": f"{query[:15]} 行业白皮书 2024",
            "url": "https://example.com/whitepaper",
            "snippet": "本白皮书深入探讨了行业发展现状、挑战与机遇...",
            "domain": "industry.org",
            "relevance_score": 0.88
        },
        {
            "title": f"专家解读: {query[:20]} 的未来趋势",
            "url": "https://example.com/analysis",
            "snippet": "知名专家对该领域未来发展方向的深度分析...",
            "domain": "expert.com",
            "relevance_score": 0.82
        }
    ]


async def rag_search(query: str, documents: List[Dict] = None) -> List[Dict[str, Any]]:
    """
    RAG 检索 - 从向量数据库中检索相关文档块
    TODO: 集成 LlamaIndex 或其他 RAG 框架
    """
    await asyncio.sleep(0.5)  # 模拟检索延迟
    
    if not documents:
        return []
    
    # 模拟检索结果
    return [
        {
            "chunk_id": f"chunk_{i}",
            "content": f"从上传文档中检索到的相关内容片段 {i+1}...",
            "source": "uploaded_document.pdf",
            "relevance_score": 0.95 - i * 0.1,
            "metadata": {"page": i + 1}
        }
        for i in range(min(3, len(documents)))
    ]


async def summarize_sources(sources: List[Dict]) -> str:
    """汇总搜索结果"""
    if not sources:
        return "未找到相关资料"
    
    summaries = []
    for i, source in enumerate(sources[:5], 1):
        title = source.get("title", "未知标题")
        snippet = source.get("snippet", "")[:100]
        summaries.append(f"{i}. {title}: {snippet}...")
    
    return "\n".join(summaries)


def merge_and_dedupe_results(
    web_results: List[Dict], 
    rag_results: List[Dict]
) -> tuple[List[Dict], List[Dict]]:
    """合并并去重搜索结果"""
    # 简单去重：基于标题
    seen_titles = set()
    unique_web = []
    
    for result in web_results:
        title = result.get("title", "")
        if title not in seen_titles:
            seen_titles.add(title)
            unique_web.append(result)
    
    return unique_web, rag_results
