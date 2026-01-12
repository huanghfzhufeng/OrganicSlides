"""
渲染引擎 Agent (Renderer)
负责调用 python-pptx 生成最终的 .pptx 文件
"""

from .agent import run

__all__ = ["run"]
