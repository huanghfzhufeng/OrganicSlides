"""
策划 Agent (Planner) - 主逻辑
负责分析用户意图，生成结构化大纲
核心原则：标题是断言句（Assertion-Evidence Framework）
"""

import json
import uuid
from typing import Any

from langchain_core.messages import HumanMessage

from agents.planner.prompts import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_USER_TEMPLATE,
    THESIS_DEFENSE_SYSTEM_PROMPT,
    THESIS_DEFENSE_USER_TEMPLATE,
)
from agents.planner.tools import build_context, build_style_context, validate_outline, normalize_outline
from agents.planner.tools import infer_min_outline_slides
from agents.base import (
    extract_json_payload,
    get_llm,
    create_system_message,
    strip_thinking_tags,
)
from skills.runtime import build_skill_prompt_packet


async def run(state: dict) -> dict[str, Any]:
    """
    策划 Agent 入口函数
    分析用户意图，生成结构化大纲（含 visual_type 和 path_hint）
    """
    llm = get_llm(temperature=0.7)

    user_intent = state.get("user_intent", "")
    source_docs = state.get("source_docs", [])
    search_results = state.get("search_results", [])
    style_id = state.get("style_id", "")
    style_config = state.get("style_config", {})
    skill_context = build_skill_prompt_packet(state.get("skill_packet"))

    # 构建上下文
    research_context = build_context(source_docs, search_results)
    style_context = build_style_context(style_id, style_config, user_intent)

    # 答辩模式使用专用提示词
    is_thesis_mode = state.get("is_thesis_mode", False)
    min_slides = infer_min_outline_slides(user_intent, source_docs, is_thesis_mode=is_thesis_mode)
    system_prompt = THESIS_DEFENSE_SYSTEM_PROMPT if is_thesis_mode else PLANNER_SYSTEM_PROMPT
    user_template = THESIS_DEFENSE_USER_TEMPLATE if is_thesis_mode else PLANNER_USER_TEMPLATE

    # 构建用户消息
    user_message = user_template.format(
        user_intent=user_intent,
        skill_context=skill_context,
        style_context=style_context,
        research_context=research_context,
    )

    messages = [
        create_system_message(system_prompt),
        HumanMessage(content=user_message)
    ]

    response = await llm.ainvoke(messages)

    # 解析 LLM 响应（剥离推理标签）
    raw_content = strip_thinking_tags(response.content)
    outline = _parse_outline_response(raw_content)

    # 规范化（补全缺失字段，强制 max 4 key_points）
    outline = normalize_outline(outline)

    # 验证大纲
    is_valid, msg = validate_outline(
        outline,
        is_thesis_mode=is_thesis_mode,
        min_slides=min_slides,
    )
    if not is_valid:
        repaired = await _repair_outline(
            llm=llm,
            base_messages=messages,
            invalid_reason=f"{msg}。当前主题至少应展开成 {min_slides} 页的大纲",
        )
        if repaired:
            outline = normalize_outline(repaired)
            is_valid, msg = validate_outline(
                outline,
                is_thesis_mode=is_thesis_mode,
                min_slides=min_slides,
            )

    if not is_valid:
        outline = _create_default_outline(user_intent, is_thesis_mode=is_thesis_mode)

    return {
        "outline": outline,
        "current_status": "outline_generated",
        "current_agent": "planner",
        "messages": state.get("messages", []) + [
            {
                "role": "assistant",
                "content": f"策划师已生成 {len(outline)} 页大纲",
                "agent": "planner"
            }
        ]
    }


def _parse_outline_response(content: str) -> list:
    """解析 LLM 响应中的大纲"""
    try:
        json_str = extract_json_payload(content)
        result = json.loads(json_str)
        outline = result.get("outline", []) if isinstance(result, dict) else result

        # 为每个章节添加 ID（如果没有）
        for i, section in enumerate(outline):
            if "id" not in section:
                section["id"] = f"section_{uuid.uuid4().hex[:8]}"

        return outline

    except (json.JSONDecodeError, IndexError, KeyError):
        return []


async def _repair_outline(
    llm,
    base_messages: list,
    invalid_reason: str,
) -> list:
    repair_message = HumanMessage(
        content=(
            "你上一次输出的大纲无效，原因如下：\n"
            f"{invalid_reason}\n\n"
            "请重新输出合法 JSON，要求：\n"
            "1. 只返回 JSON，不要 markdown 代码块\n"
            "2. 顶层必须包含 outline 数组\n"
            "3. 标题必须是断言句，不能是泛化主题词\n"
            "4. 每页最多 4 个要点，每条尽量短\n"
            "5. 保留 cover 开头，并给出明确的结论/行动页收尾"
        )
    )
    response = await llm.ainvoke([*base_messages, repair_message])
    return _parse_outline_response(strip_thinking_tags(response.content))


def _create_default_outline(user_intent: str = "", *, is_thesis_mode: bool = False) -> list:
    """创建兜底大纲，但尽量保持与主题相关。"""
    topic = _extract_topic(user_intent)
    if is_thesis_mode:
        return [
            {
                "id": "cover",
                "title": topic,
                "slide_type": "cover",
                "visual_type": "cover",
                "key_points": [],
                "path_hint": "path_b",
                "notes": "",
            },
            {
                "id": "background",
                "title": f"{topic}的研究问题具有明确现实价值",
                "slide_type": "content",
                "visual_type": "illustration",
                "key_points": ["研究动机", "现实缺口", "核心问题"],
                "path_hint": "auto",
                "notes": "说明研究背景、问题和价值。",
            },
            {
                "id": "gap",
                "title": f"现有研究仍未充分回答{topic}里的关键空白",
                "slide_type": "content",
                "visual_type": "data",
                "key_points": ["现有工作", "主要不足", "研究空白"],
                "path_hint": "path_a",
                "notes": "概述先行研究与不足。",
            },
            {
                "id": "method",
                "title": f"我们用清晰的方法路径验证了{topic}的关键假设",
                "slide_type": "content",
                "visual_type": "flow",
                "key_points": ["研究对象", "方法流程", "数据来源"],
                "path_hint": "path_a",
                "notes": "交代方法、数据与实验设计。",
            },
            {
                "id": "dataset",
                "title": f"{topic}的数据来源与实验设置保证了结论可信",
                "slide_type": "data",
                "visual_type": "data",
                "key_points": ["数据来源", "样本范围", "实验设置"],
                "path_hint": "path_a",
                "notes": "补充实验设置和数据边界。",
            },
            {
                "id": "results",
                "title": f"实验结果支持了{topic}的核心判断",
                "slide_type": "chart",
                "visual_type": "chart",
                "key_points": ["关键结果", "对比优势", "显著变化"],
                "path_hint": "path_a",
                "notes": "展示关键图表与结果。",
            },
            {
                "id": "discussion",
                "title": f"{topic}的结果解释了为什么新方法能够取得优势",
                "slide_type": "content",
                "visual_type": "flow",
                "key_points": ["结果解释", "优势来源", "理论意义"],
                "path_hint": "auto",
                "notes": "解释结果及其意义。",
            },
            {
                "id": "conclusion",
                "title": f"{topic}的研究结论为后续实践提供了可执行方向",
                "slide_type": "conclusion",
                "visual_type": "quote",
                "key_points": ["核心结论", "实践意义", "未来工作"],
                "path_hint": "auto",
                "notes": "总结贡献与下一步。",
            },
            {
                "id": "limitation",
                "title": f"{topic}仍然存在边界条件与后续优化空间",
                "slide_type": "content",
                "visual_type": "data",
                "key_points": ["研究局限", "风险边界", "改进方向"],
                "path_hint": "path_a",
                "notes": "诚实呈现研究局限。",
            },
            {
                "id": "qa",
                "title": "欢迎各位老师就研究细节继续提问",
                "slide_type": "conclusion",
                "visual_type": "cover",
                "key_points": [],
                "path_hint": "path_b",
                "notes": "Q&A 结束页。",
            },
        ]

    return [
        {
            "id": "cover",
            "title": topic,
            "slide_type": "cover",
            "visual_type": "cover",
            "key_points": [],
            "path_hint": "path_b",
            "notes": ""
        },
        {
            "id": "intro",
            "title": f"{topic}已经成为当前最需要被看清的问题",
            "slide_type": "content",
            "visual_type": "illustration",
            "key_points": ["背景现状", "核心矛盾", "关键影响"],
            "path_hint": "auto",
            "notes": "介绍背景和问题"
        },
        {
            "id": "stakes",
            "title": f"如果继续忽视{topic}，代价会持续累积",
            "slide_type": "content",
            "visual_type": "quote",
            "key_points": ["业务代价", "组织影响", "窗口缩短"],
            "path_hint": "auto",
            "notes": "强调问题的代价与 urgency。"
        },
        {
            "id": "diagnosis",
            "title": f"{topic}之所以反复出现，是因为旧做法没有抓住根因",
            "slide_type": "content",
            "visual_type": "flow",
            "key_points": ["表层现象", "根本原因", "旧法失效"],
            "path_hint": "auto",
            "notes": "拆解问题根因。"
        },
        {
            "id": "solution",
            "title": f"解决{topic}需要把动作收敛到三个关键抓手",
            "slide_type": "content",
            "visual_type": "flow",
            "key_points": ["关键抓手", "执行顺序", "协同关系"],
            "path_hint": "auto",
            "notes": "提出方法框架。"
        },
        {
            "id": "evidence",
            "title": f"{topic}的成效必须用数据和案例共同证明",
            "slide_type": "chart",
            "visual_type": "chart",
            "key_points": ["核心指标", "对比案例", "结果验证"],
            "path_hint": "path_a",
            "notes": "用案例和结果增强说服力。"
        },
        {
            "id": "rollout",
            "title": f"{topic}落地时最容易卡住的是执行顺序而不是认知共识",
            "slide_type": "content",
            "visual_type": "flow",
            "key_points": ["先后顺序", "资源配置", "风险控制"],
            "path_hint": "auto",
            "notes": "解释如何真正落地。"
        },
        {
            "id": "conclusion",
            "title": f"下一步应围绕{topic}尽快形成明确行动",
            "slide_type": "conclusion",
            "visual_type": "quote",
            "key_points": ["核心结论", "执行建议", "下一步行动"],
            "path_hint": "path_b",
            "notes": "总结与行动号召"
        },
    ]


def _extract_topic(user_intent: str) -> str:
    cleaned = (user_intent or "").strip()
    if not cleaned:
        return "演示文稿"

    for separator in ("，", "。", "\n", ":", "："):
        if separator in cleaned:
            cleaned = cleaned.split(separator)[0].strip()
            break

    return cleaned[:18] if cleaned else "演示文稿"
