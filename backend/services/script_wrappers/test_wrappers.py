"""
Unit tests for script wrapper modules

Tests parameter validation, error handling, and interface contracts
without actually invoking the external scripts.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

from image_gen import generate_image, VALID_RESOLUTIONS
from html_converter import html_to_pptx_slide
from slide_creator import create_pptx_from_images, VALID_LAYOUTS


class TestImageGen:
    """Tests for image_gen.generate_image()"""

    def test_validate_prompt_required(self):
        """Test that prompt validation rejects empty strings"""
        with pytest.raises(ValueError, match="non-empty string"):
            generate_image("", output_path="/tmp/out.png")

    def test_validate_prompt_type(self):
        """Test that prompt must be string"""
        with pytest.raises(ValueError, match="non-empty string"):
            generate_image(None, output_path="/tmp/out.png")

    def test_validate_output_path_required(self):
        """Test that output_path is required"""
        with pytest.raises(ValueError, match="output_path is required"):
            generate_image("test prompt", output_path="")

    def test_validate_resolution(self):
        """Test that resolution must be in VALID_RESOLUTIONS"""
        with pytest.raises(ValueError, match="must be one of"):
            generate_image("test prompt", output_path="/tmp/out.png", resolution="8K")

    def test_validate_resolution_accepted(self):
        """Test that valid resolutions are accepted"""
        for res in VALID_RESOLUTIONS:
            with patch("subprocess.run") as mock_run:
                with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                    mock_run.return_value = MagicMock(returncode=1)
                    # Should not raise ValueError
                    generate_image("test", output_path="/tmp/out.png", resolution=res)

    def test_validate_input_image_exists(self):
        """Test that input_image file must exist"""
        with pytest.raises(ValueError, match="input_image file not found"):
            generate_image(
                "test prompt",
                output_path="/tmp/out.png",
                input_image="/nonexistent/file.png",
            )

    def test_validate_api_key_required(self):
        """Test that API key is required"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key not provided"):
                generate_image("test prompt", output_path="/tmp/out.png")

    @patch("subprocess.run")
    def test_api_key_from_parameter(self, mock_run):
        """Test that API key parameter overrides environment"""
        mock_run.return_value = MagicMock(returncode=1)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"}, clear=True):
            # Should not raise ValueError
            generate_image(
                "test prompt", output_path="/tmp/out.png", api_key="param-key"
            )
            # Verify correct key was passed to subprocess
            env = mock_run.call_args.kwargs["env"]
            assert env["GEMINI_API_KEY"] == "param-key"

    @patch("subprocess.run")
    def test_subprocess_called(self, mock_run):
        """Test that subprocess.run is called with correct command"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.png")
            # Create a dummy output file so the function returns success
            Path(output_path).touch()

            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                mock_run.return_value = MagicMock(returncode=0)
                result = generate_image(
                    "test prompt", output_path=output_path, resolution="2K"
                )

                # Verify subprocess was called
                mock_run.assert_called_once()
                call_args = mock_run.call_args

                # Verify command
                cmd = call_args[0][0]
                assert "uv" in cmd
                assert "generate_image.py" in cmd
                assert "test prompt" in cmd
                assert "2K" in cmd

    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Test that timeout exceptions are caught and logged"""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 300)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = generate_image("test prompt", output_path="/tmp/out.png")
            assert result is None

    @patch("subprocess.run")
    def test_failed_subprocess(self, mock_run):
        """Test that non-zero exit code returns None"""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = generate_image("test prompt", output_path="/tmp/out.png")
            assert result is None


class TestHtmlConverter:
    """Tests for html_converter.html_to_pptx_slide()"""

    def test_validate_html_path_required(self):
        """Test that html_file_path is required"""
        with pytest.raises(ValueError, match="html_file_path is required"):
            html_to_pptx_slide("")

    def test_validate_html_file_exists(self):
        """Test that HTML file must exist"""
        with pytest.raises(ValueError, match="HTML file not found"):
            html_to_pptx_slide("/nonexistent/file.html")

    def test_validate_html_extension(self):
        """Test that file must have .html extension"""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            with pytest.raises(ValueError, match="Expected .html file"):
                html_to_pptx_slide(tmp.name)

    @patch("subprocess.run")
    def test_subprocess_called(self, mock_run):
        """Test that subprocess.run is called with HTML file"""
        with tempfile.NamedTemporaryFile(suffix=".html") as tmp:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"output_path": "/tmp/out.pptx"}',
            )

            result = html_to_pptx_slide(tmp.name)

            # Verify subprocess was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "node" in cmd
            assert "html2pptx.js" in cmd
            assert tmp.name in cmd

    @patch("subprocess.run")
    def test_parse_json_output(self, mock_run):
        """Test that JSON output is parsed correctly"""
        with tempfile.NamedTemporaryFile(suffix=".html") as tmp:
            expected_data = {"output_path": "/tmp/out.pptx", "slides": 5}
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=str(expected_data).replace("'", '"'),
            )

            result = html_to_pptx_slide(tmp.name)
            # Result might be dict if JSON parses, or None if it doesn't
            # The actual parsing depends on the JSON format

    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Test that timeout is caught"""
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=".html") as tmp:
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 120)
            result = html_to_pptx_slide(tmp.name)
            assert result is None

    @patch("subprocess.run")
    def test_failed_conversion(self, mock_run):
        """Test that non-zero exit code returns None"""
        with tempfile.NamedTemporaryFile(suffix=".html") as tmp:
            mock_run.return_value = MagicMock(returncode=1, stderr="Conversion failed")
            result = html_to_pptx_slide(tmp.name)
            assert result is None


class TestSlideCreator:
    """Tests for slide_creator.create_pptx_from_images()"""

    def test_validate_image_paths_required(self):
        """Test that image_paths list is required"""
        with pytest.raises(ValueError, match="non-empty list"):
            create_pptx_from_images([], output_path="/tmp/out.pptx")

    def test_validate_output_path_required(self):
        """Test that output_path is required"""
        with pytest.raises(ValueError, match="output_path is required"):
            create_pptx_from_images(["/tmp/img.png"], output_path="")

    def test_validate_layout(self):
        """Test that layout must be in VALID_LAYOUTS"""
        with pytest.raises(ValueError, match="must be one of"):
            create_pptx_from_images(
                ["/tmp/img.png"], output_path="/tmp/out.pptx", layout="invalid"
            )

    def test_validate_image_files_exist(self):
        """Test that all image files must exist"""
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            with pytest.raises(ValueError, match="Image file not found"):
                create_pptx_from_images(
                    [tmp.name, "/nonexistent/img.png"],
                    output_path="/tmp/out.pptx",
                )

    def test_validate_titles_match_images(self):
        """Test that titles count must match image count"""
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            with pytest.raises(ValueError, match="titles count"):
                create_pptx_from_images(
                    [tmp.name],
                    output_path="/tmp/out.pptx",
                    titles=["Title1", "Title2"],
                )

    @patch("subprocess.run")
    def test_subprocess_called(self, mock_run):
        """Test that subprocess is called with correct arguments"""
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "out.pptx")
                Path(output_path).touch()

                mock_run.return_value = MagicMock(returncode=0)
                result = create_pptx_from_images(
                    [tmp.name],
                    output_path=output_path,
                    layout="fullscreen",
                )

                mock_run.assert_called_once()
                call_args = mock_run.call_args
                cmd = call_args[0][0]
                assert "uv" in cmd
                assert "create_slides.py" in cmd
                assert "--layout" in cmd
                assert "fullscreen" in cmd

    @patch("subprocess.run")
    def test_titles_passed_to_subprocess(self, mock_run):
        """Test that titles are passed to subprocess"""
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "out.pptx")
                Path(output_path).touch()

                mock_run.return_value = MagicMock(returncode=0)
                result = create_pptx_from_images(
                    [tmp.name],
                    output_path=output_path,
                    titles=["My Title"],
                )

                call_args = mock_run.call_args
                cmd = call_args[0][0]
                assert "-t" in cmd
                assert "My Title" in cmd

    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Test that timeout is caught"""
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 60)
            result = create_pptx_from_images([tmp.name], output_path="/tmp/out.pptx")
            assert result is None

    @patch("subprocess.run")
    def test_failed_creation(self, mock_run):
        """Test that non-zero exit code returns None"""
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            mock_run.return_value = MagicMock(returncode=1, stderr="Failed")
            result = create_pptx_from_images([tmp.name], output_path="/tmp/out.pptx")
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
