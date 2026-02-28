"""
Style Recommender — maps user intent text to recommended styles.

Recommendation logic is based on the topic-to-style table from
huashu-slides/references/proven-styles-gallery.md. Pure keyword
matching is used so no LLM call is required at recommendation time.
"""

from __future__ import annotations

import re
from typing import Optional

from styles.registry import StyleDict, get_registry

# ---------------------------------------------------------------------------
# Keyword → topic mapping
# ---------------------------------------------------------------------------
# Each entry: (topic_key, [keywords])
# Keywords are matched case-insensitively anywhere in the intent text.
# Order matters — first match wins for primary assignment.

_TOPIC_KEYWORDS: list[tuple[str, list[str]]] = [
    ("投资路演", ["投资", "融资", "路演", "investor", "pitch", "funding", "vc", "startup"]),
    ("数据报告", ["数据", "报告", "分析", "data", "report", "analytics", "统计", "research"]),
    ("正式商务", ["商务", "business", "汇报", "corporate", "enterprise", "formal", "董事会"]),
    ("行业分析", ["行业", "industry", "市场", "market", "咨询", "consulting", "竞争"]),
    ("产品发布", ["产品", "发布", "product", "launch", "keynote", "发布会", "新品"]),
    ("品牌介绍", ["品牌", "brand", "公司介绍", "company", "介绍", "identity", "logo"]),
    ("教育培训", ["教育", "培训", "training", "课程", "课件", "学习", "education", "teaching", "workshop"]),
    ("技术分享", ["技术", "tech", "architecture", "架构", "开发", "engineering", "algorithm", "算法", "code"]),
    ("年轻受众", ["年轻", "young", "youth", "潮流", "social", "社交", "trendy", "z世代"]),
    ("创意艺术", ["创意", "艺术", "creative", "art", "设计", "design", "广告", "advertising"]),
    ("国风东方", ["国风", "东方", "chinese", "传统", "文化", "heritage", "古典", "oriental"]),
    ("培训课件", ["课件", "ppt模板", "培训材料", "教材", "slides", "内训"]),
    ("内部分享", ["内部", "internal", "team", "团队", "分享", "周报", "复盘", "回顾"]),
]

# ---------------------------------------------------------------------------
# Topic → ordered style IDs (first = strongest recommendation)
# ---------------------------------------------------------------------------

_TOPIC_TO_STYLES: dict[str, list[str]] = {
    "品牌介绍":    ["01-snoopy", "04-neo-pop", "08-ukiyo-e"],
    "教育培训":    ["18-neo-brutalism", "02-manga", "01-snoopy"],
    "技术分享":    ["05-xkcd", "18-neo-brutalism", "03-ligne-claire"],
    "数据报告":    ["p2-fathom", "p1-pentagram", "03-ligne-claire"],
    "年轻受众":    ["04-neo-pop", "17-pixel-art", "11-risograph"],
    "创意艺术":    ["16-collage", "11-risograph", "10-oatmeal"],
    "国风东方":    ["07-dunhuang", "08-ukiyo-e", "09-warm-narrative"],
    "正式商务":    ["p6-nyt-magazine", "p1-pentagram", "p4-build-luxury"],
    "行业分析":    ["p1-pentagram", "p2-fathom", "03-ligne-claire"],
    "培训课件":    ["18-neo-brutalism", "p3-muller-brockmann", "02-manga"],
    "投资路演":    ["p4-build-luxury", "p6-nyt-magazine", "p1-pentagram"],
    "产品发布":    ["06-constructivism", "04-neo-pop", "18-neo-brutalism"],
    "内部分享":    ["18-neo-brutalism", "10-oatmeal", "05-xkcd"],
}

# Default fallback when no topic matches
_DEFAULT_STYLES: list[str] = ["01-snoopy", "18-neo-brutalism", "04-neo-pop"]


class StyleRecommender:
    """
    Returns Top-3 recommended styles for a user intent string.

    Uses keyword matching against the topic table. If no topic matches,
    falls back to a sensible default set.
    """

    def __init__(self) -> None:
        self._registry = get_registry()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend(
        self, user_intent: str, max_results: int = 3
    ) -> list[StyleDict]:
        """
        Return up to *max_results* style dicts ranked by relevance for
        *user_intent*. Never mutates any global state.
        """
        if not user_intent or not user_intent.strip():
            return self._resolve([], _DEFAULT_STYLES, max_results)

        topic = self._detect_topic(user_intent.lower())
        if topic is None:
            return self._resolve([], _DEFAULT_STYLES, max_results)
        preferred = _TOPIC_TO_STYLES.get(topic, [])
        return self._resolve(preferred, _DEFAULT_STYLES, max_results)

    def recommend_ids(
        self, user_intent: str, max_results: int = 3
    ) -> list[str]:
        """Convenience method — returns style IDs only."""
        return [s["id"] for s in self.recommend(user_intent, max_results)]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_topic(text: str) -> Optional[str]:
        """Return the first matching topic key, or None."""
        for topic, keywords in _TOPIC_KEYWORDS:
            for kw in keywords:
                if re.search(re.escape(kw), text, re.IGNORECASE):
                    return topic
        return None

    def _resolve(
        self,
        preferred: list[str],
        fallback: list[str],
        max_results: int,
    ) -> list[StyleDict]:
        """
        Build the final recommendation list.

        - Preferred IDs come first.
        - If fewer than *max_results* are found, fill from *fallback*.
        - Skip IDs that don't exist in the registry.
        """
        seen: set[str] = set()
        result: list[StyleDict] = []

        for style_id in (*preferred, *fallback):
            if len(result) >= max_results:
                break
            if style_id in seen:
                continue
            seen.add(style_id)
            style = self._registry.get_style(style_id)
            if style:
                result.append(style)

        return result
