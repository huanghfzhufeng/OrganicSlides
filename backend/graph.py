"""
LangGraph 工作流编排
定义多智能体协作的状态图

流程：Input -> ResearchLocal -> [ResearchWeb] -> Planner -> [HITL] -> Writer -> Visual -> RenderPrep -> Renderer
新增：render_preparation 节点（验证、分组、进度追踪），支持双渲染路径
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import PresentationState, create_initial_state
from agents import (
    planner_agent,
    writer_agent,
    visual_agent,
    renderer_agent
)
from agents.researcher import run_local as researcher_local_agent, run_web as researcher_web_agent


# ---------------------------------------------------------------------------
# Routing conditions
# ---------------------------------------------------------------------------

def should_continue_after_outline(state: PresentationState) -> Literal["wait_for_approval", "writer"]:
    """
    条件路由：检查大纲是否已被用户确认
    这是 HITL (Human-in-the-Loop) 的关键点
    """
    if state.get("outline_approved", False):
        return "writer"
    return "wait_for_approval"


def should_continue_after_local_research(
    state: PresentationState,
) -> Literal["researcher_web", "planner"]:
    """本地检索后，根据需要决定是否继续联网搜索。"""
    if state.get("needs_web_search", False):
        return "researcher_web"
    return "planner"


def check_error(state: PresentationState) -> Literal["error", "continue"]:
    """检查是否有错误"""
    if state.get("error"):
        return "error"
    return "continue"


def should_continue_after_render_preparation(
    state: PresentationState,
) -> Literal["wait_for_slide_review", "renderer"]:
    """Collaborative mode pauses after render prep for per-slide review."""
    if (
        state.get("collaboration_mode") == "collaborative"
        and not state.get("slide_review_approved", False)
    ):
        return "wait_for_slide_review"
    return "renderer"


# ---------------------------------------------------------------------------
# Flow nodes
# ---------------------------------------------------------------------------

async def input_node(state: PresentationState) -> dict:
    """
    输入节点 - 接收用户输入并初始化流程
    """
    return {
        "current_status": "processing_input",
        "current_agent": "input",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": "工作流已启动", "agent": "system"}
        ]
    }


async def wait_for_approval_node(state: PresentationState) -> dict:
    """
    等待用户确认节点 - 这里会中断等待人工确认
    """
    return {
        "current_status": "waiting_for_outline_approval",
        "current_agent": "hitl",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": "等待用户确认大纲...", "agent": "hitl"}
        ]
    }


async def wait_for_slide_review_node(state: PresentationState) -> dict:
    """Pause before renderer so collaborative users can review slide drafts."""
    slide_count = len(state.get("slide_render_plans", [])) or len(state.get("slides_data", []))
    return {
        "current_status": "waiting_for_slide_review",
        "current_agent": "collaborative_reviewer",
        "slide_review_required": True,
        "slide_review_approved": False,
        "messages": state.get("messages", []) + [
            {
                "role": "system",
                "content": f"等待用户逐页审阅，共 {slide_count} 页待确认",
                "agent": "collaborative_reviewer",
            }
        ]
    }


async def render_preparation_node(state: PresentationState) -> dict:
    """
    渲染准备节点（Visual 和 Renderer 之间）

    职责：
    1. 验证 Visual agent 输出的 slide_render_plans 完整性
    2. 统计 path_a / path_b 分布，确定整体渲染路径
    3. 验证 style_config 中包含渲染所需的关键字段
    4. 生成初始 render_progress 追踪列表（供前端 SSE 使用）
    5. 如果 style_config 缺失，尝试从 theme_config 回退
    """
    slide_render_plans = state.get("slide_render_plans", [])
    style_config = state.get("style_config", {})
    theme_config = state.get("theme_config", {})
    slides_data = state.get("slides_data", [])

    # --- 1. Validate or build slide_render_plans ---
    if not slide_render_plans and slides_data:
        # Visual agent was skipped or failed — build minimal plans from slides_data
        slide_render_plans = _build_fallback_plans(slides_data, style_config or theme_config)

    # --- 1b. Merge text content from slides_data into render plans ---
    # slide_render_plans (from Visual) only has rendering directives;
    # slides_data (from Writer) has title, content, speaker_notes.
    # The renderer needs both.
    slides_by_page = {
        sd.get("page_number", i + 1): sd
        for i, sd in enumerate(slides_data)
    }
    enriched_plans = []
    for i, plan in enumerate(slide_render_plans):
        page = plan.get("page_number", i + 1)
        writer_data = slides_by_page.get(page, {})
        enriched_plans.append({
            **writer_data,  # title, content, speaker_notes, image_prompt, etc.
            **plan,         # render_path, html_content, layout_name, color_system (overrides)
            "page_number": page,
        })
    slide_render_plans = enriched_plans

    # --- 2. Validate each plan has required fields ---
    validated_plans = []
    for plan in slide_render_plans:
        validated = _validate_render_plan(plan, style_config)
        validated_plans.append(validated)

    # --- 3. Determine overall render_path ---
    # Filter to only path_a and path_b for overall classification
    raw_paths = {p.get("render_path", "path_a") for p in validated_plans}
    canonical_paths = {p for p in raw_paths if p in ("path_a", "path_b")}
    if canonical_paths == {"path_a"} or not canonical_paths:
        overall_path = "path_a"
    elif canonical_paths == {"path_b"}:
        overall_path = "path_b"
    else:
        overall_path = "mixed"

    # --- 4. Validate style_config has required fields ---
    if not style_config and theme_config:
        # Build minimal style_config from legacy theme_config for backward compat
        style_config = _build_style_config_from_theme(theme_config)

    # --- 5. Build render_progress tracking list ---
    render_progress = [
        {
            "slide_number": plan.get("page_number", i + 1),
            "total_slides": len(validated_plans),
            "render_path": plan.get("render_path", "path_a"),
            "status": "pending",  # pending → generating → complete | failed
        }
        for i, plan in enumerate(validated_plans)
    ]

    path_a_count = sum(1 for p in validated_plans if p.get("render_path") == "path_a")
    path_b_count = sum(1 for p in validated_plans if p.get("render_path") == "path_b")
    existing_reviews = state.get("slide_reviews", [])
    review_status_by_page = {
        int(item.get("page_number")): item for item in existing_reviews if item.get("page_number")
    }
    slide_reviews = []
    for i, plan in enumerate(validated_plans):
        page_number = plan.get("page_number", i + 1)
        existing = review_status_by_page.get(page_number, {})
        slide_reviews.append(
            {
                "page_number": page_number,
                "status": existing.get("status", "pending"),
                "accepted": bool(existing.get("accepted", False)),
                "revision_count": int(existing.get("revision_count", 0)),
                "feedback": existing.get("feedback", ""),
            }
        )
    review_required = state.get("collaboration_mode") == "collaborative"

    return {
        "slide_render_plans": validated_plans,
        "render_path": overall_path,
        "style_config": style_config,
        "render_progress": render_progress,
        "slide_reviews": slide_reviews,
        "slide_review_required": review_required,
        "slide_review_approved": False if review_required else state.get("slide_review_approved", False),
        "current_status": "waiting_for_slide_review" if review_required else "render_prepared",
        "current_agent": "collaborative_reviewer" if review_required else "render_prep",
        "messages": state.get("messages", []) + [
            {
                "role": "system",
                "content": (
                    f"渲染准备完成: {len(validated_plans)} 张幻灯片 "
                    f"（Path A: {path_a_count} 张, Path B: {path_b_count} 张, "
                    f"整体路径: {overall_path}）"
                ),
                "agent": "collaborative_reviewer" if review_required else "render_prep",
            }
        ]
    }


async def error_node(state: PresentationState) -> dict:
    """错误处理节点"""
    error = state.get("error", "未知错误")
    return {
        "current_status": "error",
        "current_agent": "error_handler",
        "messages": state.get("messages", []) + [
            {"role": "system", "content": f"工作流错误: {error}", "agent": "error_handler"}
        ]
    }


# ---------------------------------------------------------------------------
# Helper functions for render_preparation_node
# ---------------------------------------------------------------------------

def _validate_render_plan(plan: dict, style_config: dict) -> dict:
    """
    Validate and fill in missing fields in a render plan.
    Returns a new dict (immutable pattern).
    Preserves text content fields (title, content, speaker_notes) from Writer.
    """
    render_path = plan.get("render_path", "path_a")
    colors = style_config.get("colors", {}) if style_config else {}

    return {
        "page_number": plan.get("page_number", 0),
        "render_path": render_path,
        "layout_name": plan.get("layout_name", "bullet_list"),
        "html_content": plan.get("html_content"),
        "image_prompt": plan.get("image_prompt"),
        "style_notes": plan.get("style_notes", ""),
        "color_system": plan.get("color_system") or {
            "background": colors.get("background", "#FFFFFF"),
            "text": colors.get("text", "#1A1A1A"),
            "accent": colors.get("accent", "#0984E3"),
        },
        # Preserve Writer's text content for fallback rendering
        "title": plan.get("title", ""),
        "content": plan.get("content", {}),
        "speaker_notes": plan.get("speaker_notes", ""),
        "visual_type": plan.get("visual_type", ""),
        "text_to_render": plan.get("text_to_render", {}),
    }


def _build_fallback_plans(slides_data: list, config: dict) -> list:
    """
    Build minimal slide_render_plans from slides_data when Visual agent output is missing.
    All slides default to path_a.  Includes text content for fallback rendering.
    """
    colors = config.get("colors", {})
    return [
        {
            "page_number": slide.get("page_number", i + 1),
            "render_path": slide.get("path_hint", "path_a") if slide.get("path_hint") in ("path_a", "path_b") else "path_a",
            "layout_name": slide.get("layout_intent", "bullet_list"),
            "html_content": slide.get("html_content"),
            "image_prompt": slide.get("image_prompt"),
            "style_notes": "Fallback plan from slides_data",
            "color_system": {
                "background": colors.get("background", "#FFFFFF"),
                "text": colors.get("text", "#1A1A1A"),
                "accent": colors.get("accent", "#0984E3"),
            },
            # Preserve text content for fallback rendering
            "title": slide.get("title", ""),
            "content": slide.get("content", {}),
            "speaker_notes": slide.get("speaker_notes", ""),
            "visual_type": slide.get("visual_type", ""),
            "text_to_render": slide.get("text_to_render", {}),
        }
        for i, slide in enumerate(slides_data)
    ]


def _build_style_config_from_theme(theme_config: dict) -> dict:
    """
    Build a minimal style_config from legacy theme_config for backward compatibility.
    """
    colors = theme_config.get("colors", {})
    return {
        "id": theme_config.get("style") or theme_config.get("style_id", "organic"),
        "name_zh": theme_config.get("name_zh", ""),
        "name_en": theme_config.get(
            "name_en",
            theme_config.get("style", theme_config.get("style_id", "Organic"))
        ),
        "tier": theme_config.get("tier", 1),
        "render_paths": theme_config.get("render_paths", ["path_a"]),
        "colors": colors,
        "typography": theme_config.get("typography", {}),
        "base_style_prompt": theme_config.get("base_style_prompt"),
        "sample_image_path": theme_config.get("sample_image_path", ""),
        "render_path_preference": theme_config.get("render_path_preference", "auto"),
    }


# ---------------------------------------------------------------------------
# Workflow definitions
# ---------------------------------------------------------------------------

def create_workflow() -> StateGraph:
    """
    创建 LangGraph 工作流

    流程：Input → ResearchLocal → [ResearchWeb] → Planner → [HITL] → Writer → Visual → RenderPrep → Renderer
    """
    workflow = StateGraph(PresentationState)

    # 添加节点
    workflow.add_node("input", input_node)
    workflow.add_node("researcher_local", researcher_local_agent)
    workflow.add_node("researcher_web", researcher_web_agent)
    workflow.add_node("planner", planner_agent)
    workflow.add_node("wait_for_approval", wait_for_approval_node)
    workflow.add_node("wait_for_slide_review", wait_for_slide_review_node)
    workflow.add_node("writer", writer_agent)
    workflow.add_node("visual", visual_agent)
    workflow.add_node("render_preparation", render_preparation_node)  # NEW
    workflow.add_node("renderer", renderer_agent)
    workflow.add_node("error", error_node)

    # 设置入口点
    workflow.set_entry_point("input")

    # 添加边 - 定义节点间的流转
    workflow.add_edge("input", "researcher_local")
    workflow.add_conditional_edges(
        "researcher_local",
        should_continue_after_local_research,
        {
            "researcher_web": "researcher_web",
            "planner": "planner",
        }
    )
    workflow.add_edge("researcher_web", "planner")

    # 条件边 - HITL 中断点
    workflow.add_conditional_edges(
        "planner",
        should_continue_after_outline,
        {
            "wait_for_approval": "wait_for_approval",
            "writer": "writer",
        }
    )

    # 等待确认后的边 - 将由外部 resume 触发
    workflow.add_edge("wait_for_approval", END)  # 暂停在这里

    # 后续流程（新增 render_preparation 节点）
    workflow.add_edge("writer", "visual")
    workflow.add_edge("visual", "render_preparation")  # NEW: validate before rendering
    workflow.add_conditional_edges(
        "render_preparation",
        should_continue_after_render_preparation,
        {
            "wait_for_slide_review": "wait_for_slide_review",
            "renderer": "renderer",
        }
    )
    workflow.add_edge("wait_for_slide_review", END)
    workflow.add_edge("renderer", END)
    workflow.add_edge("error", END)

    return workflow


def create_app():
    """
    创建可执行的 LangGraph 应用
    带有检查点支持，用于 HITL 中断和恢复
    """
    workflow = create_workflow()

    # 使用内存检查点（生产环境应使用 PostgreSQL）
    memory = MemorySaver()

    # 编译工作流
    app = workflow.compile(
        checkpointer=memory,
        interrupt_before=["wait_for_approval"]  # 在等待确认前中断
    )

    return app


def create_resume_workflow() -> StateGraph:
    """
    创建恢复工作流 - 从 Writer 开始
    用于用户确认大纲后继续执行
    """
    workflow = StateGraph(PresentationState)

    workflow.add_node("writer", writer_agent)
    workflow.add_node("visual", visual_agent)
    workflow.add_node("render_preparation", render_preparation_node)  # NEW
    workflow.add_node("wait_for_slide_review", wait_for_slide_review_node)
    workflow.add_node("renderer", renderer_agent)

    workflow.set_entry_point("writer")

    workflow.add_edge("writer", "visual")
    workflow.add_edge("visual", "render_preparation")  # NEW
    workflow.add_conditional_edges(
        "render_preparation",
        should_continue_after_render_preparation,
        {
            "wait_for_slide_review": "wait_for_slide_review",
            "renderer": "renderer",
        }
    )
    workflow.add_edge("wait_for_slide_review", END)
    workflow.add_edge("renderer", END)

    return workflow


def create_resume_app():
    """创建恢复阶段的应用"""
    workflow = create_resume_workflow()
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# 全局应用实例
main_app = None
resume_app = None


def get_main_app():
    """获取主工作流应用"""
    global main_app
    if main_app is None:
        main_app = create_app()
    return main_app


def get_resume_app():
    """获取恢复工作流应用"""
    global resume_app
    if resume_app is None:
        resume_app = create_resume_app()
    return resume_app
