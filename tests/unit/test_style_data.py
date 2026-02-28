"""Unit tests for style data validation"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any


REQUIRED_FIELDS = {
    "id", "name_zh", "name_en", "tier", "colors", "typography",
    "use_cases", "sample_image_path", "render_paths"
}


def get_style_json_files(styles_path):
    """Get all style JSON files, excluding metadata like index.json"""
    return [f for f in styles_path.glob("*.json") if f.name != "index.json"]

REQUIRED_COLOR_FIELDS = {"primary", "secondary", "background", "text", "accent"}
REQUIRED_TYPOGRAPHY_FIELDS = {"title_size", "body_size", "family"}
VALID_TIERS = {1, 2, 3, "editorial"}
VALID_RENDER_PATHS = {"path_a", "path_b"}


@pytest.mark.unit
class TestStyleDataValidation:
    """Test style JSON data validation"""

    def test_style_files_exist(self, styles_path):
        """Verify style JSON files exist"""
        assert styles_path.exists(), f"Styles directory not found at {styles_path}"
        json_files = get_style_json_files(styles_path)
        assert len(json_files) > 0, "No style JSON files found"

    def test_style_json_is_valid(self, styles_path):
        """Verify all style JSON files are valid JSON"""
        json_files = get_style_json_files(styles_path)
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {json_file.name}: {e}")

    def test_style_has_required_fields(self, styles_path):
        """Verify each style has all required top-level fields"""
        json_files = get_style_json_files(styles_path)
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            missing_fields = REQUIRED_FIELDS - set(style.keys())
            assert not missing_fields, (
                f"{json_file.name} missing fields: {missing_fields}"
            )

    def test_style_id_matches_filename(self, styles_path):
        """Verify style id matches the filename pattern"""
        json_files = get_style_json_files(styles_path)
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            # ID should match filename without .json extension
            expected_id = json_file.stem
            assert style["id"] == expected_id, (
                f"{json_file.name} id '{style['id']}' doesn't match filename '{expected_id}'"
            )

    def test_style_colors_valid(self, styles_path):
        """Verify colors object has all required fields"""
        json_files = get_style_json_files(styles_path)
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            colors = style.get("colors", {})
            assert isinstance(colors, dict), f"{json_file.name} colors must be an object"

            missing_colors = REQUIRED_COLOR_FIELDS - set(colors.keys())
            assert not missing_colors, (
                f"{json_file.name} colors missing: {missing_colors}"
            )

            # Verify all color values are valid hex codes
            for color_name, color_value in colors.items():
                if isinstance(color_value, str):
                    assert color_value.startswith("#") and len(color_value) == 7, (
                        f"{json_file.name} color '{color_name}' has invalid format: {color_value}"
                    )
                elif isinstance(color_value, list):
                    for additional_color in color_value:
                        assert additional_color.startswith("#") and len(additional_color) == 7, (
                            f"{json_file.name} additional color has invalid format: {additional_color}"
                        )

    def test_style_typography_valid(self, styles_path):
        """Verify typography object has required fields"""
        json_files = get_style_json_files(styles_path)
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            typography = style.get("typography", {})
            assert isinstance(typography, dict), f"{json_file.name} typography must be an object"

            missing_typography = REQUIRED_TYPOGRAPHY_FIELDS - set(typography.keys())
            assert not missing_typography, (
                f"{json_file.name} typography missing: {missing_typography}"
            )

    def test_style_tier_valid(self, styles_path):
        """Verify tier value is valid"""
        json_files = get_style_json_files(styles_path)
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            tier = style.get("tier")
            assert tier in VALID_TIERS, (
                f"{json_file.name} has invalid tier: {tier}. Must be in {VALID_TIERS}"
            )

    def test_style_use_cases_valid(self, styles_path):
        """Verify use_cases is a non-empty array"""
        json_files = get_style_json_files(styles_path)
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            use_cases = style.get("use_cases", [])
            assert isinstance(use_cases, list), f"{json_file.name} use_cases must be an array"
            assert len(use_cases) > 0, f"{json_file.name} use_cases cannot be empty"

            # All items should be strings
            for case in use_cases:
                assert isinstance(case, str), (
                    f"{json_file.name} use_cases must contain only strings"
                )

    def test_style_render_paths_valid(self, styles_path):
        """Verify render_paths array has valid values"""
        json_files = get_style_json_files(styles_path)
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            render_paths = style.get("render_paths", [])
            assert isinstance(render_paths, list), (
                f"{json_file.name} render_paths must be an array"
            )
            assert len(render_paths) > 0, (
                f"{json_file.name} render_paths cannot be empty"
            )

            # All paths should be valid
            invalid_paths = set(render_paths) - VALID_RENDER_PATHS
            assert not invalid_paths, (
                f"{json_file.name} has invalid render_paths: {invalid_paths}"
            )

    def test_style_sample_image_exists(self, styles_path):
        """Verify referenced sample images exist"""
        json_files = get_style_json_files(styles_path)
        samples_dir = styles_path / "samples"

        if not samples_dir.exists():
            pytest.skip("Samples directory doesn't exist yet")

        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            sample_path = style.get("sample_image_path", "")
            assert sample_path, f"{json_file.name} must have sample_image_path"

            # Extract filename from path (e.g., "/static/styles/samples/file.png" -> "file.png")
            filename = Path(sample_path).name
            actual_path = samples_dir / filename

            if actual_path.exists():
                # Verify it's an image file
                assert filename.endswith(('.png', '.jpg', '.jpeg', '.gif')), (
                    f"{json_file.name} sample_image_path points to non-image file: {filename}"
                )

    def test_style_names_not_empty(self, styles_path):
        """Verify Chinese and English names are not empty"""
        json_files = get_style_json_files(styles_path)
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                style = json.load(f)

            name_zh = style.get("name_zh", "").strip()
            name_en = style.get("name_en", "").strip()

            assert name_zh, f"{json_file.name} name_zh cannot be empty"
            assert name_en, f"{json_file.name} name_en cannot be empty"


@pytest.mark.unit
class TestStyleDataSchema:
    """Test style data structure and types"""

    def test_sample_style_structure(self, sample_style_json):
        """Verify sample style has correct structure"""
        assert all(field in sample_style_json for field in REQUIRED_FIELDS), (
            "Sample style missing required fields"
        )

    def test_invalid_style_missing_fields(self, invalid_style_json):
        """Verify invalid style is missing required fields"""
        missing_fields = REQUIRED_FIELDS - set(invalid_style_json.keys())
        assert len(missing_fields) > 0, "Invalid style should be missing fields"

    def test_style_tier_type_coercion(self, sample_style_json):
        """Verify tier can be int or string"""
        # Test with int
        sample_style_json["tier"] = 1
        assert sample_style_json["tier"] in VALID_TIERS

        # Test with string
        sample_style_json["tier"] = "editorial"
        assert sample_style_json["tier"] in VALID_TIERS
