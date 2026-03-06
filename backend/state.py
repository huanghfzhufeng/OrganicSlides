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
    title: str                    # MUST be an assertion sentence, not a topic word
    slide_type: str = "content"
    visual_type: str = "illustration"  # illustration|chart|flow|quote|data|cover
    key_points: List[str] = field(default_factory=list)  # MAX 4 items
    path_hint: str = "auto"       # path_a|path_b|auto
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
    # New fields for dual-path rendering
    visual_type: str = "illustration"    # illustration|chart|flow|quote|data|cover
    path_hint: str = "auto"              # path_a|path_b|auto
    image_prompt: Optional[str] = None  # Path B full image prompt (Writer/Visual draft)
    text_to_render: dict = field(default_factory=dict)  # Exact text for AI rendering
    html_content: Optional[str] = None  # Path A complete HTML (Visual agent output)


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
    outline: List[dict]  # Each item: {id, title (assertion), visual_type, path_hint, key_points, notes}
    outline_approved: bool

    # 撰写与视觉阶段的中间产物
    slides_data: List[dict]  # Each item: {title, visual_type, path_hint, image_prompt, text_to_render, ...}

    # 视觉风格配置 (新样式系统)
    style_id: str          # e.g. "snoopy", "neo-brutalism", "nyt-editorial"
    style_config: dict     # Full style config from style registry

    # 视觉风格配置 (旧系统，向后兼容)
    theme_config: dict

    # 视觉总监输出 (Visual agent → RenderPrep → Renderer)
    slide_render_plans: List[dict]  # Per-slide: {render_path, html_content, image_prompt, ...}
    render_path: str                # Overall: "path_a" | "path_b" | "mixed"

    # 渲染进度追踪 (RenderPrep 生成，供前端 SSE 消费)
    render_progress: List[dict]     # Per-slide: {slide_number, total_slides, render_path, status}

    # 资产生成
    generated_assets: List[dict]  # 生成的图片/图表
    slide_files: List[dict]        # Intermediate files: [{page_number, path, type}, ...]

    # 渲染输出
    pptx_path: str  # 最终文件路径

    # 流程控制
    current_status: str  # 用于前端进度条
    current_agent: str   # 当前执行的 Agent
    error: Optional[str]

    # 消息历史 (用于 LLM 上下文)
    messages: List[dict]


def create_initial_state(
    session_id: str,
    user_intent: str,
    theme: str = "organic",
    style_id: Optional[str] = None,
    style_config: Optional[dict] = None,
) -> PresentationState:
    """
    创建初始状态。

    优先使用 style_id + style_config（新样式系统）。
    如果未提供，则回退到旧的 theme 字符串（向后兼容）。
    """
    if style_id and style_config:
        theme_config: dict = {
            # New style system fields
            "style_id": style_id,
            "style": style_config.get("id", style_id),
            "name_zh": style_config.get("name_zh", ""),
            "name_en": style_config.get("name_en", ""),
            "tier": style_config.get("tier", 1),
            "colors": style_config.get("colors", get_theme_colors(theme)),
            "typography": style_config.get("typography", {}),
            "render_paths": style_config.get("render_paths", ["path_a"]),
            "base_style_prompt": style_config.get("base_style_prompt", ""),
            "sample_image_path": style_config.get("sample_image_path", ""),
        }
    else:
        # Backward-compatible legacy theme
        theme_config = {
            "style": theme,
            "colors": get_theme_colors(theme),
        }

    return PresentationState(
        session_id=session_id,
        user_intent=user_intent,
        source_docs=[],
        search_results=[],
        outline=[],
        outline_approved=False,
        slides_data=[],
        theme_config=theme_config,
        style_id=style_id or "",
        style_config=style_config or {},
        slide_render_plans=[],
        render_path="path_a",
        render_progress=[],
        generated_assets=[],
        slide_files=[],
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
