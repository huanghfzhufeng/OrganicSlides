"""
Evaluation Runner - Execute baseline and post-improvement evaluations

This module provides utilities to run comprehensive evaluations across
the three test themes and generate comparison reports.
"""

from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime

from tests.agent_eval import (
    TEST_THEMES,
    ComprehensiveEvaluator,
    OutlineEvaluator,
    ContentEvaluator,
    VisualEvaluator
)


@dataclass
class EvaluationResult:
    """Container for a single evaluation result"""
    theme_name: str
    timestamp: str
    overall_score: float
    outline_quality: Dict[str, Any]
    content_quality: Dict[str, Any]
    visual_quality: Dict[str, Any]
    summary: str


@dataclass
class ComparisonResult:
    """Container for baseline vs improved comparison"""
    theme_name: str
    baseline_score: float
    improved_score: float
    improvement: float  # positive = better
    improvement_percent: float  # (improvement / baseline) * 100
    baseline_report: EvaluationResult
    improved_report: EvaluationResult


class EvaluationRunner:
    """Execute comprehensive evaluations"""

    @staticmethod
    def evaluate_agent_output(
        outline: List[Dict],
        slides_data: List[Dict],
        theme_name: str
    ) -> EvaluationResult:
        """
        Evaluate a single agent output

        Args:
            outline: Generated outline structure
            slides_data: Generated slides content
            theme_name: Name of the test theme

        Returns:
            EvaluationResult with all metrics
        """
        full_eval = ComprehensiveEvaluator.evaluate_full_pipeline(
            outline=outline,
            slides_data=slides_data,
            theme_name=theme_name
        )

        return EvaluationResult(
            theme_name=theme_name,
            timestamp=datetime.now().isoformat(),
            overall_score=full_eval["overall_score"],
            outline_quality=full_eval["outline_quality"],
            content_quality=full_eval["content_quality"],
            visual_quality=full_eval["visual_quality"],
            summary=full_eval["summary"]
        )

    @staticmethod
    def evaluate_batch(
        results_by_theme: Dict[str, tuple[List[Dict], List[Dict]]]
    ) -> List[EvaluationResult]:
        """
        Evaluate multiple themes

        Args:
            results_by_theme: Dict mapping theme_name -> (outline, slides_data)

        Returns:
            List of EvaluationResults
        """
        evaluations = []
        for theme_name, (outline, slides_data) in results_by_theme.items():
            result = EvaluationRunner.evaluate_agent_output(
                outline=outline,
                slides_data=slides_data,
                theme_name=theme_name
            )
            evaluations.append(result)
        return evaluations

    @staticmethod
    def compare_evaluations(
        baseline_results: List[EvaluationResult],
        improved_results: List[EvaluationResult]
    ) -> List[ComparisonResult]:
        """
        Compare baseline vs improved evaluations

        Args:
            baseline_results: Baseline evaluation results
            improved_results: Improved evaluation results

        Returns:
            List of comparison results
        """
        comparisons = []

        # Create mapping for easier lookup
        baseline_map = {r.theme_name: r for r in baseline_results}
        improved_map = {r.theme_name: r for r in improved_results}

        # Compare each theme
        for theme in TEST_THEMES:
            baseline = baseline_map.get(theme.name)
            improved = improved_map.get(theme.name)

            if baseline and improved:
                improvement = improved.overall_score - baseline.overall_score
                improvement_percent = (improvement / baseline.overall_score * 100) if baseline.overall_score > 0 else 0

                comparison = ComparisonResult(
                    theme_name=theme.name,
                    baseline_score=baseline.overall_score,
                    improved_score=improved.overall_score,
                    improvement=improvement,
                    improvement_percent=round(improvement_percent, 2),
                    baseline_report=baseline,
                    improved_report=improved
                )
                comparisons.append(comparison)

        return comparisons

    @staticmethod
    def generate_comparison_report(
        comparisons: List[ComparisonResult],
        output_path: str = None
    ) -> str:
        """
        Generate a markdown comparison report

        Args:
            comparisons: List of comparison results
            output_path: Optional path to save report

        Returns:
            Markdown report string
        """
        report = "# Agent Prompt Improvement Evaluation Report\n\n"
        report += f"Generated: {datetime.now().isoformat()}\n\n"

        # Summary statistics
        if comparisons:
            avg_improvement = sum(c.improvement for c in comparisons) / len(comparisons)
            avg_improvement_pct = sum(c.improvement_percent for c in comparisons) / len(comparisons)

            report += "## Overall Summary\n\n"
            report += f"- Themes Evaluated: {len(comparisons)}\n"
            report += f"- Average Score Improvement: {avg_improvement:+.2f} points\n"
            report += f"- Average Improvement: {avg_improvement_pct:+.2f}%\n\n"

        # Per-theme results
        report += "## Theme-by-Theme Results\n\n"

        for comparison in comparisons:
            report += f"### {comparison.theme_name}\n\n"
            report += f"| Metric | Baseline | Improved | Change |\n"
            report += f"|--------|----------|----------|--------|\n"
            report += f"| Overall Score | {comparison.baseline_score:.1f}/100 | {comparison.improved_score:.1f}/100 | {comparison.improvement:+.1f} |\n"

            # Breakdown by dimension
            b_outline = comparison.baseline_report.outline_quality["score"]
            i_outline = comparison.improved_report.outline_quality["score"]
            report += f"| Outline Quality | {b_outline:.1f}/100 | {i_outline:.1f}/100 | {i_outline - b_outline:+.1f} |\n"

            b_content = comparison.baseline_report.content_quality["score"]
            i_content = comparison.improved_report.content_quality["score"]
            report += f"| Content Quality | {b_content:.1f}/100 | {i_content:.1f}/100 | {i_content - b_content:+.1f} |\n"

            b_visual = comparison.baseline_report.visual_quality["score"]
            i_visual = comparison.improved_report.visual_quality["score"]
            report += f"| Visual Quality | {b_visual:.1f}/100 | {i_visual:.1f}/100 | {i_visual - b_visual:+.1f} |\n"

            report += "\n"

            # Detailed summary
            if comparison.improvement > 0:
                report += f"✅ **Improvement: {comparison.improvement:+.2f} points ({comparison.improvement_percent:+.1f}%)**\n\n"
            elif comparison.improvement < 0:
                report += f"⚠️ **Regression: {comparison.improvement:.2f} points ({comparison.improvement_percent:.1f}%)**\n\n"
            else:
                report += f"➖ **No Change**\n\n"

            # List any issues found
            improved_issues = comparison.improved_report.outline_quality.get("issues", [])
            if improved_issues:
                report += f"**Remaining Issues:**\n"
                for issue in improved_issues:
                    report += f"- {issue}\n"
                report += "\n"

        # Recommendations
        report += "## Recommendations\n\n"

        # Find themes needing most improvement
        if comparisons:
            lowest_improvement = min(comparisons, key=lambda c: c.improvement)
            if lowest_improvement.improvement < 5:
                report += f"- **{lowest_improvement.theme_name}**: Only {lowest_improvement.improvement:+.1f} point improvement. "
                report += "Consider additional prompt refinement.\n"

            # Find dimensions needing improvement
            dimensions = {
                "outline": [],
                "content": [],
                "visual": []
            }

            for comparison in comparisons:
                b_outline = comparison.baseline_report.outline_quality["score"]
                i_outline = comparison.improved_report.outline_quality["score"]
                if i_outline - b_outline < 5:
                    dimensions["outline"].append(comparison.theme_name)

                b_content = comparison.baseline_report.content_quality["score"]
                i_content = comparison.improved_report.content_quality["score"]
                if i_content - b_content < 5:
                    dimensions["content"].append(comparison.theme_name)

                b_visual = comparison.baseline_report.visual_quality["score"]
                i_visual = comparison.improved_report.visual_quality["score"]
                if i_visual - b_visual < 5:
                    dimensions["visual"].append(comparison.theme_name)

            if dimensions["outline"]:
                report += f"- **Outline Quality**: Focus on {', '.join(dimensions['outline'])}. "
                report += "Consider refining Planner prompts.\n"

            if dimensions["content"]:
                report += f"- **Content Quality**: Focus on {', '.join(dimensions['content'])}. "
                report += "Consider refining Writer prompts.\n"

            if dimensions["visual"]:
                report += f"- **Visual Quality**: Focus on {', '.join(dimensions['visual'])}. "
                report += "Consider refining Visual prompts and Renderer capabilities.\n"

        # Save if output_path provided
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)

        return report

    @staticmethod
    def generate_detailed_report(
        evaluation: EvaluationResult,
        output_path: str = None
    ) -> str:
        """
        Generate a detailed report for a single evaluation

        Args:
            evaluation: EvaluationResult to report on
            output_path: Optional path to save report

        Returns:
            Markdown report string
        """
        report = f"# Detailed Evaluation Report: {evaluation.theme_name}\n\n"
        report += f"Timestamp: {evaluation.timestamp}\n\n"

        # Overall Score
        report += f"## Overall Score: {evaluation.overall_score}/100\n\n"

        if evaluation.overall_score >= 90:
            report += "**Rating: ⭐⭐⭐⭐⭐ Excellent**\n\n"
        elif evaluation.overall_score >= 80:
            report += "**Rating: ⭐⭐⭐⭐ Good**\n\n"
        elif evaluation.overall_score >= 70:
            report += "**Rating: ⭐⭐⭐ Passing**\n\n"
        elif evaluation.overall_score >= 60:
            report += "**Rating: ⭐⭐ Basic**\n\n"
        else:
            report += "**Rating: ⭐ Needs Improvement**\n\n"

        # Outline Quality
        outline = evaluation.outline_quality
        report += f"## Outline Quality: {outline['score']}/100\n\n"
        report += f"- **Sections**: {outline['section_count']} "
        report += "(target: 6-12)\n"
        report += f"- **Has Cover**: {'✅' if outline['has_cover'] else '❌'}\n"
        report += f"- **Has Conclusion**: {'✅' if outline['has_conclusion'] else '❌'}\n"
        report += f"- **Title Quality**: {outline['title_quality']}/10\n"
        report += f"- **Avg Key Points**: {outline['key_points_avg']}\n"
        report += f"- **Type Distribution**: {outline['type_distribution']}\n"

        if outline['issues']:
            report += "\n**Issues:**\n"
            for issue in outline['issues']:
                report += f"- {issue}\n"

        # Content Quality
        content = evaluation.content_quality
        report += f"\n## Content Quality: {content['score']}/100\n\n"
        report += f"- **Slides**: {content['slide_count']} (target: 6-12)\n"

        text_stats = content['text_length_stats']
        report += f"- **Text Length**: min={text_stats.get('min', 0)}, "
        report += f"max={text_stats.get('max', 0)}, "
        report += f"avg={text_stats.get('avg', 0):.0f}\n"
        report += f"- **Ideal Text Ratio**: {text_stats.get('ideal_ratio', 0)}%\n"

        bullet_stats = content['bullet_point_stats']
        report += f"- **Bullet Points**: avg={bullet_stats.get('avg', 0):.1f}), "
        report += f"ideal={bullet_stats.get('ideal_ratio', 0)}%\n"
        report += f"- **Speaker Notes Coverage**: {content['speaker_notes_coverage']}%\n"

        content_variety = content['content_variety']
        report += f"- **Layout Variety**: {content_variety.get('layout_variety', 0)} types\n"

        if content['issues']:
            report += "\n**Issues:**\n"
            for issue in content['issues']:
                report += f"- {issue}\n"

        # Visual Quality
        visual = evaluation.visual_quality
        report += f"\n## Visual Quality: {visual['score']}/100\n\n"
        report += f"- **Layout Variety**: {visual['layout_variety']} types (target: 4+)\n"
        report += f"- **Layout Distribution**: {visual['layout_distribution']}\n"
        report += f"- **Visual Element Coverage**: {visual['visual_element_coverage']}%\n"

        color_usage = visual['color_usage']
        report += f"- **Colors Used**: {color_usage.get('unique_colors', 0)} unique\n"
        report += f"- **Color Emphasis Ratio**: {color_usage.get('color_emphasis_ratio', 0)}%\n"
        report += f"- **Animation Suggestions**: {visual['animation_suggestions']}%\n"

        if visual['issues']:
            report += "\n**Issues:**\n"
            for issue in visual['issues']:
                report += f"- {issue}\n"

        # Summary
        report += f"\n## Summary\n\n{evaluation.summary}\n"

        # Save if output_path provided
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)

        return report
