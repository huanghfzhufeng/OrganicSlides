"""
MAS-PPT 智能体模块
包含所有 AI Agent 的实现

目录结构：
agents/
├── __init__.py        # 本文件
├── base.py            # Agent 基础类和工具
├── planner/           # 策划 Agent
│   ├── agent.py
│   ├── prompts.py
│   └── tools.py
├── researcher/        # 研究 Agent
│   ├── agent.py
│   ├── prompts.py
│   └── tools.py
├── writer/            # 撰写 Agent
│   ├── agent.py
│   ├── prompts.py
│   └── tools.py
├── visual/            # 视觉总监 Agent
│   ├── agent.py
│   ├── prompts.py
│   └── tools.py
└── renderer/          # 渲染引擎 Agent
    ├── agent.py
    ├── prompts.py
    └── tools.py
"""

from agents.planner import run as planner_agent
from agents.researcher import run as researcher_agent
from agents.writer import run as writer_agent
from agents.visual import run as visual_agent
from agents.renderer import run as renderer_agent

__all__ = [
    "planner_agent",
    "researcher_agent", 
    "writer_agent",
    "visual_agent",
    "renderer_agent"
]
