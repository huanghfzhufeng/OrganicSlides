"""
Agent 输出评估框架

定义评估指标和评估函数，用于测量演示文稿的质量：
1. 大纲质量 (Outline Quality)
2. 内容质量 (Content Quality)
3. 视觉设计质量 (Visual Design Quality)
"""

from typing import Dict, List, Any, Tuple


class OutlineEvaluator:
    """大纲质量评估器"""

    @staticmethod
    def evaluate(outline: List[Dict]) -> Dict[str, Any]:
        """
        评估大纲质量

        指标：
        - section_count: 章节数量 (目标：6-12)
        - has_cover: 是否有封面
        - has_conclusion: 是否有总结
        - title_quality: 标题质量评分 (0-10)
        - key_points_avg: 平均要点数量
        - type_distribution: 类型分布

        Args:
            outline: 大纲结构列表

        Returns:
            包含评估指标的字典
        """
        if not outline:
            return {
                "score": 0,
                "section_count": 0,
                "has_cover": False,
                "has_conclusion": False,
                "title_quality": 0,
                "key_points_avg": 0,
                "type_distribution": {},
                "issues": ["大纲为空"]
            }

        metrics = {
            "section_count": len(outline),
            "has_cover": any(s.get("type") == "cover" for s in outline),
            "has_conclusion": any(s.get("type") == "conclusion" for s in outline),
            "title_quality": OutlineEvaluator._evaluate_title_quality(outline),
            "key_points_avg": OutlineEvaluator._calculate_key_points_avg(outline),
            "type_distribution": OutlineEvaluator._analyze_type_distribution(outline),
            "issues": []
        }

        # 检查问题
        if not metrics["has_cover"]:
            metrics["issues"].append("缺少封面页")
        if not metrics["has_conclusion"]:
            metrics["issues"].append("缺少总结页")
        if metrics["section_count"] < 6:
            metrics["issues"].append(f"章节数量过少 ({metrics['section_count']}<6)")
        if metrics["section_count"] > 12:
            metrics["issues"].append(f"章节数量过多 ({metrics['section_count']}>12)")

        # 计算综合评分 (0-100)
        metrics["score"] = OutlineEvaluator._calculate_score(metrics)

        return metrics

    @staticmethod
    def _evaluate_title_quality(outline: List[Dict]) -> float:
        """
        评估标题质量

        标准：
        - 标题不为空
        - 标题长度适中 (4-20 字符)
        - 避免过于笼统的标题 (如"介绍"、"内容")
        """
        if not outline:
            return 0.0

        valid_count = 0
        for section in outline:
            title = section.get("title", "").strip()

            # 检查标题是否存在且长度适中
            if 4 <= len(title) <= 20:
                # 避免过于笼统的标题
                generic_titles = {"介绍", "内容", "主要内容", "概述", "说明"}
                if title not in generic_titles:
                    valid_count += 1

        return round((valid_count / len(outline)) * 10, 2) if outline else 0.0

    @staticmethod
    def _calculate_key_points_avg(outline: List[Dict]) -> float:
        """计算平均要点数量"""
        if not outline:
            return 0.0

        total_points = sum(
            len(s.get("key_points", [])) for s in outline
        )
        return round(total_points / len(outline), 2)

    @staticmethod
    def _analyze_type_distribution(outline: List[Dict]) -> Dict[str, int]:
        """分析章节类型分布"""
        distribution = {}
        for section in outline:
            slide_type = section.get("type", "content")
            distribution[slide_type] = distribution.get(slide_type, 0) + 1
        return distribution

    @staticmethod
    def _calculate_score(metrics: Dict) -> float:
        """计算大纲质量综合评分 (0-100)"""
        score = 50  # 基础分

        # 章节数量评分 (最优：6-12)
        section_count = metrics["section_count"]
        if 6 <= section_count <= 12:
            score += 20
        elif 5 <= section_count <= 13:
            score += 10
        elif section_count > 0:
            score += 5

        # 结构完整性 (有封面和总结)
        if metrics["has_cover"]:
            score += 10
        if metrics["has_conclusion"]:
            score += 10

        # 标题质量
        score += metrics["title_quality"]

        # 要点数量合理性
        key_points_avg = metrics["key_points_avg"]
        if 2 <= key_points_avg <= 4:
            score += 5
        elif key_points_avg > 0:
            score += 2

        # 问题扣分
        score -= len(metrics["issues"]) * 3

        return round(min(100, max(0, score)), 2)


class ContentEvaluator:
    """内容质量评估器"""

    @staticmethod
    def evaluate(slides_data: List[Dict]) -> Dict[str, Any]:
        """
        评估内容质量

        指标：
        - slide_count: 幻灯片总数
        - text_length_stats: 文本长度统计
        - bullet_point_stats: 要点统计
        - speaker_notes_coverage: 演讲者备注覆盖率
        - content_variety: 内容多样性

        Args:
            slides_data: 幻灯片内容列表

        Returns:
            包含评估指标的字典
        """
        if not slides_data:
            return {
                "score": 0,
                "slide_count": 0,
                "text_length_stats": {},
                "bullet_point_stats": {},
                "speaker_notes_coverage": 0,
                "content_variety": {},
                "issues": ["没有幻灯片内容"]
            }

        metrics = {
            "slide_count": len(slides_data),
            "text_length_stats": ContentEvaluator._analyze_text_lengths(slides_data),
            "bullet_point_stats": ContentEvaluator._analyze_bullet_points(slides_data),
            "speaker_notes_coverage": ContentEvaluator._calculate_notes_coverage(slides_data),
            "content_variety": ContentEvaluator._analyze_content_variety(slides_data),
            "issues": []
        }

        # 检查问题
        if metrics["speaker_notes_coverage"] < 50:
            metrics["issues"].append("演讲者备注覆盖率过低")

        # 计算综合评分
        metrics["score"] = ContentEvaluator._calculate_score(metrics)

        return metrics

    @staticmethod
    def _analyze_text_lengths(slides_data: List[Dict]) -> Dict[str, Any]:
        """分析文本长度"""
        lengths = []
        for slide in slides_data:
            content = slide.get("content", {})
            main_text = content.get("main_text", "")
            bullet_points = content.get("bullet_points", [])
            supporting_text = content.get("supporting_text", "")

            total_length = (
                len(main_text) +
                sum(len(str(p)) for p in bullet_points) +
                len(supporting_text)
            )
            lengths.append(total_length)

        if not lengths:
            return {"min": 0, "max": 0, "avg": 0, "ideal_ratio": 0}

        min_length = min(lengths)
        max_length = max(lengths)
        avg_length = sum(lengths) / len(lengths)

        # 理想范围：50-200 字符
        ideal_count = sum(1 for l in lengths if 50 <= l <= 200)
        ideal_ratio = round((ideal_count / len(lengths)) * 100, 2)

        return {
            "min": min_length,
            "max": max_length,
            "avg": round(avg_length, 2),
            "ideal_ratio": ideal_ratio
        }

    @staticmethod
    def _analyze_bullet_points(slides_data: List[Dict]) -> Dict[str, Any]:
        """分析要点"""
        bullet_counts = []
        for slide in slides_data:
            content = slide.get("content", {})
            bullet_points = content.get("bullet_points", [])
            bullet_counts.append(len(bullet_points))

        if not bullet_counts:
            return {"min": 0, "max": 0, "avg": 0, "ideal_ratio": 0}

        min_count = min(bullet_counts)
        max_count = max(bullet_counts)
        avg_count = sum(bullet_counts) / len(bullet_counts)

        # 理想范围：2-5 个要点
        ideal_count = sum(1 for c in bullet_counts if 2 <= c <= 5)
        ideal_ratio = round((ideal_count / len(bullet_counts)) * 100, 2)

        return {
            "min": min_count,
            "max": max_count,
            "avg": round(avg_count, 2),
            "ideal_ratio": ideal_ratio
        }

    @staticmethod
    def _calculate_notes_coverage(slides_data: List[Dict]) -> float:
        """计算演讲者备注覆盖率"""
        if not slides_data:
            return 0.0

        slides_with_notes = sum(
            1 for slide in slides_data
            if slide.get("speaker_notes", "").strip()
        )

        return round((slides_with_notes / len(slides_data)) * 100, 2)

    @staticmethod
    def _analyze_content_variety(slides_data: List[Dict]) -> Dict[str, Any]:
        """分析内容多样性"""
        layout_distribution = {}
        visual_needs_stats = {
            "needs_image": 0,
            "needs_chart": 0,
            "neither": 0
        }

        for slide in slides_data:
            # 布局分布
            layout_intent = slide.get("layout_intent", "content")
            layout_distribution[layout_intent] = layout_distribution.get(layout_intent, 0) + 1

            # 视觉需求
            visual_needs = slide.get("visual_needs", {})
            if visual_needs.get("needs_image"):
                visual_needs_stats["needs_image"] += 1
            elif visual_needs.get("needs_chart"):
                visual_needs_stats["needs_chart"] += 1
            else:
                visual_needs_stats["neither"] += 1

        return {
            "layout_distribution": layout_distribution,
            "visual_needs": visual_needs_stats,
            "layout_variety": len(layout_distribution)
        }

    @staticmethod
    def _calculate_score(metrics: Dict) -> float:
        """计算内容质量综合评分 (0-100)"""
        score = 50  # 基础分

        # 幻灯片数量评分 (合理范围：6-12)
        slide_count = metrics["slide_count"]
        if 6 <= slide_count <= 12:
            score += 15
        elif 5 <= slide_count <= 13:
            score += 10
        elif slide_count > 0:
            score += 5

        # 文本长度合理性
        text_stats = metrics["text_length_stats"]
        if text_stats.get("ideal_ratio", 0) > 70:
            score += 15
        elif text_stats.get("ideal_ratio", 0) > 50:
            score += 10
        else:
            score += 5

        # 要点分布合理性
        bullet_stats = metrics["bullet_point_stats"]
        if bullet_stats.get("ideal_ratio", 0) > 70:
            score += 10
        elif bullet_stats.get("ideal_ratio", 0) > 50:
            score += 5

        # 演讲者备注覆盖率
        notes_coverage = metrics["speaker_notes_coverage"]
        if notes_coverage > 80:
            score += 10
        elif notes_coverage > 50:
            score += 5

        # 内容多样性
        content_variety = metrics["content_variety"]
        if content_variety.get("layout_variety", 0) > 3:
            score += 10

        # 视觉需求多样性
        visual_needs = content_variety.get("visual_needs", {})
        if visual_needs.get("needs_image", 0) > 0 or visual_needs.get("needs_chart", 0) > 0:
            score += 5

        # 问题扣分
        score -= len(metrics.get("issues", [])) * 5

        return round(min(100, max(0, score)), 2)


class VisualEvaluator:
    """视觉设计质量评估器"""

    @staticmethod
    def evaluate(slides_data: List[Dict]) -> Dict[str, Any]:
        """
        评估视觉设计质量

        指标：
        - layout_variety: 布局多样性
        - color_usage: 颜色使用情况
        - visual_element_coverage: 视觉元素覆盖率
        - animation_suggestions: 动画建议覆盖率

        Args:
            slides_data: 幻灯片内容列表

        Returns:
            包含评估指标的字典
        """
        if not slides_data:
            return {
                "score": 0,
                "layout_variety": 0,
                "layout_distribution": {},
                "visual_element_coverage": 0,
                "color_usage": {},
                "animation_suggestions": 0,
                "issues": ["没有幻灯片内容"]
            }

        metrics = {
            "layout_variety": VisualEvaluator._calculate_layout_variety(slides_data),
            "layout_distribution": VisualEvaluator._analyze_layout_distribution(slides_data),
            "visual_element_coverage": VisualEvaluator._calculate_visual_coverage(slides_data),
            "color_usage": VisualEvaluator._analyze_color_usage(slides_data),
            "animation_suggestions": VisualEvaluator._calculate_animation_coverage(slides_data),
            "issues": []
        }

        # 检查问题
        if metrics["layout_variety"] < 2:
            metrics["issues"].append("布局多样性不足")

        # 计算综合评分
        metrics["score"] = VisualEvaluator._calculate_score(metrics)

        return metrics

    @staticmethod
    def _calculate_layout_variety(slides_data: List[Dict]) -> int:
        """计算布局多样性（不同布局的数量）"""
        layouts = set()
        for slide in slides_data:
            layout = slide.get("layout_name", slide.get("layout_intent", "content"))
            layouts.add(layout)
        return len(layouts)

    @staticmethod
    def _analyze_layout_distribution(slides_data: List[Dict]) -> Dict[str, int]:
        """分析布局分布"""
        distribution = {}
        for slide in slides_data:
            layout = slide.get("layout_name", slide.get("layout_intent", "content"))
            distribution[layout] = distribution.get(layout, 0) + 1
        return distribution

    @staticmethod
    def _calculate_visual_coverage(slides_data: List[Dict]) -> float:
        """计算视觉元素覆盖率"""
        if not slides_data:
            return 0.0

        slides_with_elements = 0
        for slide in slides_data:
            visual_elements = slide.get("visual_elements", [])
            if visual_elements and len(visual_elements) > 0:
                slides_with_elements += 1

        return round((slides_with_elements / len(slides_data)) * 100, 2)

    @staticmethod
    def _analyze_color_usage(slides_data: List[Dict]) -> Dict[str, Any]:
        """分析颜色使用"""
        colors_used = set()
        slides_with_color_emphasis = 0

        for slide in slides_data:
            # 收集颜色强调
            color_emphasis = slide.get("color_emphasis", [])
            if color_emphasis:
                colors_used.update(color_emphasis)
                slides_with_color_emphasis += 1

        color_emphasis_ratio = (
            round((slides_with_color_emphasis / len(slides_data)) * 100, 2)
            if slides_data else 0
        )

        return {
            "unique_colors": len(colors_used),
            "colors_used": list(colors_used),
            "color_emphasis_ratio": color_emphasis_ratio
        }

    @staticmethod
    def _calculate_animation_coverage(slides_data: List[Dict]) -> float:
        """计算动画建议覆盖率"""
        if not slides_data:
            return 0.0

        slides_with_animation = sum(
            1 for slide in slides_data
            if slide.get("animation_suggestion")
        )

        return round((slides_with_animation / len(slides_data)) * 100, 2)

    @staticmethod
    def _calculate_score(metrics: Dict) -> float:
        """计算视觉设计质量综合评分 (0-100)"""
        score = 50  # 基础分

        # 布局多样性
        layout_variety = metrics["layout_variety"]
        if layout_variety >= 4:
            score += 20
        elif layout_variety >= 3:
            score += 15
        elif layout_variety >= 2:
            score += 10
        else:
            score += 5

        # 视觉元素覆盖率
        visual_coverage = metrics["visual_element_coverage"]
        if visual_coverage > 50:
            score += 15
        elif visual_coverage > 25:
            score += 10
        else:
            score += 5

        # 颜色使用
        color_usage = metrics["color_usage"]
        if color_usage.get("unique_colors", 0) >= 2:
            score += 10

        if color_usage.get("color_emphasis_ratio", 0) > 50:
            score += 5

        # 动画建议覆盖率
        animation_suggestions = metrics["animation_suggestions"]
        if animation_suggestions > 50:
            score += 10
        elif animation_suggestions > 0:
            score += 5

        # 问题扣分
        score -= len(metrics.get("issues", [])) * 5

        return round(min(100, max(0, score)), 2)


class ComprehensiveEvaluator:
    """综合评估器 - 整合所有评估维度"""

    @staticmethod
    def evaluate_full_pipeline(
        outline: List[Dict],
        slides_data: List[Dict],
        theme_name: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        全面评估演示文稿生成的整个流程

        Args:
            outline: 大纲结构
            slides_data: 幻灯片内容
            theme_name: 主题名称

        Returns:
            包含所有评估维度的综合报告
        """
        outline_eval = OutlineEvaluator.evaluate(outline)
        content_eval = ContentEvaluator.evaluate(slides_data)
        visual_eval = VisualEvaluator.evaluate(slides_data)

        # 计算综合评分
        overall_score = round(
            (outline_eval["score"] * 0.3 +
             content_eval["score"] * 0.4 +
             visual_eval["score"] * 0.3),
            2
        )

        return {
            "theme": theme_name,
            "overall_score": overall_score,
            "outline_quality": outline_eval,
            "content_quality": content_eval,
            "visual_quality": visual_eval,
            "summary": ComprehensiveEvaluator._generate_summary(
                overall_score,
                outline_eval,
                content_eval,
                visual_eval
            )
        }

    @staticmethod
    def _generate_summary(
        overall_score: float,
        outline_eval: Dict,
        content_eval: Dict,
        visual_eval: Dict
    ) -> str:
        """生成评估摘要"""
        summary = f"综合评分: {overall_score}/100\n"
        summary += f"- 大纲质量: {outline_eval['score']}/100\n"
        summary += f"- 内容质量: {content_eval['score']}/100\n"
        summary += f"- 视觉质量: {visual_eval['score']}/100\n"

        all_issues = (
            outline_eval.get("issues", []) +
            content_eval.get("issues", []) +
            visual_eval.get("issues", [])
        )

        if all_issues:
            summary += f"\n发现的问题:\n"
            for issue in all_issues:
                summary += f"- {issue}\n"

        return summary
