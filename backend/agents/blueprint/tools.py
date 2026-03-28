"""Helpers for building and validating slide blueprints."""

from __future__ import annotations

from typing import Any, Dict, List


def format_outline_for_prompt(outline: List[Dict[str, Any]]) -> str:
    if not outline:
        return "暂无大纲"

    lines: list[str] = []
    for index, section in enumerate(outline, start=1):
        title = section.get("title", "未命名章节")
        slide_type = section.get("slide_type") or section.get("type", "content")
        visual_type = section.get("visual_type", "illustration")
        key_points = section.get("key_points", [])
        notes = section.get("notes", "")

        lines.append(f"{index}. [{slide_type}] {title}")
        lines.append(f"   visual_type={visual_type}")
        if key_points:
            lines.append(f"   key_points={', '.join(str(item) for item in key_points[:4])}")
        if notes:
            lines.append(f"   notes={notes}")

    return "\n".join(lines)


def format_docs_for_context(source_docs: List[Dict[str, Any]], max_docs: int = 4) -> str:
    if not source_docs:
        return ""

    docs_text = "\n".join(
        f"[资料 {index + 1}]: {doc.get('content', '')[:320]}..."
        for index, doc in enumerate(source_docs[:max_docs])
    )
    return f"<参考资料>\n{docs_text}\n</参考资料>"


def validate_slide_blueprint(
    blueprint: List[Dict[str, Any]],
    outline: List[Dict[str, Any]],
) -> tuple[bool, str]:
    if not blueprint:
        return False, "页级策划不能为空"

    if len(blueprint) < len(outline):
        return False, f"页级策划页数不足：章节数 {len(outline)}，蓝图仅 {len(blueprint)} 页"

    valid_visual_types = {"illustration", "chart", "flow", "quote", "data", "cover"}
    valid_path_hints = {"path_a", "path_b", "auto"}
    valid_evidence_types = {"data", "case", "logic", "quote", "story"}

    for index, item in enumerate(blueprint, start=1):
        if not str(item.get("section_id", "")).strip():
            return False, f"第 {index} 页缺少 section_id"
        if not str(item.get("section_title", "")).strip():
            return False, f"第 {index} 页缺少 section_title"
        if not str(item.get("title", "")).strip():
            return False, f"第 {index} 页缺少 title"
        if not str(item.get("goal", "")).strip():
            return False, f"第 {index} 页缺少 goal"
        if not str(item.get("content_brief", "")).strip():
            return False, f"第 {index} 页缺少 content_brief"

        key_points = item.get("key_points", [])
        if len(key_points) > 4:
            return False, f"第 {index} 页 key_points 超过 4 条"

        visual_type = item.get("visual_type")
        if visual_type not in valid_visual_types:
            return False, f"第 {index} 页 visual_type 无效：{visual_type}"

        path_hint = item.get("path_hint")
        if path_hint not in valid_path_hints:
            return False, f"第 {index} 页 path_hint 无效：{path_hint}"

        evidence_type = item.get("evidence_type")
        if evidence_type not in valid_evidence_types:
            return False, f"第 {index} 页 evidence_type 无效：{evidence_type}"

    return True, "验证通过"


def normalize_slide_blueprint(blueprint: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: list[Dict[str, Any]] = []
    for index, item in enumerate(blueprint, start=1):
        slide_type = item.get("slide_type") or item.get("type", "content")
        visual_type = item.get("visual_type", "illustration")
        if slide_type == "cover":
            visual_type = "cover"

        normalized.append(
            {
                **item,
                "id": item.get("id") or f"slide_{index}",
                "page_number": index,
                "slide_type": slide_type,
                "visual_type": visual_type,
                "path_hint": item.get("path_hint", "auto"),
                "key_points": list(item.get("key_points", []))[:4],
                "evidence_type": item.get("evidence_type", _derive_evidence_type(visual_type)),
            }
        )
    return normalized


def create_default_blueprint_from_outline(outline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    slides: list[Dict[str, Any]] = []
    page_number = 1

    for section in outline:
        section_id = section.get("id", f"section_{page_number}")
        section_title = section.get("title", f"章节 {page_number}")
        slide_type = section.get("slide_type") or section.get("type", "content")
        visual_type = section.get("visual_type", "illustration")
        path_hint = section.get("path_hint", "auto")
        key_points = [str(item) for item in section.get("key_points", [])[:4]]
        notes = section.get("notes", "")

        if slide_type == "cover" or len(key_points) <= 2:
            point_groups = [key_points]
        else:
            point_groups = [key_points[:2], key_points[2:4]]

        for group_index, point_group in enumerate(point_groups, start=1):
            title = section_title if group_index == 1 else _derive_follow_up_title(section_title, group_index)
            slides.append(
                {
                    "id": f"{section_id}_slide_{group_index}",
                    "section_id": section_id,
                    "section_title": section_title,
                    "page_number": page_number,
                    "title": title,
                    "slide_type": slide_type,
                    "visual_type": visual_type,
                    "path_hint": path_hint,
                    "goal": notes or f"说明“{title}”这一页的核心结论",
                    "evidence_type": _derive_evidence_type(visual_type),
                    "key_points": point_group,
                    "content_brief": "；".join(point_group) if point_group else section_title,
                    "speaker_notes": notes or section_title,
                }
            )
            page_number += 1

    return slides


def _derive_follow_up_title(title: str, group_index: int) -> str:
    if "关键" in title:
        return title.replace("关键", "剩余关键", 1)
    if group_index == 2:
        return f"{title}还可以从另一个侧面展开"
    return f"{title}需要进一步补充证据"


def _derive_evidence_type(visual_type: str) -> str:
    mapping = {
        "chart": "data",
        "data": "data",
        "flow": "logic",
        "quote": "quote",
        "cover": "story",
        "illustration": "case",
    }
    return mapping.get(visual_type, "logic")
