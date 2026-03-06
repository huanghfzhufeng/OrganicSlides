"""
Agent Evaluation Framework

评估框架用于测量演示文稿生成的基准质量。

模块：
- test_themes: 定义三个测试主题 (学术、商业、公益)
- evaluator: 评估器和指标定义
- evaluation_runner: 执行评估和生成报告的工具
"""

from tests.agent_eval.test_themes import (
    TestTheme,
    ACADEMIC_THEME,
    BUSINESS_THEME,
    PUBLIC_WELFARE_THEME,
    TEST_THEMES,
    get_theme_by_name,
    get_themes_by_category
)

from tests.agent_eval.evaluator import (
    OutlineEvaluator,
    ContentEvaluator,
    VisualEvaluator,
    ComprehensiveEvaluator
)

from tests.agent_eval.evaluation_runner import (
    EvaluationResult,
    ComparisonResult,
    EvaluationRunner
)

__all__ = [
    # Test Themes
    "TestTheme",
    "ACADEMIC_THEME",
    "BUSINESS_THEME",
    "PUBLIC_WELFARE_THEME",
    "TEST_THEMES",
    "get_theme_by_name",
    "get_themes_by_category",
    # Evaluators
    "OutlineEvaluator",
    "ContentEvaluator",
    "VisualEvaluator",
    "ComprehensiveEvaluator",
    # Evaluation Runner
    "EvaluationResult",
    "ComparisonResult",
    "EvaluationRunner"
]
