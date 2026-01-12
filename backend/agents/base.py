"""
Agent 基础类和工具函数
"""

from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from config import settings


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
