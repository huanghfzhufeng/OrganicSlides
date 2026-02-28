"""
Wrapper for huashu-slides/scripts/generate_image.py

Generates images using Google Gemini 3 Pro Image API with parameter validation,
timeout handling, and comprehensive logging.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Valid resolution values
VALID_RESOLUTIONS = {"1K", "2K", "4K"}
DEFAULT_TIMEOUT = 300  # 5 minutes for image generation


def generate_image(
    prompt: str,
    output_path: str,
    input_image: Optional[str] = None,
    resolution: str = "1K",
    api_key: Optional[str] = None,
) -> Optional[str]:
    """
    Generate an image using Google Gemini 3 Pro Image API.

    Args:
        prompt: Image description/prompt (non-empty string required)
        output_path: Output file path for generated image
        input_image: Optional path to input image for style reference/editing
        resolution: Output resolution (1K, 2K, or 4K). Defaults to 1K
        api_key: Gemini API key (uses GEMINI_API_KEY env var if not provided)

    Returns:
        Absolute path to generated image file on success, None on failure

    Raises:
        ValueError: If validation fails
    """
    # Input validation
    if not prompt or not isinstance(prompt, str):
        raise ValueError("prompt must be a non-empty string")

    if not output_path:
        raise ValueError("output_path is required")

    if resolution not in VALID_RESOLUTIONS:
        raise ValueError(f"resolution must be one of {VALID_RESOLUTIONS}, got {resolution}")

    if input_image is not None:
        input_image_path = Path(input_image)
        if not input_image_path.exists():
            raise ValueError(f"input_image file not found: {input_image}")

    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("API key not provided and GEMINI_API_KEY not set in environment")

    # Prepare output directory
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Build command for uv run
    cmd = [
        "uv",
        "run",
        # Find the script in huashu-slides directory
        "huashu-slides/scripts/generate_image.py",
        "--prompt",
        prompt,
        "--filename",
        str(output_file),
        "--resolution",
        resolution,
    ]

    # Add input image if provided
    if input_image is not None:
        cmd.extend(["--input-image", str(input_image)])

    # Set up environment with API key
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = api_key

    logger.info(
        f"Generating image: resolution={resolution}, "
        f"has_input={input_image is not None}, output={output_file}"
    )
    logger.debug(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
        )

        if result.returncode != 0:
            logger.error(
                f"Image generation failed: {result.stderr}",
                extra={"stdout": result.stdout, "stderr": result.stderr},
            )
            return None

        # Verify output file exists
        if not output_file.exists():
            logger.error("Image generation completed but output file not found")
            return None

        logger.info(f"Image generated successfully: {output_file.resolve()}")
        return str(output_file.resolve())

    except subprocess.TimeoutExpired:
        logger.error(f"Image generation timed out after {DEFAULT_TIMEOUT}s")
        return None

    except Exception as e:
        logger.error(f"Image generation error: {str(e)}", exc_info=True)
        return None
