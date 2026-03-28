"""
研究 Agent (Researcher)
负责 RAG 检索和联网搜索素材
"""

from .agent import run, run_local, run_web

__all__ = ["run", "run_local", "run_web"]
