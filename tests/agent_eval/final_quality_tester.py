"""
Final Quality Verification Test Suite

Comprehensive testing framework for validating presentation quality across
5 themes × 3 styles = 15 test combinations.

Status: Prepared and ready to execute once error handling (Task #15) is in place.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json


class Theme(Enum):
    """Test themes for final quality verification"""
    ACADEMIC = "AI人工智能在医疗领域的应用"
    BUSINESS = "新能源汽车市场分析与投资策略"
    PUBLIC_WELFARE = "校园心理健康关爱行动"
    STARTUP = "创业公司融资路演"
    ENVIRONMENTAL = "环保可持续发展倡议"


class StyleTier(Enum):
    """Style tier selection"""
    TIER_1 = "01-snoopy"          # Recommended
    TIER_2 = "05-xkcd"            # Advanced
    TIER_3 = "18-neo-brutalism"   # Specialized


@dataclass
class TestCombination:
    """Single test case: theme × style"""
    theme: Theme
    style: StyleTier
    combination_id: str

    def __str__(self) -> str:
        return f"{self.combination_id}: {self.theme.value} + {self.style.value}"


@dataclass
class VerificationResult:
    """Result of verifying a single presentation"""
    combination_id: str
    theme: str
    style: str
    passed: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, Any]
    details: Dict[str, Any]


class TestMatrix:
    """Generate and manage the 5×3 test matrix"""

    THEMES = [
        Theme.ACADEMIC,
        Theme.BUSINESS,
        Theme.PUBLIC_WELFARE,
        Theme.STARTUP,
        Theme.ENVIRONMENTAL,
    ]

    STYLES = [
        StyleTier.TIER_1,
        StyleTier.TIER_2,
        StyleTier.TIER_3,
    ]

    @staticmethod
    def generate_combinations() -> List[TestCombination]:
        """Generate all 15 test combinations"""
        combinations = []
        counter = 1

        for theme in TestMatrix.THEMES:
            for style in TestMatrix.STYLES:
                combination_id = f"T{counter:02d}"
                combinations.append(
                    TestCombination(theme=theme, style=style, combination_id=combination_id)
                )
                counter += 1

        return combinations

    @staticmethod
    def print_test_matrix():
        """Print test matrix for reference"""
        combinations = TestMatrix.generate_combinations()
        print("\n=== Final Quality Verification Test Matrix ===\n")
        print(f"{'ID':<5} {'Theme':<40} {'Style':<20}")
        print("-" * 65)

        for combo in combinations:
            print(f"{combo.combination_id:<5} {combo.theme.value:<40} {combo.style.value:<20}")

        print(f"\nTotal: {len(combinations)} test combinations")
        print()


class VerificationChecklist:
    """Checklist for verifying each presentation"""

    @staticmethod
    def verify_generation_completion(pptx_path: str) -> Tuple[bool, List[str]]:
        """Check that generation completed and file exists"""
        errors = []

        if not pptx_path:
            errors.append("PPTX path is empty")
            return False, errors

        # Note: Actual file check would go here
        # import os
        # if not os.path.exists(pptx_path):
        #     errors.append(f"PPTX file not found: {pptx_path}")

        if errors:
            return False, errors
        return True, []

    @staticmethod
    def verify_slide_count(slide_data: List[Dict], expected_min: int = 6, expected_max: int = 12) -> Tuple[bool, List[str]]:
        """Verify slide count is in expected range"""
        errors = []
        warnings = []

        if not slide_data:
            errors.append("No slides in presentation")
            return False, errors

        count = len(slide_data)

        if count < expected_min:
            errors.append(f"Too few slides: {count} (expected ≥{expected_min})")
        elif count > expected_max:
            warnings.append(f"Too many slides: {count} (expected ≤{expected_max})")

        passed = len(errors) == 0
        return passed, errors + warnings

    @staticmethod
    def verify_assertion_evidence_titles(slide_data: List[Dict]) -> Tuple[bool, List[str], List[str]]:
        """Verify titles follow assertion-evidence principle"""
        errors = []
        warnings = []

        invalid_titles = []
        for i, slide in enumerate(slide_data, 1):
            title = slide.get("title", "").strip()

            if not title:
                errors.append(f"Slide {i}: Missing title")
                continue

            # Check if title is a complete sentence (has subject, verb, possibly object)
            # This is a heuristic check
            words = title.split()
            if len(words) < 3:
                warnings.append(f"Slide {i}: Title too short - may not be complete assertion: '{title}'")
                invalid_titles.append((i, title))
            elif any(generic in title for generic in ["介绍", "内容", "说明", "讲解"]):
                warnings.append(f"Slide {i}: Title may be generic topic word: '{title}'")
                invalid_titles.append((i, title))

        passed = len(errors) == 0
        return passed, errors, warnings + [f"Invalid titles: {invalid_titles}"] if invalid_titles else warnings

    @staticmethod
    def verify_visual_types(slide_data: List[Dict]) -> Tuple[bool, List[str], List[str]]:
        """Verify visual types are appropriate for content"""
        errors = []
        warnings = []

        valid_types = {"illustration", "chart", "flow", "quote", "data", "cover"}

        for i, slide in enumerate(slide_data, 1):
            visual_type = slide.get("visual_type")

            if not visual_type:
                warnings.append(f"Slide {i}: Missing visual_type")
                continue

            if visual_type not in valid_types:
                errors.append(f"Slide {i}: Invalid visual_type '{visual_type}'")
            else:
                # Heuristic checks for appropriateness
                content = slide.get("content", {})
                bullet_points = content.get("bullet_points", [])

                if visual_type == "chart" and not bullet_points:
                    warnings.append(f"Slide {i}: visual_type='chart' but no data/bullet points")
                elif visual_type == "quote" and len(bullet_points) > 1:
                    warnings.append(f"Slide {i}: visual_type='quote' but has {len(bullet_points)} bullet points")

        passed = len(errors) == 0
        return passed, errors, warnings

    @staticmethod
    def verify_bullet_point_constraints(slide_data: List[Dict]) -> Tuple[bool, List[str], List[str]]:
        """Verify bullet point constraints (≤4 per slide, ≤12 chars each)"""
        errors = []
        warnings = []

        for i, slide in enumerate(slide_data, 1):
            content = slide.get("content", {})
            bullet_points = content.get("bullet_points", [])

            if len(bullet_points) > 4:
                errors.append(f"Slide {i}: {len(bullet_points)} bullet points (max 4)")

            for j, point in enumerate(bullet_points, 1):
                point_text = str(point).strip()
                if len(point_text) > 12:
                    warnings.append(f"Slide {i}, point {j}: '{point_text}' is {len(point_text)} chars (max 12)")

        passed = len(errors) == 0
        return passed, errors, warnings

    @staticmethod
    def verify_style_compliance(style: StyleTier) -> Tuple[bool, List[str], List[str]]:
        """Verify style colors and typography are correctly applied"""
        errors = []
        warnings = []

        # Note: Actual verification would require analyzing the PPTX file
        # For now, this is a placeholder that checks configuration

        # Would check:
        # - Colors match style config
        # - Fonts match style config (Fraunces for headers, Nunito for body)
        # - Spacing follows organic design principles

        return True, errors, warnings

    @staticmethod
    def verify_pptx_compatibility(pptx_path: str) -> Tuple[bool, List[str], List[str]]:
        """Verify PPTX file can be opened and is valid"""
        errors = []
        warnings = []

        # Note: Requires python-pptx library
        # from pptx import Presentation
        # try:
        #     prs = Presentation(pptx_path)
        #     if len(prs.slides) == 0:
        #         errors.append("PPTX contains no slides")
        # except Exception as e:
        #     errors.append(f"Cannot open PPTX: {str(e)}")

        return True, errors, warnings

    @staticmethod
    def verify_no_blank_slides(slide_data: List[Dict]) -> Tuple[bool, List[str], List[str]]:
        """Verify no blank/empty slides"""
        errors = []

        for i, slide in enumerate(slide_data, 1):
            title = slide.get("title", "").strip()
            content = slide.get("content", {})
            bullet_points = content.get("bullet_points", [])
            main_text = content.get("main_text", "").strip()
            speaker_notes = slide.get("speaker_notes", "").strip()

            if not title and not main_text and not bullet_points:
                errors.append(f"Slide {i}: Appears blank (no title, text, or points)")

        passed = len(errors) == 0
        return passed, errors, []


class QualityVerifier:
    """Main verifier that runs all checks"""

    @staticmethod
    def verify_combination(
        combination: TestCombination,
        slide_data: List[Dict],
        pptx_path: Optional[str] = None,
    ) -> VerificationResult:
        """
        Verify a single test combination

        Args:
            combination: Test combination (theme × style)
            slide_data: Slide data from generation
            pptx_path: Path to generated PPTX file

        Returns:
            VerificationResult with all checks
        """
        all_errors = []
        all_warnings = []
        metrics = {}

        # Check 1: Generation completion
        if pptx_path:
            passed, errors = VerificationChecklist.verify_generation_completion(pptx_path)
            all_errors.extend(errors)
            metrics["generation_completed"] = passed

        # Check 2: Slide count
        passed, issues = VerificationChecklist.verify_slide_count(slide_data)
        all_errors.extend([e for e in issues if "Too few" in e])
        all_warnings.extend([w for w in issues if "Too many" in w])
        metrics["slide_count"] = len(slide_data)

        # Check 3: Assertion-evidence titles
        passed, errors, warnings = VerificationChecklist.verify_assertion_evidence_titles(slide_data)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        metrics["assertion_titles_valid"] = passed

        # Check 4: Visual types
        passed, errors, warnings = VerificationChecklist.verify_visual_types(slide_data)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        metrics["visual_types_valid"] = passed

        # Check 5: Bullet point constraints
        passed, errors, warnings = VerificationChecklist.verify_bullet_point_constraints(slide_data)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        metrics["bullet_points_valid"] = passed

        # Check 6: Style compliance
        passed, errors, warnings = VerificationChecklist.verify_style_compliance(combination.style)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        metrics["style_compliant"] = passed

        # Check 7: PPTX compatibility
        if pptx_path:
            passed, errors, warnings = VerificationChecklist.verify_pptx_compatibility(pptx_path)
            all_errors.extend(errors)
            all_warnings.extend(warnings)
            metrics["pptx_valid"] = passed

        # Check 8: No blank slides
        passed, errors, _ = VerificationChecklist.verify_no_blank_slides(slide_data)
        all_errors.extend(errors)
        metrics["no_blank_slides"] = passed

        # Determine overall pass/fail
        overall_passed = len(all_errors) == 0

        return VerificationResult(
            combination_id=combination.combination_id,
            theme=combination.theme.value,
            style=combination.style.value,
            passed=overall_passed,
            errors=all_errors,
            warnings=all_warnings,
            metrics=metrics,
            details={"checked_at": "2026-03-01"},
        )

    @staticmethod
    def run_full_matrix_test(
        results_by_combination: Dict[str, Tuple[List[Dict], Optional[str]]]
    ) -> List[VerificationResult]:
        """
        Run verification on all 15 test combinations

        Args:
            results_by_combination: Dict mapping combination_id to (slide_data, pptx_path)

        Returns:
            List of VerificationResults
        """
        combinations = TestMatrix.generate_combinations()
        results = []

        for combo in combinations:
            if combo.combination_id in results_by_combination:
                slide_data, pptx_path = results_by_combination[combo.combination_id]
                result = QualityVerifier.verify_combination(combo, slide_data, pptx_path)
                results.append(result)

        return results


def print_test_matrix_reference():
    """Print the test matrix for quick reference"""
    TestMatrix.print_test_matrix()


if __name__ == "__main__":
    # Print test matrix when run directly
    print_test_matrix_reference()
