# Agent Evaluation Framework

This directory contains the evaluation framework for measuring and comparing OrganicSlides agent output quality.

## Overview

The evaluation framework provides comprehensive metrics for three dimensions of presentation quality:

1. **Outline Quality** (30% weight)
   - Section count, structure completeness
   - Title quality and clarity
   - Key point distribution
   - Content type variety

2. **Content Quality** (40% weight)
   - Text length appropriateness
   - Bullet point structure and count
   - Speaker notes coverage
   - Content type variety

3. **Visual Quality** (30% weight)
   - Layout variety and appropriateness
   - Visual element usage
   - Color scheme consistency
   - Animation suggestions

## Files

### Core Evaluation Code

- **`test_themes.py`** - Three standardized test themes
  - `ACADEMIC_THEME`: "AI人工智能在医疗领域的应用"
  - `BUSINESS_THEME`: "新能源汽车市场分析与投资策略"
  - `PUBLIC_WELFARE_THEME`: "校园心理健康关爱行动"
  - Utility functions: `get_theme_by_name()`, `get_themes_by_category()`

- **`evaluator.py`** - Evaluation implementation
  - `OutlineEvaluator`: Evaluates outline structure and quality
  - `ContentEvaluator`: Evaluates content quality metrics
  - `VisualEvaluator`: Evaluates visual design metrics
  - `ComprehensiveEvaluator`: Combines all three evaluators with weighted scoring

- **`evaluation_runner.py`** - Execution utilities
  - `EvaluationRunner.evaluate_agent_output()`: Single evaluation
  - `EvaluationRunner.evaluate_batch()`: Multiple themes
  - `EvaluationRunner.compare_evaluations()`: Baseline vs improved
  - `EvaluationRunner.generate_comparison_report()`: Auto-generate markdown reports
  - `EvaluationRunner.generate_detailed_report()`: Detailed single-theme report

- **`__init__.py`** - Framework exports

### Documentation

- **`comparison_template.md`** - Template for baseline vs improved reports
- **`README.md`** - This file

## Usage

### Basic Evaluation

```python
from tests.agent_eval import ComprehensiveEvaluator, TEST_THEMES

# Evaluate a single agent output
result = ComprehensiveEvaluator.evaluate_full_pipeline(
    outline=state["outline"],
    slides_data=state["slides_data"],
    theme_name=TEST_THEMES[0].name
)

print(f"Overall Score: {result['overall_score']}/100")
print(result['summary'])
```

### Batch Evaluation

```python
from tests.agent_eval import EvaluationRunner, TEST_THEMES

# Prepare results from all three themes
results_by_theme = {
    TEST_THEMES[0].name: (outline1, slides_data1),
    TEST_THEMES[1].name: (outline2, slides_data2),
    TEST_THEMES[2].name: (outline3, slides_data3),
}

# Run batch evaluation
evaluations = EvaluationRunner.evaluate_batch(results_by_theme)

for eval in evaluations:
    print(f"{eval.theme_name}: {eval.overall_score}/100")
```

### Comparison Analysis

```python
from tests.agent_eval import EvaluationRunner

# Compare baseline vs improved
comparisons = EvaluationRunner.compare_evaluations(
    baseline_results=baseline_evals,
    improved_results=improved_evals
)

# Generate comparison report
report = EvaluationRunner.generate_comparison_report(
    comparisons,
    output_path="reports/comparison_report.md"
)
```

### Individual Reports

```python
from tests.agent_eval import EvaluationRunner

# Generate detailed report for single evaluation
detailed_report = EvaluationRunner.generate_detailed_report(
    evaluation=eval_result,
    output_path=f"reports/{eval_result.theme_name}_detailed.md"
)
```

## Metrics Reference

### Outline Quality Metrics

| Metric | Min | Target | Max | Notes |
|--------|-----|--------|-----|-------|
| section_count | 2 | 6-12 | 20 | Number of outline sections |
| title_quality | 0 | 7-10 | 10 | Based on clarity and specificity |
| key_points_avg | 0 | 2-4 | 10+ | Average points per section |
| type_distribution | 1 | 3+ | - | Number of different section types |

**Scoring Formula**:
```
Base: 50 points
+ 20 if section count in 6-12 range
+ 10 for having cover page
+ 10 for having conclusion page
+ title_quality score (0-10)
+ 5 if average key points in 2-4 range
- 3 points per issue found
= Final score (0-100)
```

### Content Quality Metrics

| Metric | Min | Target | Max | Notes |
|--------|-----|--------|-----|-------|
| slide_count | 1 | 6-12 | - | Total number of slides |
| text_length_avg | 0 | 50-200 | - | Characters per slide |
| bullet_point_avg | 0 | 2-5 | - | Bullet points per slide |
| speaker_notes_coverage | 0% | >80% | 100% | % of slides with notes |
| layout_variety | 1 | 3+ | - | Number of different layouts |

**Scoring Formula**:
```
Base: 50 points
+ 15 if slide count in 6-12 range
+ 15 if >70% of slides have ideal text length
+ 10 if >70% of slides have ideal bullet counts
+ 10 if speaker notes coverage >80%
+ 10 if layout variety ≥3
+ 5 if visual needs detected
- 5 points per issue found
= Final score (0-100)
```

### Visual Quality Metrics

| Metric | Min | Target | Max | Notes |
|--------|-----|--------|-----|-------|
| layout_variety | 1 | 4+ | - | Number of different layouts |
| visual_element_coverage | 0% | >50% | 100% | % of slides with elements |
| color_usage | 1 | 2+ | - | Unique colors used |
| animation_suggestions | 0% | >50% | 100% | % of slides with animations |

**Scoring Formula**:
```
Base: 50 points
+ 20 if layout variety ≥4
+ 15 if visual element coverage >50%
+ 10 if ≥2 unique colors used
+ 5 if color emphasis >50%
+ 10 if animation suggestions >50%
- 5 points per issue found
= Final score (0-100)
```

### Overall Score

```
Overall Score = (Outline × 0.3) + (Content × 0.4) + (Visual × 0.3)
```

**Rating Scale**:
- ⭐⭐⭐⭐⭐: 90-100 (Excellent)
- ⭐⭐⭐⭐: 80-89 (Good)
- ⭐⭐⭐: 70-79 (Passing)
- ⭐⭐: 60-69 (Basic)
- ⭐: <60 (Needs Improvement)

## Evaluation Workflow

### Phase 1: Baseline (Task #6) ✅ COMPLETED
1. ✅ Analyze all agent code and prompts
2. ✅ Define evaluation metrics
3. ✅ Create test themes
4. ✅ Document baseline expectations

**Output**: `docs/agent-baseline-report.md`
**Baseline Score**: 55-65/100 (⭐⭐⭐)

### Phase 2: Prompt Improvement (Task #7) IN PROGRESS
1. ⏳ Refactor Planner, Writer, Visual prompts
2. ⏳ Integrate huashu-slides knowledge
3. ⏳ Test improved prompts

**Expected Target**: 70+/100 (⭐⭐⭐)

### Phase 3: Evaluation & Reporting (Task #12) PENDING
1. ⏳ Run evaluations on improved prompts
2. ⏳ Generate comparison reports
3. ⏳ Document improvements and gaps

**Expected Target**: 75-80/100 (⭐⭐⭐+)

## Running Task #12

When Task #7 is complete and new prompts are ready:

### Step 1: Collect Baseline Outputs
```python
# Run agents with baseline prompts and capture outputs
baseline_results = {
    "theme_1": (outline, slides_data),
    "theme_2": (outline, slides_data),
    "theme_3": (outline, slides_data),
}
```

### Step 2: Collect Improved Outputs
```python
# Run agents with improved prompts and capture outputs
improved_results = {
    "theme_1": (outline, slides_data),
    "theme_2": (outline, slides_data),
    "theme_3": (outline, slides_data),
}
```

### Step 3: Run Evaluations
```python
from tests.agent_eval import EvaluationRunner

baseline_evals = EvaluationRunner.evaluate_batch(baseline_results)
improved_evals = EvaluationRunner.evaluate_batch(improved_results)
```

### Step 4: Generate Comparison Report
```python
comparisons = EvaluationRunner.compare_evaluations(baseline_evals, improved_evals)
report = EvaluationRunner.generate_comparison_report(
    comparisons,
    output_path="reports/prompt_improvement_comparison.md"
)
```

### Step 5: Generate Individual Reports
```python
for eval in improved_evals:
    EvaluationRunner.generate_detailed_report(
        eval,
        output_path=f"reports/{eval.theme_name}_detailed.md"
    )
```

## Output Structure

### Evaluation Result JSON
```python
{
    "theme_name": "AI人工智能在医疗领域的应用",
    "timestamp": "2026-03-01T12:34:56.789Z",
    "overall_score": 72.5,
    "outline_quality": {
        "score": 75.0,
        "section_count": 8,
        "has_cover": true,
        "has_conclusion": true,
        "title_quality": 8.5,
        "key_points_avg": 3.1,
        "type_distribution": {
            "cover": 1,
            "content": 5,
            "comparison": 1,
            "conclusion": 1
        },
        "issues": []
    },
    "content_quality": {
        "score": 70.0,
        "slide_count": 8,
        "text_length_stats": {...},
        "bullet_point_stats": {...},
        "speaker_notes_coverage": 87.5,
        "content_variety": {...},
        "issues": []
    },
    "visual_quality": {
        "score": 65.0,
        "layout_variety": 3,
        "layout_distribution": {...},
        "visual_element_coverage": 37.5,
        "color_usage": {...},
        "animation_suggestions": 25.0,
        "issues": [...]
    },
    "summary": "..."
}
```

## Common Patterns

### Low Outline Score
- Check: Not enough sections (target 6-12)
- Check: Missing cover or conclusion
- Check: Titles are too generic
- Fix: Improve Planner prompt with specific guidelines

### Low Content Score
- Check: Too many/few bullet points
- Check: Low speaker notes coverage
- Check: Inconsistent text lengths
- Fix: Improve Writer prompt with specific constraints

### Low Visual Score
- Check: Limited layout variety
- Check: No visual elements specified
- Check: No color emphasis
- Fix: Improve Visual prompt; enhance Renderer capabilities

## Troubleshooting

**Q: How do I run just outline evaluation?**
```python
from tests.agent_eval import OutlineEvaluator
result = OutlineEvaluator.evaluate(outline)
```

**Q: How do I run just content evaluation?**
```python
from tests.agent_eval import ContentEvaluator
result = ContentEvaluator.evaluate(slides_data)
```

**Q: How do I run just visual evaluation?**
```python
from tests.agent_eval import VisualEvaluator
result = VisualEvaluator.evaluate(slides_data)
```

**Q: Can I use different themes?**
```python
from tests.agent_eval import get_theme_by_name
theme = get_theme_by_name("My Custom Theme")
# Note: Only predefined themes in TEST_THEMES are supported
```

## References

- **Baseline Report**: `docs/agent-baseline-report.md`
- **Agent Code**: `backend/agents/`
  - Researcher: `backend/agents/researcher/`
  - Planner: `backend/agents/planner/`
  - Writer: `backend/agents/writer/`
  - Visual: `backend/agents/visual/`
  - Renderer: `backend/agents/renderer/`

## Contributing

When adding new evaluation metrics:

1. Add metric calculation to appropriate evaluator
2. Update scoring formula in `_calculate_score()`
3. Add metric to README.md reference section
4. Update comparison template
5. Document in docstrings

---

**Framework Version**: 1.0
**Last Updated**: 2026-03-01
**Next Phase**: Task #12 (Post-Improvement Evaluation)
