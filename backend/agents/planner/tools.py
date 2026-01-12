"""
策划 Agent (Planner) 工具函数
"""

from typing import List, Dict, Any


def format_docs_for_context(source_docs: List[Dict], max_docs: int = 3) -> str:
    """将检索到的文档格式化为上下文"""
    if not source_docs:
        return ""
    
    docs_text = "\n".join([
        f"[文档 {i+1}]: {doc.get('content', '')[:500]}..." 
        for i, doc in enumerate(source_docs[:max_docs])
    ])
    return f"<参考文档>\n{docs_text}\n</参考文档>"


def format_search_for_context(search_results: List[Dict], max_results: int = 5) -> str:
    """将搜索结果格式化为上下文"""
    if not search_results:
        return ""
    
    search_text = "\n".join([
        f"[搜索 {i+1}]: {result.get('title', '')} - {result.get('snippet', '')[:200]}" 
        for i, result in enumerate(search_results[:max_results])
    ])
    return f"<搜索结果>\n{search_text}\n</搜索结果>"


def build_context(source_docs: List[Dict], search_results: List[Dict]) -> str:
    """构建完整的上下文"""
    parts = []
    
    docs_context = format_docs_for_context(source_docs)
    if docs_context:
        parts.append(docs_context)
    
    search_context = format_search_for_context(search_results)
    if search_context:
        parts.append(search_context)
    
    return "\n\n".join(parts)


def validate_outline(outline: List[Dict]) -> tuple[bool, str]:
    """验证大纲结构是否合法"""
    if not outline:
        return False, "大纲不能为空"
    
    if len(outline) < 2:
        return False, "大纲至少需要 2 个章节"
    
    if len(outline) > 20:
        return False, "大纲不能超过 20 个章节"
    
    required_types = {"cover", "conclusion"}
    found_types = {s.get("type") for s in outline}
    
    # 检查是否有封面
    has_cover = outline[0].get("type") == "cover" or "cover" in found_types
    if not has_cover:
        return False, "大纲应包含封面页"
    
    return True, "验证通过"
