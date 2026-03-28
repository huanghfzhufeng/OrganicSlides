"""Agent 基础类和工具函数。"""

import re
from typing import Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from config import settings

# MiniMax-M2.5 包裹推理内容的标签正则
_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def get_llm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> ChatOpenAI:
    """
    获取 LLM 实例。

    使用 MiniMax 的 OpenAI 兼容 API。
    model 和 base_url 从 settings 读取，不再硬编码。
    max_tokens 默认 4096，确保推理模型有足够空间输出内容。
    """
    return ChatOpenAI(
        model=model or settings.LLM_MODEL,
        temperature=temperature,
        api_key=settings.MINIMAX_API_KEY,
        base_url=settings.LLM_BASE_URL,
        max_tokens=max_tokens,
    )


def strip_thinking_tags(content: str) -> str:
    """
    去除 MiniMax-M2.5 等推理模型在回复中包含的 <think>...</think> 标签。
    返回清理后的实际回复内容。
    """
    return _THINK_RE.sub("", _coerce_text_content(content)).strip()


def extract_json_payload(content: Any) -> str:
    """
    Extract the most likely JSON object/array from an LLM response.

    Providers often wrap JSON in markdown fences or add explanatory text before
    and after the payload. Pulling out the balanced JSON block here reduces the
    chance that Planner / Writer silently fall back to generic defaults.
    """
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


def _extract_balanced_json(text: str) -> str:
    starts = [idx for idx in (text.find("{"), text.find("[")) if idx != -1]
    if not starts:
        return ""

    start = min(starts)
    stack: list[str] = []
    in_string = False
    escaped = False

    for idx, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char in "{[":
            stack.append(char)
            continue

        if char in "}]":
            if not stack:
                return ""

            opening = stack.pop()
            if (opening, char) not in {("{", "}"), ("[", "]")}:
                return ""

            if not stack:
                return text[start: idx + 1].strip()

    return ""


def _coerce_text_content(content: Any) -> str:
    """
    Normalize provider-specific response payloads into plain text.

    MiniMax currently returns strings, but OpenAI-compatible providers can also
    return structured content blocks. Keeping the coercion here avoids leaking
    <think> tags or block wrappers into downstream JSON parsing.
    """
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue

            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue

                nested_text = item.get("content")
                if isinstance(nested_text, str):
                    parts.append(nested_text)

        return "\n".join(part for part in parts if part).strip()

    return str(content)


def create_system_message(content: str) -> SystemMessage:
    """创建系统消息"""
    return SystemMessage(content=content)


def create_human_message(content: str) -> HumanMessage:
    """创建用户消息"""
    return HumanMessage(content=content)


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
