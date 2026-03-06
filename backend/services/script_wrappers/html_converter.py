"""
Wrapper for huashu-slides/scripts/html2pptx.js

Converts HTML slide files to PowerPoint format using Playwright and pptxgenjs.
Includes validation, error handling, and comprehensive logging.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120  # 2 minutes for HTML conversion


def html_to_pptx_slide(html_file_path: str) -> Optional[dict]:
    """
    Convert a single HTML slide file to PPTX format.

    Args:
        html_file_path: Path to HTML file to convert

    Returns:
        Dictionary containing slide data on success, None on failure.
        Dictionary structure:
        {
            "success": bool,
            "slide_id": str,
            "width_px": int,
            "height_px": int,
            "placeholders": [
                {"id": str, "x": float, "y": float, "w": float, "h": float},
                ...
            ],
            "output_path": str
        }

    Raises:
        ValueError: If validation fails
    """
    # Input validation
    if not html_file_path:
        raise ValueError("html_file_path is required")

    html_path = Path(html_file_path)
    if not html_path.exists():
        raise ValueError(f"HTML file not found: {html_file_path}")

    if html_path.suffix.lower() != ".html":
        raise ValueError(f"Expected .html file, got {html_path.suffix}")

    logger.info(f"Converting HTML to PPTX: {html_path}")

    # Build command to run html2pptx.js
    cmd = [
        "node",
        "huashu-slides/scripts/html2pptx.js",
        str(html_path),
    ]

    logger.debug(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
            cwd=None,  # Run from current working directory
        )

        if result.returncode != 0:
            logger.error(
                f"HTML conversion failed: {result.stderr}",
                extra={"stdout": result.stdout, "stderr": result.stderr},
            )
            return None

        # Parse stdout for slide data (json format expected)
        stdout = result.stdout.strip()
        if not stdout:
            logger.error("HTML conversion produced no output")
            return None

        try:
            slide_data = json.loads(stdout)
            logger.info(f"HTML conversion successful: {slide_data.get('output_path', 'unknown')}")
            return slide_data
        except json.JSONDecodeError:
            logger.error(f"Failed to parse slide data as JSON: {stdout}")
            return None

    except subprocess.TimeoutExpired:
        logger.error(f"HTML conversion timed out after {DEFAULT_TIMEOUT}s")
        return None

    except Exception as e:
        logger.error(f"HTML conversion error: {str(e)}", exc_info=True)
        return None
