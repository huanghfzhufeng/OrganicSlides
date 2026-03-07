"""Assemble StylePacket context from style JSON, references, constraints, and assets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_ROOT.parent
_REFERENCE_ROOT = _PROJECT_ROOT / "huashu-slides" / "references"

_REFERENCE_FILES = {
    "gallery": "proven-styles-gallery.md",
    "prompt_templates": "prompt-templates.md",
    "design_movement": "design-movements.md",
    "design_principles": "design-principles.md",
    "snoopy": "proven-styles-snoopy.md",
}

_STYLE_KEYWORDS: dict[str, list[str]] = {
    "01-snoopy": ["Snoopy温暖漫画", "Warm Comic Strip", "Snoopy"],
    "02-manga": ["學習漫画", "Manga", "Manga Educational"],
    "03-ligne-claire": ["Ligne Claire", "清线漫画"],
    "04-neo-pop": ["Neo-Pop", "新波普", "孟菲斯", "De Stijl"],
    "05-xkcd": ["xkcd", "白板手绘"],
    "06-constructivism": ["苏联构成主义", "Constructivism", "俄国构成主义"],
    "07-dunhuang": ["敦煌壁画", "Dunhuang"],
    "08-ukiyo-e": ["浮世绘", "Ukiyo-e"],
    "09-warm-narrative": ["温暖叙事", "Warm Narrative"],
    "10-oatmeal": ["The Oatmeal", "信息图漫画"],
    "11-risograph": ["Risograph", "孔版印刷"],
    "12-isometric": ["Isometric", "等轴测"],
    "13-bauhaus": ["Bauhaus", "包豪斯", "Swiss"],
    "14-blueprint": ["Blueprint", "工程蓝图"],
    "15-vintage-ad": ["Vintage Ad", "复古广告"],
    "16-collage": ["Collage", "达达拼贴", "Sagmeister"],
    "17-pixel-art": ["Pixel Art", "像素画"],
    "18-neo-brutalism": ["Neo-Brutalism", "新粗野主义"],
    "p1-pentagram": ["Pentagram Editorial", "Pentagram"],
    "p2-fathom": ["Fathom Data Narrative", "Fathom"],
    "p3-muller-brockmann": ["Müller-Brockmann", "Muller-Brockmann", "Swiss Style"],
    "p4-build-luxury": ["Build Luxury Minimal", "Luxury Minimal"],
    "p5-takram": ["Takram Speculative", "Takram"],
    "p6-nyt-magazine": ["NYT Magazine Editorial", "纽约时报编辑风", "NYT"],
}

_PATH_B_FORBIDDEN_TERMS = [
    "左",
    "右",
    "上",
    "下",
    "居中",
    "background-color",
    "font-size",
    "position",
]


def assemble_style_packet_context(style_config: dict[str, Any]) -> dict[str, Any]:
    """Build the enriched StylePacket context from tracked reference materials."""
    style_id = str(
        style_config.get("style_id")
        or style_config.get("id")
        or style_config.get("style")
        or "organic"
    )
    keywords = _keywords_for_style(style_id, style_config)
    references = _load_reference_texts()

    gallery_excerpt = _find_best_section(references["gallery"], keywords)
    movement_excerpt = _find_best_section(references["design_movement"], keywords)
    design_principles_excerpt = _combine_sections(
        references["design_principles"],
        [
            "Ten Evidence-Based Rules",
            "Assertion-Evidence Framework",
            "Information Density",
        ],
    )

    extra_sections = []
    if style_id == "01-snoopy":
        extra_sections.append(references["snoopy"].strip())

    prompt_constraints = _build_prompt_constraints(references["prompt_templates"])
    reference_sources = [
        f"huashu-slides/references/{_REFERENCE_FILES['gallery']}",
        f"huashu-slides/references/{_REFERENCE_FILES['design_movement']}",
        f"huashu-slides/references/{_REFERENCE_FILES['design_principles']}",
        f"huashu-slides/references/{_REFERENCE_FILES['prompt_templates']}",
    ]
    if style_id == "01-snoopy":
        reference_sources.append(f"huashu-slides/references/{_REFERENCE_FILES['snoopy']}")

    reference_summary = "\n\n".join(
        section
        for section in [gallery_excerpt, movement_excerpt, *extra_sections]
        if section
    )
    sample_asset_path = _resolve_sample_asset_path(style_config)

    return {
        "sample_asset_path": sample_asset_path,
        "sample_asset_exists": bool(sample_asset_path),
        "reference_sources": reference_sources,
        "reference_summary": reference_summary,
        "gallery_excerpt": gallery_excerpt,
        "movement_excerpt": movement_excerpt,
        "design_principles_excerpt": design_principles_excerpt,
        "prompt_constraints": prompt_constraints,
    }


def _load_reference_texts() -> dict[str, str]:
    return {
        key: (_REFERENCE_ROOT / filename).read_text(encoding="utf-8")
        for key, filename in _REFERENCE_FILES.items()
    }


def _keywords_for_style(style_id: str, style_config: dict[str, Any]) -> list[str]:
    keywords = list(_STYLE_KEYWORDS.get(style_id, []))
    for value in (
        style_config.get("name_zh"),
        style_config.get("name_en"),
        style_config.get("description"),
    ):
        text = _clean_text(value)
        if text:
            keywords.append(text)
    return list(dict.fromkeys(keywords))


def _find_best_section(markdown: str, keywords: list[str]) -> str:
    for keyword in keywords:
        section = _extract_section(markdown, keyword)
        if section:
            return section
    return ""


def _combine_sections(markdown: str, keywords: list[str]) -> str:
    sections = []
    for keyword in keywords:
        section = _extract_section(markdown, keyword)
        if section:
            sections.append(section)
    return "\n\n".join(sections)


def _extract_section(markdown: str, keyword: str) -> str:
    if not keyword:
        return ""

    headings = list(_heading_matches(markdown))
    lowered_keyword = keyword.lower()
    for index, heading in enumerate(headings):
        if lowered_keyword not in heading["title"].lower():
            continue

        start = heading["start"]
        end = len(markdown)
        for next_heading in headings[index + 1 :]:
            if next_heading["level"] <= heading["level"]:
                end = next_heading["start"]
                break
        section = markdown[start:end].strip()
        return _trim_section(section)
    return ""


def _heading_matches(markdown: str):
    pattern = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)
    for match in pattern.finditer(markdown):
        yield {
            "start": match.start(),
            "level": len(match.group(1)),
            "title": match.group(2).strip(),
        }


def _build_prompt_constraints(prompt_templates: str) -> dict[str, Any]:
    path_a_section = _extract_section(prompt_templates, "Path A HTML 生成规范")
    path_b_section = _extract_section(prompt_templates, "Slide Image Generation Prompts")
    base_style_pattern = _extract_section(prompt_templates, "Base Style Prompt Pattern")

    path_a_rules = re.findall(r"\*\*规则 \d+：(.+?)\*\*", path_a_section)

    return {
        "path_a_rules": path_a_rules,
        "path_a_excerpt": path_a_section,
        "path_b_template_excerpt": base_style_pattern or path_b_section,
        "path_b_required_sections": [
            "visual_reference",
            "base_style",
            "design_intent",
            "text_to_render",
            "visual_narrative",
        ],
        "path_b_forbidden_terms": _PATH_B_FORBIDDEN_TERMS,
    }


def _resolve_sample_asset_path(style_config: dict[str, Any]) -> str:
    sample_image_path = str(style_config.get("sample_image_path", "")).strip()
    if not sample_image_path:
        return ""

    relative = sample_image_path.lstrip("/")
    candidate = _BACKEND_ROOT / relative
    if candidate.exists():
        return str(candidate)
    return ""


def _trim_section(section: str, max_chars: int = 1800) -> str:
    compact = re.sub(r"\n{3,}", "\n\n", section).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "..."


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
