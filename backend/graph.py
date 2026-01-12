"""
LangGraph 工作流编排
定义多智能体协作的状态图
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import PresentationState, create_initial_state
from agents import (
    researcher_agent,
    planner_agent,
    writer_agent,
    visual_agent,
    renderer_agent
)


def should_continue_after_outline(state: PresentationState) -> Literal["wait_for_approval", "writer"]:
    """
    条件路由：检查大纲是否已被用户确认
    这是 HITL (Human-in-the-Loop) 的关键点
    """
    if state.get("outline_approved", False):
        return "writer"
    return "wait_for_approval"


def check_error(state: PresentationState) -> Literal["error", "continue"]:
    """检查是否有错误"""
    if state.get("error"):
        return "error"
    return "continue"


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


async def error_node(state: PresentationState) -> dict:
    """错误处理节点"""
    return {
        "current_status": "error",
        "current_agent": "error_handler"
    }


def create_workflow() -> StateGraph:
    """
    创建 LangGraph 工作流
    
    流程：Input -> Researcher -> Planner -> [HITL] -> Writer -> Visual -> Renderer
    """
    # 创建状态图
    workflow = StateGraph(PresentationState)
    
    # 添加节点
    workflow.add_node("input", input_node)
    workflow.add_node("researcher", researcher_agent)
    workflow.add_node("planner", planner_agent)
    workflow.add_node("wait_for_approval", wait_for_approval_node)
    workflow.add_node("writer", writer_agent)
    workflow.add_node("visual", visual_agent)
    workflow.add_node("renderer", renderer_agent)
    workflow.add_node("error", error_node)
    
    # 设置入口点
    workflow.set_entry_point("input")
    
    # 添加边 - 定义节点间的流转
    workflow.add_edge("input", "researcher")
    workflow.add_edge("researcher", "planner")
    
    # 条件边 - HITL 中断点
    workflow.add_conditional_edges(
        "planner",
        should_continue_after_outline,
        {
            "wait_for_approval": "wait_for_approval",
            "writer": "writer"
        }
    )
    
    # 等待确认后的边 - 将由外部 resume 触发
    workflow.add_edge("wait_for_approval", END)  # 暂停在这里
    
    # 后续流程
    workflow.add_edge("writer", "visual")
    workflow.add_edge("visual", "renderer")
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


# 创建第二阶段工作流（从 Writer 开始）
def create_resume_workflow() -> StateGraph:
    """
    创建恢复工作流 - 从 Writer 开始
    用于用户确认大纲后继续执行
    """
    workflow = StateGraph(PresentationState)
    
    workflow.add_node("writer", writer_agent)
    workflow.add_node("visual", visual_agent)
    workflow.add_node("renderer", renderer_agent)
    
    workflow.set_entry_point("writer")
    
    workflow.add_edge("writer", "visual")
    workflow.add_edge("visual", "renderer")
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
