"""
研究 Agent (Researcher) 工具函数
包含真实联网搜索（DuckDuckGo + News API）和本地知识库检索（huashu-slides/references/）
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse
import re

from skills.runtime import get_skill_runtime_packet

logger = logging.getLogger(__name__)

_WEB_SEARCH_TRIGGER_TOKENS = (
    "最新",
    "当前",
    "recent",
    "latest",
    "today",
    "2024",
    "2025",
    "2026",
    "市场",
    "增长率",
    "市场规模",
    "趋势",
    "案例",
    "融资",
    "数据",
    "统计",
)
_DDG_TIMEOUT_SECONDS = 4.0
_NEWS_TIMEOUT_SECONDS = 4.0


async def web_search(query: str) -> List[Dict[str, Any]]:
    """
    联网搜索：DuckDuckGo + News API 并行。
    失败时返回空列表，绝不返回虚假数据。
    """
    ddg_task = _run_with_timeout(_ddg_search_async(query), _DDG_TIMEOUT_SECONDS, "DuckDuckGo")
    news_task = _run_with_timeout(_news_search_async(query), _NEWS_TIMEOUT_SECONDS, "News API")

    ddg_results, news_results = await asyncio.gather(
        ddg_task, news_task, return_exceptions=True
    )

    results: List[Dict[str, Any]] = []
    if isinstance(ddg_results, list):
        results.extend(ddg_results)
    else:
        logger.warning("DuckDuckGo search failed: %s", ddg_results)

    if isinstance(news_results, list):
        results.extend(news_results)
    else:
        logger.warning("News API search failed: %s", news_results)

    return results


async def _run_with_timeout(coro, timeout_seconds: float, label: str) -> List[Dict[str, Any]]:
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.info("%s search timed out after %.1fs", label, timeout_seconds)
        return []
    except Exception as exc:
        logger.warning("%s search failed: %s", label, exc)
        return []


async def _ddg_search_async(query: str) -> List[Dict[str, Any]]:
    """DuckDuckGo search wrapped for async."""
    try:
        from ddgs import DDGS
    except ImportError:
        logger.warning("ddgs not installed, skipping")
        return []

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ddg_search_sync, query)


def _ddg_search_sync(query: str) -> List[Dict[str, Any]]:
    """Synchronous DuckDuckGo search (run in executor)."""
    from ddgs import DDGS

    with DDGS() as ddgs:
        raw_results = list(ddgs.text(query, max_results=5))

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", "")[:300],
            "domain": _extract_domain(r.get("href", "")),
            "source": "duckduckgo",
            "relevance_score": None,
        }
        for r in raw_results
    ]


async def _news_search_async(query: str) -> List[Dict[str, Any]]:
    """Search recent news articles via News API."""
    api_key = os.environ.get("NEWS_API_KEY", "")
    if not api_key:
        return []

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _news_search_sync, query, api_key)


def _news_search_sync(query: str, api_key: str) -> List[Dict[str, Any]]:
    """Synchronous News API search (run in executor)."""
    import httpx

    try:
        resp = httpx.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "pageSize": 5,
                "sortBy": "relevancy",
                "language": "zh",
                "apiKey": api_key,
            },
            timeout=_NEWS_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("News API request failed: %s", exc)
        return []

    articles = data.get("articles", [])
    return [
        {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "snippet": (a.get("description") or "")[:300],
            "domain": _extract_domain(a.get("url", "")),
            "source": "newsapi",
            "relevance_score": None,
        }
        for a in articles
    ]


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
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
    skill_packet = get_skill_runtime_packet()
    candidate = Path(skill_packet.get("references_dir", ""))
    if not candidate.exists():
        logger.debug("huashu-slides/references/ not found, skipping knowledge base search")
        return []

    reference_files = [
        (filename, _reference_description(filename))
        for filename in skill_packet.get("reference_files", [])
    ]

    results = []
    query_tokens = _tokenize_query(query)

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


def _reference_description(filename: str) -> str:
    descriptions = {
        "design-principles.md": "设计原则",
        "proven-styles-gallery.md": "风格画廊",
        "prompt-templates.md": "提示词模板",
        "design-movements.md": "设计运动参考",
        "proven-styles-snoopy.md": "Snoopy风格指南",
    }
    return descriptions.get(filename, filename)


def _search_uploaded_documents(query: str, documents: List[Dict]) -> List[Dict[str, Any]]:
    """Search user-uploaded documents for relevant content."""
    query_tokens = _tokenize_query(query)
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


def _compute_relevance(chunk: str, query_tokens: set[str]) -> float:
    """
    Simple keyword-based relevance scoring.
    Returns a score between 0 and 1.
    """
    if not query_tokens:
        return 0.0

    chunk_lower = chunk.lower()
    weighted_total = 0.0
    matched = 0.0

    for token in query_tokens:
        weight = 1.6 if len(token) >= 5 else 1.0
        weighted_total += weight
        if token in chunk_lower:
            matched += weight

    score = matched / weighted_total if weighted_total else 0.0

    phrase_candidates = sorted(query_tokens, key=len, reverse=True)[:3]
    for phrase in phrase_candidates:
        if len(phrase) >= 4 and phrase in chunk_lower:
            score = min(1.0, score + 0.18)

    return score


def _tokenize_query(query: str) -> set[str]:
    """
    Tokenize mixed Chinese/English queries for lightweight local retrieval.

    The previous implementation only split on spaces, which makes Chinese
    queries nearly unsearchable. Here we keep whole phrases plus short CJK
    n-grams so huashu references can actually be matched by中文主题.
    """
    lowered = query.lower().strip()
    if not lowered:
        return set()

    tokens = set(re.findall(r"[a-z0-9][a-z0-9\-+_.]{1,}", lowered))
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)

    for chunk in chinese_chunks:
        tokens.add(chunk)
        if len(chunk) < 4:
            continue
        ngram_sizes = [2, 3]
        if len(chunk) >= 8:
            ngram_sizes.append(4)
        for size in ngram_sizes:
            for idx in range(0, len(chunk) - size + 1):
                tokens.add(chunk[idx: idx + size])

    return {token for token in tokens if len(token) >= 2}


def should_run_web_search(
    query: str,
    documents: List[Dict] | None = None,
    local_results: List[Dict[str, Any]] | None = None,
    *,
    is_thesis_mode: bool = False,
) -> bool:
    """
    Decide whether a slow web search is worth doing.

    Principles:
    - Thesis / uploaded-document flows should prefer the user's own material.
    - If local retrieval already found enough usable context, skip the network.
    - Only force web search when the prompt clearly asks for current data/cases.
    """
    lowered = (query or "").lower()
    has_time_sensitive_need = any(token in lowered for token in _WEB_SEARCH_TRIGGER_TOKENS)
    document_count = len(documents or [])
    local_hit_count = len(local_results or [])

    if has_time_sensitive_need:
        return True

    if is_thesis_mode:
        return False

    if document_count >= 3:
        return False

    if local_hit_count >= 3:
        return False

    return True


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
