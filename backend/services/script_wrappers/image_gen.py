"""
Image generation via Google Gemini API (supports custom proxy like 12ai).

Uses google-genai SDK directly instead of subprocess, enabling:
- Custom base_url for API proxies (e.g., 12ai.org)
- Configurable model and image_size
- Better error handling and logging
- Multi-candidate generation with best-image selection
- Automatic normalization onto a slide-friendly 16:9 canvas
"""

import logging
import os
import shutil
from io import BytesIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Valid image_size values (resolution or aspect ratio)
VALID_RESOLUTIONS = {"0.5K", "1K", "2K", "4K"}
VALID_RATIOS = {"1:1", "3:4", "4:3", "9:16", "16:9"}
_DEFAULT_CANDIDATE_COUNT = 1
_MAX_CANDIDATE_COUNT = 4
_DEFAULT_SLIDE_SIZE = (1600, 900)


def generate_image(
    prompt: str,
    output_path: str,
    input_image: Optional[str] = None,
    resolution: str = "1K",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    image_size: Optional[str] = None,
    number_of_images: Optional[int] = None,
    normalize_for_slides: bool = True,
) -> Optional[str]:
    """
    Generate an image using Gemini API (with optional proxy).

    Args:
        prompt: Image description/prompt (non-empty string required)
        output_path: Output file path for generated image
        input_image: Optional path to input image for style reference
        resolution: Legacy resolution param (1K, 2K, 4K). Ignored if image_size is set.
        api_key: API key (falls back to IMAGEN_API_KEY or GEMINI_API_KEY env vars)
        base_url: Custom API base URL (falls back to IMAGEN_BASE_URL env var)
        model: Model name (falls back to IMAGEN_MODEL env var)
        image_size: Image size/ratio (e.g. "3:4", "1K"). Overrides resolution.
            Note: some proxies such as 12ai only accept resolution values.
        number_of_images: Generate multiple candidates, then keep the best one.
        normalize_for_slides: Convert generated output to a 16:9 slide canvas.

    Returns:
        Absolute path to generated image file on success, None on failure

    Raises:
        ValueError: If validation fails
    """
    if not prompt or not isinstance(prompt, str):
        raise ValueError("prompt must be a non-empty string")

    if not output_path:
        raise ValueError("output_path is required")

    if input_image is not None:
        input_path = Path(input_image)
        if not input_path.exists():
            raise ValueError(f"input_image file not found: {input_image}")

    # Resolve API key
    resolved_key = (
        api_key
        or os.environ.get("IMAGEN_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )
    if not resolved_key:
        raise ValueError(
            "API key not provided and neither IMAGEN_API_KEY nor GEMINI_API_KEY is set"
        )

    # Resolve model
    resolved_model = (
        model
        or os.environ.get("IMAGEN_MODEL")
        or "gemini-3.1-flash-image-preview"
    )

    # Resolve base URL (empty string means use Google default)
    resolved_base_url = (
        base_url
        or os.environ.get("IMAGEN_BASE_URL")
        or ""
    )

    # Resolve image size
    resolved_size = (
        image_size
        or os.environ.get("IMAGEN_IMAGE_SIZE")
        or resolution
    )
    resolved_size = str(resolved_size).strip()
    if resolved_size not in VALID_RESOLUTIONS and resolved_size not in VALID_RATIOS:
        raise ValueError(
            "resolution must be one of "
            f"{sorted(VALID_RESOLUTIONS)} or aspect ratios {sorted(VALID_RATIOS)}"
        )

    resolved_candidate_count = _resolve_candidate_count(number_of_images)

    # Prepare output directory
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Generating image: model=%s, size=%s, candidates=%d, proxy=%s, output=%s",
        resolved_model,
        resolved_size,
        resolved_candidate_count,
        resolved_base_url or "google-default",
        output_file,
    )

    candidate_outputs: list[tuple[Path, float]] = []
    for candidate_index in range(resolved_candidate_count):
        candidate_file = _candidate_output_path(
            output_file,
            candidate_index=candidate_index,
            total_candidates=resolved_candidate_count,
        )
        try:
            result_path = _generate_single_candidate(
                prompt=prompt,
                output_file=candidate_file,
                api_key=resolved_key,
                base_url=resolved_base_url,
                model=resolved_model,
                image_size=resolved_size,
                input_image=input_image,
            )
        except ImportError:
            logger.error(
                "google-genai package not installed. Run: pip install google-genai"
            )
            return None
        except Exception as exc:
            logger.warning(
                "Image candidate %d/%d failed: %s",
                candidate_index + 1,
                resolved_candidate_count,
                exc,
                exc_info=True,
            )
            continue

        if not result_path:
            continue

        raw_path = Path(result_path)
        score = _score_image_candidate(raw_path)
        prepared_path = _prepare_slide_image(
            source_path=raw_path,
            output_path=candidate_file,
            normalize_for_slides=normalize_for_slides,
        )
        candidate_outputs.append((prepared_path, score))

    if not candidate_outputs:
        logger.error("No image candidate was generated successfully")
        return None

    best_path, best_score = max(candidate_outputs, key=lambda item: item[1])
    logger.info("Selected best image candidate with score %.3f", best_score)

    final_output = output_file.resolve()
    if best_path.resolve() != final_output:
        shutil.copy2(best_path, final_output)

    for candidate_path, _ in candidate_outputs:
        resolved_candidate = candidate_path.resolve()
        if resolved_candidate == final_output:
            continue
        candidate_path.unlink(missing_ok=True)

    return str(final_output)


def _resolve_candidate_count(number_of_images: Optional[int]) -> int:
    raw_value = (
        number_of_images
        if number_of_images is not None
        else os.environ.get("IMAGEN_NUMBER_OF_IMAGES", _DEFAULT_CANDIDATE_COUNT)
    )
    try:
        count = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("number_of_images must be an integer") from exc

    if count < 1 or count > _MAX_CANDIDATE_COUNT:
        raise ValueError(
            f"number_of_images must be between 1 and {_MAX_CANDIDATE_COUNT}"
        )

    return count


def _candidate_output_path(
    output_file: Path,
    candidate_index: int,
    total_candidates: int,
) -> Path:
    if total_candidates == 1:
        return output_file

    suffix = output_file.suffix or ".png"
    return output_file.with_name(
        f"{output_file.stem}_candidate_{candidate_index + 1}{suffix}"
    )


def _generate_single_candidate(
    prompt: str,
    output_file: Path,
    api_key: str,
    base_url: str,
    model: str,
    image_size: str,
    input_image: Optional[str],
) -> Optional[str]:
    try:
        return _generate_with_genai(
            prompt=prompt,
            output_file=output_file,
            api_key=api_key,
            base_url=base_url,
            model=model,
            image_size=image_size,
            input_image=input_image,
        )
    except Exception as exc:
        if _should_retry_with_resolution_fallback(exc, base_url, image_size):
            fallback_size = "1K"
            logger.warning(
                "Proxy %s rejected image_size=%s; retrying with provider-safe size=%s",
                base_url,
                image_size,
                fallback_size,
            )
            return _generate_with_genai(
                prompt=prompt,
                output_file=output_file,
                api_key=api_key,
                base_url=base_url,
                model=model,
                image_size=fallback_size,
                input_image=input_image,
            )
        raise


def _should_retry_with_resolution_fallback(
    exc: Exception,
    base_url: str,
    image_size: str,
) -> bool:
    """Retry aspect-ratio sizes against proxies that only accept resolution values."""
    if image_size not in VALID_RATIOS:
        return False
    if "12ai" not in (base_url or "").lower():
        return False

    message = str(exc).lower()
    return "image_size" in message and "invalid_value" in message


def _prepare_slide_image(
    source_path: Path,
    output_path: Path,
    normalize_for_slides: bool,
) -> Path:
    if not normalize_for_slides:
        if source_path.resolve() != output_path.resolve():
            shutil.copy2(source_path, output_path)
        return output_path

    return _normalize_for_slide_canvas(source_path, output_path)


def _normalize_for_slide_canvas(source_path: Path, output_path: Path) -> Path:
    from PIL import Image as PILImage
    from PIL import ImageEnhance, ImageFilter, ImageOps

    resampling = getattr(PILImage, "Resampling", PILImage)
    target_width, target_height = _DEFAULT_SLIDE_SIZE
    target_ratio = target_width / target_height

    with PILImage.open(source_path) as opened_image:
        image = _to_rgb_image(opened_image)
        source_ratio = image.width / image.height if image.height else target_ratio

        if abs(source_ratio - target_ratio) <= 0.05:
            canvas = ImageOps.fit(
                image,
                _DEFAULT_SLIDE_SIZE,
                method=resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
        else:
            canvas = ImageOps.fit(
                image,
                _DEFAULT_SLIDE_SIZE,
                method=resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=18))
            canvas = ImageEnhance.Brightness(canvas).enhance(0.72)

            foreground = ImageOps.contain(
                image,
                _DEFAULT_SLIDE_SIZE,
                method=resampling.LANCZOS,
            )
            offset = (
                (target_width - foreground.width) // 2,
                (target_height - foreground.height) // 2,
            )
            canvas.paste(foreground, offset)

        canvas.save(output_path, "PNG")

    return output_path


def _score_image_candidate(image_path: Path) -> float:
    from math import log2
    from PIL import Image as PILImage
    from PIL import ImageStat

    target_ratio = 16 / 9

    with PILImage.open(image_path) as opened_image:
        image = _to_rgb_image(opened_image)
        width, height = image.size
        ratio = width / height if height else target_ratio

        aspect_score = max(0.0, 1.0 - abs(ratio - target_ratio) / target_ratio)
        grayscale = image.convert("L")
        stat = ImageStat.Stat(grayscale)
        brightness = stat.mean[0] / 255 if stat.mean else 0.5
        contrast = min((stat.stddev[0] / 64), 1.0) if stat.stddev else 0.0
        brightness_score = max(0.0, 1.0 - abs(brightness - 0.55) / 0.55)
        area_score = min((width * height) / (_DEFAULT_SLIDE_SIZE[0] * _DEFAULT_SLIDE_SIZE[1]), 1.0)

        histogram = grayscale.histogram()
        total_pixels = float(sum(histogram) or 1)
        entropy = 0.0
        for count in histogram:
            if not count:
                continue
            probability = count / total_pixels
            entropy -= probability * log2(probability)
        entropy_score = min(entropy / 8.0, 1.0)

    return (
        aspect_score * 0.35
        + contrast * 0.25
        + entropy_score * 0.20
        + brightness_score * 0.10
        + area_score * 0.10
    )


def _to_rgb_image(image):
    if image.mode == "RGBA":
        from PIL import Image as PILImage

        rgb = PILImage.new("RGB", image.size, (255, 255, 255))
        rgb.paste(image, mask=image.split()[3])
        return rgb

    if image.mode != "RGB":
        return image.convert("RGB")

    return image.copy()


def _generate_with_genai(
    prompt: str,
    output_file: Path,
    api_key: str,
    base_url: str,
    model: str,
    image_size: str,
    input_image: Optional[str],
) -> Optional[str]:
    """Call google-genai SDK to generate an image."""
    from google import genai
    from google.genai import types
    from PIL import Image as PILImage

    # Build client with optional proxy base URL
    client_kwargs: dict = {"api_key": api_key}
    if base_url:
        client_kwargs["http_options"] = types.HttpOptions(
            base_url=base_url
        )

    client = genai.Client(**client_kwargs)

    # Build contents (image + text for editing, text only for generation)
    if input_image:
        img = PILImage.open(input_image)
        contents = [img, prompt]
        logger.debug("Image editing mode with input: %s", input_image)
    else:
        contents = prompt

    # Build generation config
    config_kwargs = {
        "response_modalities": ["TEXT", "IMAGE"],
    }
    # Prefer explicit image_size when the provider supports it.
    try:
        config_kwargs["image_config"] = types.ImageConfig(image_size=image_size)
    except Exception:
        logger.warning("ImageConfig(image_size=%s) unsupported; falling back to default size", image_size)

    gen_config = types.GenerateContentConfig(**config_kwargs)

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=gen_config,
    )

    # Extract and save image from response
    for part in response.parts:
        if part.text is not None:
            logger.debug("Model text response: %s", part.text[:200])
        elif part.inline_data is not None:
            image_data = part.inline_data.data
            if isinstance(image_data, str):
                import base64
                image_data = base64.b64decode(image_data)

            image = PILImage.open(BytesIO(image_data))
            _to_rgb_image(image).save(str(output_file), "PNG")

            logger.info("Image saved: %s", output_file.resolve())
            return str(output_file.resolve())

    logger.error("No image found in API response")
    return None
