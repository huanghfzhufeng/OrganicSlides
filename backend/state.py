"""
MAS-PPT 全局状态定义
基于 LangGraph 的多智能体协同演示文稿生成系统
"""

from typing import TypedDict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class SlideType(str, Enum):
    """幻灯片类型"""
    COVER = "cover"
    CONTENT = "content"
    DATA = "data"
    COMPARISON = "comparison"
    QUOTE = "quote"
    CHART = "chart"
    IMAGE = "image"
    CONCLUSION = "conclusion"


@dataclass
class DocumentChunk:
    """RAG 检索到的文档块"""
    chunk_id: str
    content: str
    source: str
    metadata: dict = field(default_factory=dict)


@dataclass
class OutlineSection:
    """大纲章节"""
    id: str
    title: str
    slide_type: str = "content"
    key_points: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class SlideElement:
    """幻灯片元素"""
    type: str  # text_block, image, chart, shape
    placeholder_idx: int
    content: Any
    style: dict = field(default_factory=dict)


@dataclass
class SlideModel:
    """幻灯片数据模型"""
    page_number: int
    layout_intent: str
    title: str
    speaker_notes: str = ""
    elements: List[SlideElement] = field(default_factory=list)


class PresentationState(TypedDict, total=False):
    """
    LangGraph 全局状态
    这是在整个工作流中传递的状态对象
    """
    # 会话信息
    session_id: str
    user_intent: str  # 用户原始输入
    
    # RAG 相关
    source_docs: List[dict]  # 检索到的上下文文档
    search_results: List[dict]  # 联网搜索结果
    
    # 策划阶段产物 (HITL 介入点)
    outline: List[dict]
    outline_approved: bool
    
    # 撰写与视觉阶段的中间产物
    slides_data: List[dict]
    
    # 视觉风格配置
    theme_config: dict
    
    # 资产生成
    generated_assets: List[dict]  # 生成的图片/图表
    
    # 渲染输出
    pptx_path: str  # 最终文件路径
    
    # 流程控制
    current_status: str  # 用于前端进度条
    current_agent: str  # 当前执行的 Agent
    error: Optional[str]
    
    # 消息历史 (用于 LLM 上下文)
    messages: List[dict]


def create_initial_state(session_id: str, user_intent: str, theme: str = "organic") -> PresentationState:
    """创建初始状态"""
    return PresentationState(
        session_id=session_id,
        user_intent=user_intent,
        source_docs=[],
        search_results=[],
        outline=[],
        outline_approved=False,
        slides_data=[],
        theme_config={
            "style": theme,
            "colors": get_theme_colors(theme),
        },
        generated_assets=[],
        pptx_path="",
        current_status="initialized",
        current_agent="",
        error=None,
        messages=[]
    )


def get_theme_colors(theme: str) -> dict:
    """获取主题颜色配置"""
    themes = {
        "organic": {
            "primary": "#5D7052",
            "secondary": "#C18C5D",
            "background": "#FDFCF8",
            "text": "#2C2C24",
            "accent": "#A85448"
        },
        "tech": {
            "primary": "#2563EB",
            "secondary": "#7C3AED",
            "background": "#F8FAFC",
            "text": "#1E293B",
            "accent": "#06B6D4"
        },
        "classic": {
            "primary": "#475569",
            "secondary": "#64748B",
            "background": "#FFFFFF",
            "text": "#1E293B",
            "accent": "#0F172A"
        }
    }
    return themes.get(theme, themes["organic"])
