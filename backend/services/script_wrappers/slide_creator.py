"""
Wrapper for huashu-slides/scripts/create_slides.py

Creates PowerPoint presentations from image sequences using python-pptx.
Includes validation, layout support, and comprehensive logging.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Valid layout modes
VALID_LAYOUTS = {"fullscreen", "title_above", "title_below", "title_left", "center", "grid"}
DEFAULT_TIMEOUT = 60  # 1 minute for slide creation
DEFAULT_LAYOUT = "fullscreen"


def create_pptx_from_images(
    image_paths: list[str],
    output_path: str,
    layout: str = "fullscreen",
    titles: Optional[list[str]] = None,
    bg_color: str = "FFFFFF",
) -> Optional[str]:
    """
    Create a PowerPoint presentation from a sequence of images.

    Args:
        image_paths: List of image file paths to include in presentation
        output_path: Output PPTX file path
        layout: Layout mode (fullscreen, title_above, title_below, title_left, center, grid)
        titles: Optional list of slide titles (must match image count if provided)
        bg_color: Background color hex code (default FFFFFF)

    Returns:
        Absolute path to created PPTX file on success, None on failure

    Raises:
        ValueError: If validation fails
    """
    # Input validation
    if not image_paths or not isinstance(image_paths, list):
        raise ValueError("image_paths must be a non-empty list")

    if len(image_paths) == 0:
        raise ValueError("At least one image path is required")

    if not output_path:
        raise ValueError("output_path is required")

    if layout not in VALID_LAYOUTS:
        raise ValueError(f"layout must be one of {VALID_LAYOUTS}, got {layout}")

    # Validate all image files exist
    image_file_paths = []
    for img_path in image_paths:
        img_file = Path(img_path)
        if not img_file.exists():
            raise ValueError(f"Image file not found: {img_path}")
        image_file_paths.append(str(img_file.resolve()))

    # Validate titles if provided
    if titles is not None:
        if not isinstance(titles, list):
            raise ValueError("titles must be a list")
        if len(titles) != len(image_paths):
            raise ValueError(f"titles count ({len(titles)}) must match image count ({len(image_paths)})")

    # Prepare output directory
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Build command for uv run
    cmd = [
        "uv",
        "run",
        "huashu-slides/scripts/create_slides.py",
    ]

    # Add image paths
    cmd.extend(image_file_paths)

    # Add layout
    cmd.extend(["--layout", layout])

    # Add output path
    cmd.extend(["-o", str(output_file)])

    # Add titles if provided
    if titles:
        cmd.extend(["-t"] + titles)

    logger.info(
        f"Creating PPTX from {len(image_paths)} images: layout={layout}, output={output_file}"
    )
    logger.debug(f"Command: {' '.join(cmd[:5])}... (+ {len(image_paths)} images)")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
        )

        if result.returncode != 0:
            logger.error(
                f"PPTX creation failed: {result.stderr}",
                extra={"stdout": result.stdout, "stderr": result.stderr},
            )
            return None

        # Verify output file exists
        if not output_file.exists():
            logger.error("PPTX creation completed but output file not found")
            return None

        logger.info(f"PPTX created successfully: {output_file.resolve()}")
        return str(output_file.resolve())

    except subprocess.TimeoutExpired:
        logger.error(f"PPTX creation timed out after {DEFAULT_TIMEOUT}s")
        return None

    except Exception as e:
        logger.error(f"PPTX creation error: {str(e)}", exc_info=True)
        return None
