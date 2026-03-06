"""
Script wrapper modules for huashu-slides scripts
"""

from .image_gen import generate_image
from .html_converter import html_to_pptx_slide
from .slide_creator import create_pptx_from_images

__all__ = [
    "generate_image",
    "html_to_pptx_slide",
    "create_pptx_from_images",
]
