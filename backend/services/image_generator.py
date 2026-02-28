"""
Async-friendly image generator service.

Wraps backend/services/script_wrappers/image_gen.py in an asyncio executor
so it can be called from async code without blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from services.script_wrappers.image_gen import generate_image as _sync_generate

logger = logging.getLogger(__name__)


async def generate_image_async(
    prompt: str,
    output_path: str,
    input_image: Optional[str] = None,
    resolution: str = "1K",
    api_key: Optional[str] = None,
) -> Optional[str]:
    """
    Async wrapper around the synchronous generate_image function.

    Runs the blocking subprocess in a thread pool executor so it does not
    block the main event loop.

    Returns:
        Absolute path to the generated image on success, None on failure.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None,
            lambda: _sync_generate(
                prompt=prompt,
                output_path=output_path,
                input_image=input_image,
                resolution=resolution,
                api_key=api_key,
            ),
        )
    except ValueError as exc:
        logger.error("Image generation validation error: %s", exc)
        return None
    except Exception as exc:
        logger.exception("Image generation unexpected error")
        return None
