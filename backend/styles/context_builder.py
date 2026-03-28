"""
Build richer style context packets for Planner / Writer / Visual.

The current system already stores useful style metadata in JSON, but most agents
only receive the style name plus a short base prompt excerpt. This module turns
the local style config and huashu reference docs into a compact, structured
packet so generation can stay closer to the intended design language.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
import re

from skills.runtime import get_skill_runtime_packet

_ROOT_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_REFERENCE_FILES = (
    "proven-styles-gallery.md",
    "prompt-templates.md",
    "design-principles.md",
    "design-movements.md",
    "proven-styles-snoopy.md",
)

_STYLE_KEYWORD_HINTS: dict[str, tuple[str, ...]] = {
    "01-snoopy": ("snoopy", "peanuts", "warm comic", "温暖漫画", "schulz"),
    "02-manga": ("manga", "学习漫画", "educational manga"),
    "03-ligne-claire": ("ligne claire", "清线", "clear line"),
    "04-neo-pop": ("neo-pop", "新波普", "magazine"),
    "05-xkcd": ("xkcd", "白板手绘", "whiteboard"),
    "06-constructivism": ("constructivism", "构成主义"),
    "07-dunhuang": ("dunhuang", "敦煌"),
    "08-ukiyo-e": ("ukiyo", "浮世绘"),
    "09-warm-narrative": ("warm narrative", "温暖叙事"),
    "10-oatmeal": ("oatmeal", "信息图漫画"),
    "11-risograph": ("risograph", "孔版印刷"),
    "12-isometric": ("isometric", "等轴测"),
    "13-bauhaus": ("bauhaus", "包豪斯"),
    "14-blueprint": ("blueprint", "工程蓝图"),
    "15-vintage-ad": ("vintage ad", "复古广告"),
    "16-collage": ("collage", "达达拼贴"),
    "17-pixel-art": ("pixel art", "像素画"),
    "18-neo-brutalism": ("neo-brutalism", "新粗野主义"),
    "p1-pentagram": ("pentagram",),
    "p2-fathom": ("fathom", "data narrative"),
    "p3-muller-brockmann": ("müller-brockmann", "muller-brockmann", "grid"),
    "p4-build-luxury": ("build luxury", "luxury minimal"),
    "p5-takram": ("takram",),
    "p6-nyt-magazine": ("nyt", "new york times", "editorial", "magazine"),
}


def build_style_packet(
    style_id: str,
    style_config: dict,
    user_intent: str = "",
    *,
    max_reference_snippets: int = 3,
) -> str:
    """Create a compact but high-signal style packet for prompt injection."""
    if not style_config:
        return "未指定风格（系统将以默认风格生成）"

    name_zh = style_config.get("name_zh", "")
    name_en = style_config.get("name_en", "")
    description = style_config.get("description", "")
    tier = style_config.get("tier", "")
    render_paths = style_config.get("render_paths", ["path_a"])
    use_cases = style_config.get("use_cases", [])
    colors = style_config.get("colors", {}) or {}
    typography = style_config.get("typography", {}) or {}
    principles = style_config.get("key_principles", []) or []
    path_note = style_config.get("path_note", "")
    philosophy = style_config.get("philosophy", "")
    base_prompt = style_config.get("base_style_prompt", "") or ""
    sample_image_path = style_config.get("sample_image_path", "") or ""

    lines = [
        f"风格ID：{style_id or style_config.get('id', '')}",
        f"风格名称：{name_zh} / {name_en}".strip(" /"),
        f"风格层级：{tier}",
        f"推荐渲染路径：{', '.join(render_paths)}",
    ]
    if description:
        lines.append(f"风格概述：{description}")
    if use_cases:
        lines.append(f"推荐场景：{', '.join(use_cases[:6])}")
    if path_note:
        lines.append(f"路径备注：{path_note}")
    if philosophy:
        lines.append(f"设计哲学：{philosophy}")
    if principles:
        lines.append("关键原则：")
        lines.extend(f"- {item}" for item in principles[:6])
    if colors:
        lines.append(
            "色彩系统："
            + ", ".join(f"{key}={value}" for key, value in colors.items() if value)
        )
    if typography:
        lines.append(
            "字体系统："
            + ", ".join(f"{key}={value}" for key, value in typography.items() if value)
        )
    if sample_image_path:
        lines.append(f"样例图：{sample_image_path}")
    if base_prompt:
        lines.append(f"基础风格提示词：{_truncate(base_prompt, 420)}")

    reference_snippets = _select_reference_snippets(
        style_id=style_id,
        style_config=style_config,
        user_intent=user_intent,
        limit=max_reference_snippets,
    )
    if reference_snippets:
        lines.append("参考知识摘录：")
        for item in reference_snippets:
            lines.append(f"[{item['source']}] {item['snippet']}")

    return "\n".join(lines)


def _select_reference_snippets(
    *,
    style_id: str,
    style_config: dict,
    user_intent: str,
    limit: int,
) -> list[dict[str, str]]:
    skill_packet = get_skill_runtime_packet()
    references_dir = Path(skill_packet.get("references_dir", ""))
    reference_files = tuple(skill_packet.get("reference_files", [])) or _DEFAULT_REFERENCE_FILES

    if not references_dir.exists():
        return []

    keywords = _collect_keywords(style_id, style_config, user_intent)
    if not keywords:
        return []

    snippets: list[dict[str, str | float]] = []
    for filename in reference_files:
        path = references_dir / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in _extract_candidate_snippets(text):
            score = _score_snippet(snippet, keywords)
            if score <= 0:
                continue
            snippets.append(
                {
                    "source": filename,
                    "snippet": _truncate(_clean_snippet(snippet), 260),
                    "score": score,
                }
            )

    snippets.sort(key=lambda item: item["score"], reverse=True)
    deduped: list[dict[str, str]] = []
    seen = set()
    for item in snippets:
        signature = item["snippet"]
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append({"source": str(item["source"]), "snippet": str(item["snippet"])})
        if len(deduped) >= limit:
            break
    return deduped


def _collect_keywords(style_id: str, style_config: dict, user_intent: str) -> set[str]:
    keywords: set[str] = set()

    for value in (
        style_id,
        style_config.get("name_zh", ""),
        style_config.get("name_en", ""),
        style_config.get("description", ""),
        user_intent,
    ):
        keywords.update(_tokenize_text(str(value)))

    for item in style_config.get("use_cases", []) or []:
        keywords.update(_tokenize_text(str(item)))

    for item in _STYLE_KEYWORD_HINTS.get(style_id, ()):
        keywords.update(_tokenize_text(item))

    return {token for token in keywords if len(token) >= 2}


def _extract_candidate_snippets(text: str) -> Iterable[str]:
    for section in re.split(r"\n(?=##+\s)", text):
        normalized = section.strip()
        if len(normalized) < 40:
            continue
        yield normalized


def _score_snippet(snippet: str, keywords: set[str]) -> float:
    lowered = snippet.lower()
    score = 0.0
    for keyword in keywords:
        if keyword in lowered:
            if len(keyword) >= 5:
                score += 1.5
            else:
                score += 0.7
    if "path a" in lowered or "path b" in lowered:
        score += 0.4
    if "核心" in snippet or "关键" in snippet:
        score += 0.4
    return score


def _tokenize_text(text: str) -> set[str]:
    lowered = text.lower().strip()
    if not lowered:
        return set()

    latin_tokens = set(re.findall(r"[a-z0-9][a-z0-9\-+_.]{1,}", lowered))
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)

    tokens = set(latin_tokens)
    for chunk in chinese_chunks:
        tokens.add(chunk)
        if len(chunk) < 4:
            continue
        ngram_sizes = [2, 3]
        if len(chunk) >= 8:
            ngram_sizes.append(4)
        for size in ngram_sizes:
            for idx in range(0, len(chunk) - size + 1):
                tokens.add(chunk[idx: idx + size])

    return tokens


def _clean_snippet(snippet: str) -> str:
    cleaned = re.sub(r"\s+", " ", snippet).strip()
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    return cleaned


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
