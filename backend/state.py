"""
MAS-PPT 全局状态定义
基于 LangGraph 的多智能体协同演示文稿生成系统
"""

from typing import TypedDict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from runtime_schemas import build_research_packet, build_style_packet, serialize_models
from skills.runtime import get_skill_runtime_packet


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
    visual_type: str = "illustration"
    path_hint: str = "auto"
    image_prompt: Optional[str] = None
    text_to_render: dict = field(default_factory=dict)
    html_content: Optional[str] = None


class PresentationState(TypedDict, total=False):
    """
    LangGraph 全局状态
    这是在整个工作流中传递的状态对象
    """
    # 会话信息
    session_id: str
    user_intent: str  # 用户原始输入
    is_thesis_mode: bool  # 答辩PPT模式（上传论文时启用）
    skill_id: str
    collaboration_mode: str
    skill_packet: dict

    # RAG 相关
    source_docs: List[dict]  # 检索到的上下文文档
    search_results: List[dict]  # 联网搜索结果
    needs_web_search: bool
    research_packet: dict       # Validated ResearchPacket

    # 策划阶段产物 (HITL 介入点)
    outline: List[dict]
    outline_approved: bool
    slide_blueprint: List[dict]
    slide_blueprint_approved: bool
    slide_reviews: List[dict]
    slide_review_required: bool
    slide_review_approved: bool

    # 撰写与视觉阶段的中间产物
    slides_data: List[dict]

    # 视觉风格配置 (新样式系统)
    style_id: str
    style_config: dict
    style_packet: dict     # Validated StylePacket

    # 视觉风格配置 (旧系统，向后兼容)
    theme_config: dict

    # 视觉总监输出
    slide_render_plans: List[dict]
    render_path: str

    # 渲染进度追踪
    render_progress: List[dict]

    # 资产生成
    generated_assets: List[dict]
    slide_files: List[dict]

    # 渲染输出
    pptx_path: str
    pptx_storage_key: str

    # 流程控制
    current_status: str
    current_agent: str
    error: Optional[str]

    # 消息历史
    messages: List[dict]

    # Structured output diagnostics
    planner_diagnostics: dict
    writer_diagnostics: dict
    visual_diagnostics: dict


def create_initial_state(
    session_id: str,
    user_intent: str,
    theme: str = "organic",
    style_id: Optional[str] = None,
    style_config: Optional[dict] = None,
    skill_id: Optional[str] = None,
    collaboration_mode: str = "guided",
    source_docs: Optional[List[dict]] = None,
    is_thesis_mode: bool = False,
) -> PresentationState:
    """
    创建初始状态。

    优先使用 style_id + style_config（新样式系统）。
    如果未提供，则回退到旧的 theme 字符串（向后兼容）。
    """
    skill_runtime_id = skill_id or "huashu-slides"
    skill_packet_data = get_skill_runtime_packet(skill_runtime_id, collaboration_mode)

    if style_id and style_config:
        theme_config: dict = {
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
        theme_config = {
            "style": theme,
            "colors": get_theme_colors(theme),
        }

    research_packet = build_research_packet(user_intent, [], [])
    style_packet = build_style_packet(
        style_id=style_id or theme_config.get("style", ""),
        style_config=style_config or {},
        theme_config=theme_config,
    )

    return PresentationState(
        session_id=session_id,
        user_intent=user_intent,
        is_thesis_mode=is_thesis_mode,
        skill_id=skill_runtime_id,
        collaboration_mode=skill_packet_data.get("collaboration_mode", collaboration_mode),
        skill_packet=skill_packet_data,
        source_docs=source_docs or [],
        search_results=[],
        needs_web_search=False,
        research_packet=serialize_models(research_packet),
        outline=[],
        outline_approved=False,
        slide_blueprint=[],
        slide_blueprint_approved=False,
        slide_reviews=[],
        slide_review_required=False,
        slide_review_approved=False,
        slides_data=[],
        theme_config=theme_config,
        style_id=style_id or "",
        style_config=style_config or {},
        style_packet=serialize_models(style_packet),
        slide_render_plans=[],
        render_path="path_a",
        render_progress=[],
        generated_assets=[],
        slide_files=[],
        pptx_path="",
        pptx_storage_key="",
        current_status="initialized",
        current_agent="",
        error=None,
        messages=[],
        planner_diagnostics={},
        writer_diagnostics={},
        visual_diagnostics={},
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
