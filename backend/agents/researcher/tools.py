"""
研究 Agent (Researcher) 工具函数
包含真实联网搜索（DuckDuckGo）和本地知识库检索（huashu-slides/references/）
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


async def web_search(query: str) -> List[Dict[str, Any]]:
    """
    真实联网搜索（DuckDuckGo，无需 API key）。
    失败时返回空列表，绝不返回虚假数据。
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.warning(
            "duckduckgo-search package not installed. "
            "Run: pip install duckduckgo-search"
        )
        return []

    try:
        # Run synchronous DuckDuckGo search in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _ddg_search, query)
        return results
    except Exception as e:
        logger.warning(f"web_search failed for query '{query[:50]}': {e}")
        return []


def _ddg_search(query: str) -> List[Dict[str, Any]]:
    """Synchronous DuckDuckGo search (run in executor)."""
    from duckduckgo_search import DDGS

    with DDGS() as ddgs:
        raw_results = list(ddgs.text(query, max_results=5))

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", "")[:300],
            "domain": _extract_domain(r.get("href", "")),
            "relevance_score": None,  # DuckDuckGo does not provide scores
        }
        for r in raw_results
    ]


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or ""
    except Exception:
        return ""


async def rag_search(query: str, documents: List[Dict] = None) -> List[Dict[str, Any]]:
    """
    本地知识库检索：
    1. 搜索 huashu-slides/references/ 参考文件
    2. 搜索用户上传的文档

    使用简单关键词匹配（无需向量数据库）。
    """
    results = []

    # 1. Search huashu-slides reference knowledge base
    reference_results = await _search_huashu_references(query)
    results.extend(reference_results)

    # 2. Search user-uploaded documents
    if documents:
        doc_results = _search_uploaded_documents(query, documents)
        results.extend(doc_results)

    # Sort by relevance, return top 5
    results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return results[:5]


async def _search_huashu_references(query: str) -> List[Dict[str, Any]]:
    """Search huashu-slides/references/ directory for relevant content."""
    # Find the references directory relative to this file's location
    current_dir = Path(__file__).resolve().parent
    # Walk up to find huashu-slides/references/
    project_root = current_dir
    for _ in range(6):
        candidate = project_root / "huashu-slides" / "references"
        if candidate.exists():
            break
        project_root = project_root.parent
    else:
        logger.debug("huashu-slides/references/ not found, skipping knowledge base search")
        return []

    reference_files = [
        ("design-principles.md", "设计原则"),
        ("proven-styles-gallery.md", "风格画廊"),
        ("prompt-templates.md", "提示词模板"),
        ("design-movements.md", "设计运动参考"),
        ("proven-styles-snoopy.md", "Snoopy风格指南"),
    ]

    results = []
    query_lower = query.lower()
    query_tokens = set(query_lower.split())

    for filename, description in reference_files:
        filepath = candidate / filename
        if not filepath.exists():
            continue

        try:
            content = filepath.read_text(encoding="utf-8")
            chunks = _split_into_chunks(content, chunk_size=500)

            for i, chunk in enumerate(chunks):
                score = _compute_relevance(chunk, query_tokens)
                if score > 0:
                    results.append({
                        "chunk_id": f"huashu_{filename}_{i}",
                        "content": chunk,
                        "source": f"huashu-slides/references/{filename}",
                        "relevance_score": score,
                        "metadata": {
                            "file": filename,
                            "description": description,
                            "chunk_index": i,
                        }
                    })
        except OSError as e:
            logger.debug(f"Could not read {filename}: {e}")

    return results


def _search_uploaded_documents(query: str, documents: List[Dict]) -> List[Dict[str, Any]]:
    """Search user-uploaded documents for relevant content."""
    query_tokens = set(query.lower().split())
    results = []

    for doc in documents:
        content = doc.get("content", "")
        if not content:
            continue

        chunks = _split_into_chunks(content, chunk_size=500)
        for i, chunk in enumerate(chunks):
            score = _compute_relevance(chunk, query_tokens)
            if score > 0:
                results.append({
                    "chunk_id": f"doc_{i}",
                    "content": chunk,
                    "source": doc.get("filename", "uploaded_document"),
                    "relevance_score": score,
                    "metadata": {"chunk_index": i},
                })

    return results


def _split_into_chunks(text: str, chunk_size: int = 500) -> List[str]:
    """Split text into overlapping chunks for search."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current_len + len(para) > chunk_size and current:
            chunks.append("\n\n".join(current))
            current = [current[-1]] if current else []  # Overlap: keep last paragraph
            current_len = len(current[0]) if current else 0
        current.append(para)
        current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _compute_relevance(chunk: str, query_tokens: set) -> float:
    """
    Simple keyword-based relevance scoring.
    Returns a score between 0 and 1.
    """
    if not query_tokens:
        return 0.0

    chunk_lower = chunk.lower()
    matched = sum(1 for token in query_tokens if token in chunk_lower)
    score = matched / len(query_tokens)

    # Boost if query appears as a phrase
    query_phrase = " ".join(query_tokens)
    if query_phrase in chunk_lower:
        score = min(1.0, score + 0.3)

    return score


async def summarize_sources(sources: List[Dict]) -> str:
    """汇总搜索结果为可读文本"""
    if not sources:
        return "未找到相关资料"

    summaries = []
    for i, source in enumerate(sources[:5], 1):
        title = source.get("title", "未知标题")
        snippet = source.get("snippet", source.get("content", ""))[:150]
        src = source.get("url", source.get("source", ""))
        summaries.append(f"{i}. {title}\n   来源: {src}\n   摘要: {snippet}...")

    return "\n\n".join(summaries)


def merge_and_dedupe_results(
    web_results: List[Dict],
    rag_results: List[Dict]
) -> tuple[List[Dict], List[Dict]]:
    """合并并去重搜索结果（基于标题/内容前50字去重）"""
    seen = set()
    unique_web = []

    for result in web_results:
        key = result.get("title", "") or result.get("content", "")[:50]
        if key and key not in seen:
            seen.add(key)
            unique_web.append(result)

    return unique_web, rag_results
