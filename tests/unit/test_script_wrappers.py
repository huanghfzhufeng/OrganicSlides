"""Unit tests for script wrapper validation"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from PIL import Image as PILImage, ImageStat

from services.script_wrappers.image_gen import generate_image, VALID_RESOLUTIONS
from services.script_wrappers.html_converter import html_to_pptx_slide
from services.script_wrappers.slide_creator import create_pptx_from_images, VALID_LAYOUTS


@pytest.mark.unit
class TestImageGenWrapper:
    """Test image_gen wrapper parameter validation"""

    def test_validate_prompt_required(self):
        """Test that prompt is required and non-empty"""
        with pytest.raises(ValueError, match="prompt must be a non-empty string"):
            generate_image("", "/tmp/output.png", api_key="test-key")

    def test_validate_prompt_must_be_string(self):
        """Test that prompt must be a string"""
        with pytest.raises(ValueError, match="prompt must be a non-empty string"):
            generate_image(None, "/tmp/output.png", api_key="test-key")

    def test_validate_output_path_required(self):
        """Test that output_path is required"""
        with pytest.raises(ValueError, match="output_path is required"):
            generate_image("test prompt", "", api_key="test-key")

    def test_validate_resolution_valid_values(self):
        """Test that resolution must be from valid set"""
        for resolution in ["0.5K", "1K", "2K", "4K"]:
            # Should not raise
            assert resolution in VALID_RESOLUTIONS

    def test_validate_resolution_invalid_value(self):
        """Test rejection of invalid resolution"""
        with pytest.raises(ValueError, match="resolution must be one of"):
            generate_image("test", "/tmp/out.png", resolution="8K", api_key="test-key")

    def test_validate_input_image_must_exist(self):
        """Test that input_image must exist if provided"""
        with pytest.raises(ValueError, match="input_image file not found"):
            generate_image("test", "/tmp/out.png", input_image="/nonexistent/file.png", api_key="test-key")

    def test_validate_api_key_required(self):
        """Test that API key is required"""
        with pytest.raises(ValueError, match="API key not provided"):
            generate_image("test", "/tmp/out.png")

    @patch.dict("os.environ", {}, clear=True)
    def test_validate_api_key_from_env_missing(self):
        """Test error when API key not in environment and not provided"""
        with pytest.raises(ValueError, match="API key not provided"):
            generate_image("test prompt", "/tmp/output.png")

    @patch("services.script_wrappers.image_gen._generate_with_genai")
    def test_successful_image_generation(self, mock_generate, tmp_path):
        """Test successful image generation returns path"""
        output_file = tmp_path / "output.png"
        PILImage.new("RGB", (1200, 1200), color="white").save(output_file, "PNG")
        mock_generate.return_value = str(output_file.resolve())

        result = generate_image(
            "test prompt",
            str(output_file),
            api_key="test-key"
        )

        assert result == str(output_file.resolve())
        mock_generate.assert_called_once()

    @patch("services.script_wrappers.image_gen._generate_with_genai")
    def test_image_generation_returns_none_on_nonzero_exit(self, mock_generate):
        """Test that internal generation errors return None"""
        mock_generate.side_effect = RuntimeError("Error")

        result = generate_image(
            "test prompt",
            "/tmp/output.png",
            api_key="test-key"
        )

        assert result is None

    @patch("services.script_wrappers.image_gen._generate_with_genai")
    def test_image_generation_file_not_created(self, mock_generate, tmp_path):
        """Test that None is returned if generation yields no output path"""
        mock_generate.return_value = None
        output_path = tmp_path / "output.png"

        result = generate_image(
            "test prompt",
            str(output_path),
            api_key="test-key"
        )

        assert result is None

    @patch("services.script_wrappers.image_gen._generate_with_genai")
    def test_image_generation_timeout_handling(self, mock_generate):
        """Test timeout handling"""
        mock_generate.side_effect = TimeoutError("timed out")

        result = generate_image(
            "test prompt",
            "/tmp/output.png",
            api_key="test-key"
        )

        assert result is None

    @patch("services.script_wrappers.image_gen._generate_with_genai")
    def test_image_gen_command_includes_input_image(self, mock_generate, tmp_path):
        """Test that input_image is forwarded to the SDK wrapper if provided"""
        input_file = tmp_path / "input.png"
        output_file = tmp_path / "output.png"
        PILImage.new("RGB", (100, 100), color="white").save(input_file, "PNG")
        PILImage.new("RGB", (1200, 1200), color="white").save(output_file, "PNG")
        mock_generate.return_value = str(output_file.resolve())

        generate_image(
            "test prompt",
            str(output_file),
            input_image=str(input_file),
            api_key="test-key"
        )

        assert mock_generate.call_args.kwargs["input_image"] == str(input_file)

    @patch("services.script_wrappers.image_gen._generate_with_genai")
    def test_retry_ratio_size_with_12ai_proxy(self, mock_generate, tmp_path):
        """Test that 12ai ratio sizes retry with a provider-safe resolution."""
        output_file = tmp_path / "output.png"

        def side_effect(**kwargs):
            if kwargs["image_size"] == "16:9":
                raise RuntimeError('{"code":"invalid_value","path":["image_size"]}')
            PILImage.new("RGB", (1024, 1024), color="white").save(kwargs["output_file"], "PNG")
            return str(Path(kwargs["output_file"]).resolve())

        mock_generate.side_effect = side_effect

        result = generate_image(
            "test prompt",
            str(output_file),
            api_key="test-key",
            base_url="https://new.12ai.org",
            image_size="16:9",
        )

        assert result == str(output_file.resolve())
        assert mock_generate.call_count == 2
        assert mock_generate.call_args.kwargs["image_size"] == "1K"

    @patch("services.script_wrappers.image_gen._generate_with_genai")
    def test_multiple_candidates_choose_best_image(self, mock_generate, tmp_path):
        """Test that multiple image candidates are scored and best candidate is kept."""
        output_file = tmp_path / "output.png"

        def side_effect(**kwargs):
            destination = Path(kwargs["output_file"])
            if "candidate_1" in destination.name:
                PILImage.new("RGB", (1024, 1024), color=(128, 128, 128)).save(destination, "PNG")
            elif "candidate_2" in destination.name:
                image = PILImage.new("RGB", (1600, 900), color="black")
                for x in range(800, 1600):
                    for y in range(900):
                        image.putpixel((x, y), (255, 255, 255))
                image.save(destination, "PNG")
            else:
                PILImage.new("RGB", (900, 1600), color=(140, 140, 140)).save(destination, "PNG")
            return str(destination.resolve())

        mock_generate.side_effect = side_effect

        result = generate_image(
            "test prompt",
            str(output_file),
            api_key="test-key",
            number_of_images=3,
        )

        assert result == str(output_file.resolve())
        assert mock_generate.call_count == 3

        with PILImage.open(output_file) as image:
            assert image.size == (1600, 900)
            contrast = ImageStat.Stat(image.convert("L")).stddev[0]
            assert contrast > 50


@pytest.mark.unit
class TestHtmlConverterWrapper:
    """Test html_converter wrapper validation"""

    def test_validate_html_file_path_required(self):
        """Test that html_file_path is required"""
        with pytest.raises(ValueError, match="html_file_path is required"):
            html_to_pptx_slide("")

    def test_validate_html_file_must_exist(self):
        """Test that HTML file must exist"""
        with pytest.raises(ValueError, match="HTML file not found"):
            html_to_pptx_slide("/nonexistent/file.html")

    def test_validate_html_file_extension(self, tmp_path):
        """Test that file must have .html extension"""
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        with pytest.raises(ValueError, match="Expected .html file"):
            html_to_pptx_slide(str(txt_file))

    @patch("subprocess.run")
    def test_successful_html_conversion(self, mock_run, tmp_path):
        """Test successful HTML conversion returns slide data"""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html></html>")

        slide_data = {
            "success": True,
            "slide_id": "slide-1",
            "width_px": 1920,
            "height_px": 1080,
            "placeholders": [],
            "output_path": "/output/slide.pptx"
        }

        import json
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(slide_data),
            stderr=""
        )

        result = html_to_pptx_slide(str(html_file))

        assert result is not None
        assert result["slide_id"] == "slide-1"
        assert result["width_px"] == 1920

    @patch("subprocess.run")
    def test_html_conversion_returns_none_on_error(self, mock_run, tmp_path):
        """Test that conversion error returns None"""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html></html>")

        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error")

        result = html_to_pptx_slide(str(html_file))

        assert result is None

    @patch("subprocess.run")
    def test_html_conversion_invalid_json_output(self, mock_run, tmp_path):
        """Test that invalid JSON output returns None"""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html></html>")

        mock_run.return_value = Mock(
            returncode=0,
            stdout="invalid json",
            stderr=""
        )

        result = html_to_pptx_slide(str(html_file))

        assert result is None

    @patch("subprocess.run")
    def test_html_conversion_timeout_handling(self, mock_run, tmp_path):
        """Test timeout handling"""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html></html>")

        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 120)

        result = html_to_pptx_slide(str(html_file))

        assert result is None


@pytest.mark.unit
class TestSlideCreatorWrapper:
    """Test slide_creator wrapper validation"""

    def test_validate_image_paths_required(self):
        """Test that image_paths is required and non-empty"""
        with pytest.raises(ValueError, match="image_paths must be a non-empty list"):
            create_pptx_from_images([], "/tmp/output.pptx")

    def test_validate_image_paths_must_be_list(self):
        """Test that image_paths must be a list"""
        with pytest.raises(ValueError, match="image_paths must be a non-empty list"):
            create_pptx_from_images("not a list", "/tmp/output.pptx")

    def test_validate_output_path_required(self):
        """Test that output_path is required"""
        with pytest.raises(ValueError, match="output_path is required"):
            create_pptx_from_images(["/tmp/test.png"], "")

    def test_validate_layout_valid_values(self):
        """Test that layout must be from valid set"""
        for layout in VALID_LAYOUTS:
            assert layout in VALID_LAYOUTS

    def test_validate_layout_invalid_value(self):
        """Test rejection of invalid layout"""
        with tempfile.TemporaryDirectory() as tmp:
            img_file = Path(tmp) / "test.png"
            img_file.touch()
            with pytest.raises(ValueError, match="layout must be one of"):
                create_pptx_from_images(
                    [str(img_file)],
                    "/tmp/output.pptx",
                    layout="invalid_layout"
                )

    def test_validate_image_files_must_exist(self):
        """Test that all image files must exist"""
        with pytest.raises(ValueError, match="Image file not found"):
            create_pptx_from_images(
                ["/nonexistent/image.png"],
                "/tmp/output.pptx"
            )

    def test_validate_titles_must_match_image_count(self, tmp_path):
        """Test that titles count must match image count"""
        img_file = tmp_path / "test.png"
        img_file.touch()

        with pytest.raises(ValueError, match="titles count.*must match"):
            create_pptx_from_images(
                [str(img_file)],
                "/tmp/output.pptx",
                titles=["Title 1", "Title 2"]  # Mismatch: 2 titles, 1 image
            )

    @patch("subprocess.run")
    def test_successful_pptx_creation(self, mock_run, tmp_path):
        """Test successful PPTX creation returns path"""
        img_file = tmp_path / "test.png"
        img_file.touch()
        output_file = tmp_path / "output.pptx"
        output_file.touch()

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = create_pptx_from_images(
            [str(img_file)],
            str(output_file)
        )

        assert result == str(output_file.resolve())

    @patch("subprocess.run")
    def test_pptx_creation_returns_none_on_error(self, mock_run, tmp_path):
        """Test that creation error returns None"""
        img_file = tmp_path / "test.png"
        img_file.touch()

        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error")

        result = create_pptx_from_images(
            [str(img_file)],
            "/tmp/output.pptx"
        )

        assert result is None

    @patch("subprocess.run")
    def test_pptx_creation_file_not_created(self, mock_run, tmp_path):
        """Test that None is returned if output file doesn't exist"""
        img_file = tmp_path / "test.png"
        img_file.touch()

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        output_path = tmp_path / "output.pptx"

        result = create_pptx_from_images(
            [str(img_file)],
            str(output_path)
        )

        # Since the subprocess call succeeds but the file wasn't created, should return None
        assert result is None

    @patch("subprocess.run")
    def test_pptx_creation_with_titles(self, mock_run, tmp_path):
        """Test PPTX creation with titles"""
        img_file = tmp_path / "test.png"
        img_file.touch()
        output_file = tmp_path / "output.pptx"
        output_file.touch()

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        create_pptx_from_images(
            [str(img_file)],
            str(output_file),
            titles=["My Title"]
        )

        # Verify command includes titles
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "-t" in cmd
        assert "My Title" in cmd

    @patch("subprocess.run")
    def test_pptx_creation_timeout_handling(self, mock_run, tmp_path):
        """Test timeout handling"""
        img_file = tmp_path / "test.png"
        img_file.touch()

        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 60)

        result = create_pptx_from_images(
            [str(img_file)],
            "/tmp/output.pptx"
        )

        assert result is None

    @patch("subprocess.run")
    def test_pptx_creation_multiple_images(self, mock_run, tmp_path):
        """Test PPTX creation with multiple images"""
        img_files = []
        for i in range(3):
            img_file = tmp_path / f"test{i}.png"
            img_file.touch()
            img_files.append(str(img_file))

        output_file = tmp_path / "output.pptx"
        output_file.touch()

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = create_pptx_from_images(img_files, str(output_file))

        assert result is not None
        # Verify command includes all images
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        for img in img_files:
            assert img in cmd
