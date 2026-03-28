"""Runtime loader for local project skills."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SKILL_ID = "huashu-slides"
_REFERENCE_DESCRIPTIONS = {
    "proven-styles-gallery.md": "风格画廊",
    "prompt-templates.md": "提示词模板",
    "design-movements.md": "设计运动参考",
    "design-principles.md": "设计原则",
    "proven-styles-snoopy.md": "Snoopy 风格指南",
}
_MODE_KEY_MAP = {
    "full auto": "full_auto",
    "guided": "guided",
    "collaborative": "collaborative",
}


def list_skill_runtimes() -> list[dict[str, Any]]:
    """List local project skills with light metadata."""
    runtimes: list[dict[str, Any]] = []
    for skill_file in sorted(_PROJECT_ROOT.glob("*/SKILL.md")):
        skill_id = skill_file.parent.name
        packet = get_skill_runtime_packet(skill_id)
        runtimes.append(
            {
                "skill_id": packet["skill_id"],
                "name": packet["name"],
                "description": packet["description"],
                "default_collaboration_mode": packet["default_collaboration_mode"],
                "default_render_path": packet["default_render_path"],
            }
        )
    return runtimes


@lru_cache(maxsize=8)
def get_skill_runtime_packet(
    skill_id: str = _DEFAULT_SKILL_ID,
    collaboration_mode: str | None = None,
) -> dict[str, Any]:
    """Load and normalize a local skill into a runtime packet."""
    skill_root = _PROJECT_ROOT / skill_id
    skill_file = skill_root / "SKILL.md"
    if not skill_file.exists():
        raise ValueError(f"Unknown skill_id: {skill_id}")

    markdown = skill_file.read_text(encoding="utf-8")
    front_matter = _parse_front_matter(markdown)
    philosophy = _extract_design_philosophy(markdown)
    collaboration_modes = _parse_collaboration_modes(markdown)
    render_paths = _parse_render_paths(markdown)
    runtime_steps = _parse_runtime_steps(markdown)
    reference_files = _discover_reference_files(skill_root)
    default_mode = next(
        (mode["key"] for mode in collaboration_modes if mode.get("is_default")),
        "guided",
    )
    chosen_mode = _normalize_collaboration_mode(collaboration_mode or default_mode)
    if chosen_mode not in {mode["key"] for mode in collaboration_modes}:
        chosen_mode = default_mode

    checkpoint_names = [cp["key"] for step in runtime_steps for cp in step.get("checkpoints", [])]

    return {
        "skill_id": skill_id,
        "name": front_matter.get("name", skill_id),
        "description": front_matter.get("description", ""),
        "design_philosophy": philosophy,
        "skill_file": str(skill_file.resolve()),
        "root_dir": str(skill_root.resolve()),
        "scripts_dir": str((skill_root / "scripts").resolve()),
        "style_samples_dir": str((skill_root / "assets" / "style-samples").resolve()),
        "references_dir": str((skill_root / "references").resolve()),
        "reference_files": reference_files,
        "supported_collaboration_modes": collaboration_modes,
        "default_collaboration_mode": default_mode,
        "collaboration_mode": chosen_mode,
        "render_paths": render_paths,
        "default_render_path": next(
            (path["key"] for path in render_paths if path.get("is_default")),
            "path_a",
        ),
        "runtime_steps": runtime_steps,
        "checkpoint_keys": checkpoint_names,
    }


def build_skill_prompt_packet(skill_packet: dict[str, Any] | None) -> str:
    """Build a compact prompt-ready summary from the runtime packet."""
    if not skill_packet:
        return "未加载 SkillRuntime，按系统默认策略执行。"

    mode = next(
        (
            item
            for item in skill_packet.get("supported_collaboration_modes", [])
            if item.get("key") == skill_packet.get("collaboration_mode")
        ),
        None,
    )
    default_path = next(
        (
            item
            for item in skill_packet.get("render_paths", [])
            if item.get("key") == skill_packet.get("default_render_path")
        ),
        None,
    )
    checkpoints: list[str] = []
    for step in skill_packet.get("runtime_steps", []):
        for checkpoint in step.get("checkpoints", []):
            checkpoints.append(checkpoint["label"])

    lines = [
        f"运行 Skill：{skill_packet.get('name')} ({skill_packet.get('skill_id')})",
        f"设计哲学：{skill_packet.get('design_philosophy') or 'Context, not control'}",
    ]
    if mode:
        lines.append(
            f"协作模式：{mode['label']}；适用={mode['fit']}；检查点={mode['checkpoints']}"
        )
    if default_path:
        lines.append(
            f"默认制作路径：{default_path['label']}；优势={default_path['advantage']}；适合={default_path['best_for']}"
        )

    steps = skill_packet.get("runtime_steps", [])
    if steps:
        lines.append("技能运行步骤：")
        lines.extend(
            f"- Step {step['number']} {step['title']} -> 当前系统映射: {', '.join(step['mapped_stages'])}"
            for step in steps[:5]
        )
    if checkpoints:
        lines.append("关键检查点：" + "；".join(checkpoints[:5]))
    if skill_packet.get("reference_files"):
        lines.append("本地参考：" + ", ".join(skill_packet["reference_files"][:5]))

    return "\n".join(lines)


def _parse_front_matter(markdown: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", markdown, flags=re.S)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def _extract_design_philosophy(markdown: str) -> str:
    match = re.search(r"\*\*设计哲学：(.+?)\*\*", markdown)
    if match:
        return match.group(1).strip()
    return "Context, not control。理解目标和风格感觉，自主做出设计决策。"


def _parse_collaboration_modes(markdown: str) -> list[dict[str, Any]]:
    block = _extract_subsection(markdown, "协作模式")
    rows = _parse_markdown_table(block)
    modes: list[dict[str, Any]] = []
    for row in rows:
        raw_label = row.get("模式", "")
        label = re.sub(r"\*+", "", raw_label).strip()
        is_default = "默认" in label
        normalized_label = re.sub(r"（.*?）", "", label).strip()
        key = _normalize_collaboration_mode(normalized_label)
        modes.append(
            {
                "key": key,
                "label": normalized_label,
                "fit": row.get("适合", ""),
                "checkpoints": row.get("检查点", ""),
                "is_default": is_default or key == "guided",
            }
        )
    return modes or [
        {"key": "guided", "label": "Guided", "fit": "把控方向，不管细节", "checkpoints": "大纲 / 风格选定 / 组装前", "is_default": True}
    ]


def _parse_render_paths(markdown: str) -> list[dict[str, Any]]:
    block = _extract_subsection(markdown, "制作路径")
    rows = _parse_markdown_table(block)
    paths: list[dict[str, Any]] = []
    for row in rows:
        label_a = re.sub(r"\*+", "", row.get("", "")).strip()
        if not label_a:
            # The first table header cell is empty; values live in the first two path columns.
            continue
    path_a_match = re.search(r"\*\*Path A：(.+?)\*\*（默认）", block)
    path_b_match = re.search(r"\*\*Path B：(.+?)\*\*", block)
    paths.append(
        {
            "key": "path_a",
            "label": f"Path A：{path_a_match.group(1).strip()}" if path_a_match else "Path A：可编辑HTML",
            "advantage": _extract_row_cell(block, "优势", 1),
            "best_for": _extract_row_cell(block, "适合", 1),
            "notes": _extract_row_cell(block, "注意", 1),
            "is_default": True,
        }
    )
    paths.append(
        {
            "key": "path_b",
            "label": f"Path B：{path_b_match.group(1).strip()}" if path_b_match else "Path B：全AI视觉",
            "advantage": _extract_row_cell(block, "优势", 2),
            "best_for": _extract_row_cell(block, "适合", 2),
            "notes": _extract_row_cell(block, "注意", 2),
            "is_default": False,
        }
    )
    return paths


def _parse_runtime_steps(markdown: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for match in re.finditer(r"^## Step (\d+): (.+?)\n(.*?)(?=^## Step \d+:|\Z)", markdown, flags=re.M | re.S):
        number = int(match.group(1))
        title = match.group(2).strip()
        body = match.group(3)
        mapped_stages = _map_runtime_stages(number, title)
        checkpoints = _parse_checkpoints(body, number)
        steps.append(
            {
                "number": number,
                "title": title,
                "mapped_stages": mapped_stages,
                "checkpoints": checkpoints,
            }
        )
    return steps


def _parse_checkpoints(body: str, step_number: int) -> list[dict[str, str]]:
    matches = re.findall(r"\*\*Checkpoint（(.+?)）：\*\*\s*(.+)", body)
    checkpoints: list[dict[str, str]] = []
    for audiences, description in matches:
        checkpoints.append(
            {
                "key": _checkpoint_key_for_step(step_number),
                "label": description.strip(),
                "audiences": audiences.strip(),
            }
        )
    return checkpoints


def _checkpoint_key_for_step(step_number: int) -> str:
    return {
        1: "outline_and_blueprint_approval",
        2: "style_selection",
        4: "assembly_review",
        5: "final_preview",
    }.get(step_number, f"step_{step_number}_checkpoint")


def _map_runtime_stages(step_number: int, title: str) -> list[str]:
    lowered = title.lower()
    if step_number == 1 or "内容梳理" in title:
        return ["research", "outline", "blueprint"]
    if step_number == 2 or "风格选择" in title:
        return ["style"]
    if step_number == 3 or "构建" in title:
        return ["writer", "visual", "render_preparation"]
    if step_number == 4 or "组装" in title:
        return ["renderer"]
    if step_number == 5 or "收尾" in title or "finish" in lowered:
        return ["preview", "download"]
    return [f"step_{step_number}"]


def _discover_reference_files(skill_root: Path) -> list[str]:
    references_dir = skill_root / "references"
    if not references_dir.exists():
        return []
    return [path.name for path in sorted(references_dir.glob("*.md"))]


def _extract_subsection(markdown: str, title: str) -> str:
    pattern = rf"^### {re.escape(title)}\n(.*?)(?=^### |\Z)"
    match = re.search(pattern, markdown, flags=re.M | re.S)
    return match.group(1) if match else ""


def _parse_markdown_table(block: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []
    headers = [_clean_table_cell(cell) for cell in lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        if set(line.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
            continue
        cells = [_clean_table_cell(cell) for cell in line.strip("|").split("|")]
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append(dict(zip(headers, cells)))
    return rows


def _clean_table_cell(cell: str) -> str:
    cleaned = cell.replace("**", "").replace("`", "").strip()
    return re.sub(r"\s+", " ", cleaned)


def _extract_row_cell(block: str, row_name: str, cell_index: int) -> str:
    for line in block.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [_clean_table_cell(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) <= cell_index:
            continue
        if cells[0] == row_name:
            return cells[cell_index]
    return ""


def _normalize_collaboration_mode(label: str) -> str:
    lowered = label.lower().strip()
    lowered = re.sub(r"[（）()]", "", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return _MODE_KEY_MAP.get(lowered, lowered.replace(" ", "_") or "guided")
