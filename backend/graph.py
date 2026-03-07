"""
LangGraph 工作流编排
定义多智能体协作的状态图

流程：Input -> Researcher -> Planner -> [HITL] -> Writer -> Visual -> RenderPrep -> Renderer
新增：render_preparation 节点（验证、分组、进度追踪），支持双渲染路径
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from pydantic import ValidationError

from state import PresentationState
from runtime_schemas import (
    build_style_packet,
    serialize_models,
    validate_render_plans,
    validation_error_message,
)
from agents import (
    researcher_agent,
    planner_agent,
    writer_agent,
    visual_agent,
    renderer_agent
)
from agents.renderer.preflight import validate_renderer_preflight


# ---------------------------------------------------------------------------
# Routing conditions
# ---------------------------------------------------------------------------

def should_continue_after_outline(state: PresentationState) -> Literal["wait_for_approval", "writer", "error"]:
    """
    条件路由：检查大纲是否已被用户确认
    这是 HITL (Human-in-the-Loop) 的关键点
    """
    if state.get("error"):
        return "error"
    if state.get("outline_approved", False):
        return "writer"
    return "wait_for_approval"


def check_error(state: PresentationState) -> Literal["error", "continue"]:
    """检查是否有错误"""
    if state.get("error"):
        return "error"
    return "continue"


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
    style_config = state.get("style_packet", state.get("style_config", {}))
    theme_config = state.get("theme_config", {})
    slides_data = state.get("slides_data", [])

    try:
        style_packet = build_style_packet(
            style_id=state.get("style_id", ""),
            style_config=style_config,
            theme_config=theme_config,
        )
    except ValidationError as exc:
        return _render_preparation_error(state, validation_error_message(exc))
    style_config = serialize_models(style_packet)

    # --- 1. Validate slide_render_plans ---
    if not slide_render_plans and slides_data:
        message = "Visual 未返回 slide_render_plans，渲染准备阶段拒绝静默回退"
        return _render_preparation_error(state, message)
    if not slide_render_plans:
        return _render_preparation_error(state, "缺少可渲染的 slide_render_plans")

    # --- 2. Validate each plan has required fields ---
    try:
        validated_plans = serialize_models(
            validate_render_plans(slide_render_plans, style_packet)
        )
    except ValidationError as exc:
        return _render_preparation_error(state, validation_error_message(exc))

    preflight_ok, preflight_message = validate_renderer_preflight(validated_plans, style_config)
    if not preflight_ok:
        return _render_preparation_error(state, preflight_message)

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

    # --- 4. Build render_progress tracking list ---
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

    return {
        "slide_render_plans": validated_plans,
        "render_path": overall_path,
        "style_config": style_config,
        "style_packet": style_config,
        "render_progress": render_progress,
        "current_status": "render_prepared",
        "current_agent": "render_prep",
        "messages": state.get("messages", []) + [
            {
                "role": "system",
                "content": (
                    f"渲染准备完成: {len(validated_plans)} 张幻灯片 "
                    f"（Path A: {path_a_count} 张, Path B: {path_b_count} 张, "
                    f"整体路径: {overall_path}）"
                ),
                "agent": "render_prep",
            }
        ]
    }


async def error_node(state: PresentationState) -> dict:
    """错误处理节点"""
    error = state.get("error", "未知错误")
    return {
        "current_status": "error",
        "current_agent": "error_handler",
        "error": error,
        "messages": state.get("messages", []) + [
            {"role": "system", "content": f"工作流错误: {error}", "agent": "error_handler"}
        ]
    }


def _render_preparation_error(state: PresentationState, message: str) -> dict:
    return {
        "current_status": "render_preparation_error",
        "current_agent": "render_prep",
        "error": message,
        "messages": state.get("messages", []) + [
            {
                "role": "system",
                "content": f"渲染准备失败: {message}",
                "agent": "render_prep",
            }
        ],
    }

# ---------------------------------------------------------------------------
# Workflow definitions
# ---------------------------------------------------------------------------

def create_workflow() -> StateGraph:
    """
    创建 LangGraph 工作流

    流程：Input → Researcher → Planner → [HITL] → Writer → Visual → RenderPrep → Renderer
    """
    workflow = StateGraph(PresentationState)

    # 添加节点
    workflow.add_node("input", input_node)
    workflow.add_node("researcher", researcher_agent)
    workflow.add_node("planner", planner_agent)
    workflow.add_node("wait_for_approval", wait_for_approval_node)
    workflow.add_node("writer", writer_agent)
    workflow.add_node("visual", visual_agent)
    workflow.add_node("render_preparation", render_preparation_node)  # NEW
    workflow.add_node("renderer", renderer_agent)
    workflow.add_node("error", error_node)

    # 设置入口点
    workflow.set_entry_point("input")

    # 添加边 - 定义节点间的流转
    workflow.add_edge("input", "researcher")
    workflow.add_conditional_edges(
        "researcher",
        check_error,
        {
            "error": "error",
            "continue": "planner",
        }
    )

    # 条件边 - HITL 中断点
    workflow.add_conditional_edges(
        "planner",
        should_continue_after_outline,
        {
            "error": "error",
            "wait_for_approval": "wait_for_approval",
            "writer": "writer",
        }
    )

    # 等待确认后的边 - 将由外部 resume 触发
    workflow.add_edge("wait_for_approval", END)  # 暂停在这里

    # 后续流程（新增 render_preparation 节点）
    workflow.add_conditional_edges(
        "writer",
        check_error,
        {
            "error": "error",
            "continue": "visual",
        }
    )
    workflow.add_conditional_edges(
        "visual",
        check_error,
        {
            "error": "error",
            "continue": "render_preparation",
        }
    )
    workflow.add_conditional_edges(
        "render_preparation",
        check_error,
        {
            "error": "error",
            "continue": "renderer",
        }
    )
    workflow.add_conditional_edges(
        "renderer",
        check_error,
        {
            "error": "error",
            "continue": END,
        }
    )
    workflow.add_edge("error", END)

    return workflow


def create_app():
    """
    创建可执行的 LangGraph 应用
    使用无状态编译结果；工作流状态由外部持久化层负责保存。
    """
    workflow = create_workflow()
    return workflow.compile()


def create_resume_workflow() -> StateGraph:
    """
    创建恢复工作流 - 从 Writer 开始
    用于用户确认大纲后继续执行
    """
    workflow = StateGraph(PresentationState)

    workflow.add_node("writer", writer_agent)
    workflow.add_node("visual", visual_agent)
    workflow.add_node("render_preparation", render_preparation_node)  # NEW
    workflow.add_node("renderer", renderer_agent)
    workflow.add_node("error", error_node)

    workflow.set_entry_point("writer")

    workflow.add_conditional_edges(
        "writer",
        check_error,
        {
            "error": "error",
            "continue": "visual",
        }
    )
    workflow.add_conditional_edges(
        "visual",
        check_error,
        {
            "error": "error",
            "continue": "render_preparation",
        }
    )
    workflow.add_conditional_edges(
        "render_preparation",
        check_error,
        {
            "error": "error",
            "continue": "renderer",
        }
    )
    workflow.add_conditional_edges(
        "renderer",
        check_error,
        {
            "error": "error",
            "continue": END,
        }
    )
    workflow.add_edge("error", END)

    return workflow


def create_resume_app():
    """创建恢复阶段的应用"""
    workflow = create_resume_workflow()
    return workflow.compile()


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
