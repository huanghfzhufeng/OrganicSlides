"""
Agent 基础类和工具函数
"""

import re
from typing import Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from config import settings

# MiniMax-M2.5 包裹推理内容的标签正则
_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def get_llm(model: str = "gpt-4o", temperature: float = 0.7) -> ChatOpenAI:
    """获取 LLM 实例"""
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY
    )


def create_system_message(content: str) -> SystemMessage:
    """创建系统消息"""
    return SystemMessage(content=content)


def create_human_message(content: str) -> HumanMessage:
    """创建用户消息"""
    return HumanMessage(content=content)


def strip_thinking_tags(content: Any) -> str:
    """去除 MiniMax-M2.5 等推理模型在回复中包含的 <think>...</think> 标签。"""
    return _THINK_RE.sub("", _coerce_text_content(content)).strip()


def extract_json_payload(content: Any) -> str:
    """Extract the most likely JSON object/array from an LLM response."""
    text = strip_thinking_tags(_coerce_text_content(content))
    if not text:
        return ""

    candidates = [match.strip() for match in _CODE_FENCE_RE.findall(text) if match.strip()]
    candidates.append(text.strip())

    for candidate in candidates:
        extracted = _extract_balanced_json(candidate)
        if extracted:
            return extracted

    return text.strip()


def _coerce_text_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text", "")
                if text and not _THINK_RE.fullmatch(text.strip()):
                    cleaned = _THINK_RE.sub("", text).strip()
                    if cleaned:
                        parts.append(cleaned)
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content)


def _extract_balanced_json(text: str) -> str:
    starts = [idx for idx in (text.find("{"), text.find("[")) if idx != -1]
    if not starts:
        return ""
    start = min(starts)
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
        if not in_string:
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start: i + 1]
    return ""


def format_outline_for_prompt(outline: list) -> str:
    """将大纲格式化为提示语"""
    if not outline:
        return "暂无大纲"
    
    lines = []
    for i, section in enumerate(outline, 1):
        title = section.get("title", "未命名章节")
        slide_type = section.get("type", "content")
        lines.append(f"{i}. [{slide_type}] {title}")
    
    return "\n".join(lines)


def format_slides_for_prompt(slides: list) -> str:
    """将幻灯片数据格式化为提示语"""
    if not slides:
        return "暂无幻灯片内容"
    
    lines = []
    for slide in slides:
        page = slide.get("page_number", "?")
        title = slide.get("title", "未命名")
        layout = slide.get("layout_intent", "default")
        lines.append(f"Page {page}: [{layout}] {title}")
    
    return "\n".join(lines)
